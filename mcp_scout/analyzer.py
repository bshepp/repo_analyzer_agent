"""MCP server detection and analysis."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from .config import Config
from .github_client import GitHubClient
from .models import RepositoryAnalysis, RepositoryMetadata

logger = logging.getLogger(__name__)


# Files we sniff for dependency declarations across ecosystems.
# The actual file → language mapping lives in Config.MANIFEST_LANGUAGE_MAP.
_DEP_MANIFEST_NAMES = set(Config.MANIFEST_LANGUAGE_MAP.keys()) | {"Pipfile"}

# File extensions worth scanning for code-level MCP signals
_CODE_EXTENSIONS = (".py", ".ts", ".tsx", ".js", ".mjs", ".go", ".rs", ".java", ".kt")

# Directories we'll recurse into looking for MCP server code. Covers Python
# (src/, app/), TS/JS monorepos (packages/, src/), Go (cmd/, pkg/, internal/),
# Rust (src/), Java (lib/), and generic MCP layouts (server/, mcp/, handlers/).
_CODE_SUBDIRS = {
    "src", "server", "mcp", "app", "cmd", "pkg",
    "internal", "lib", "packages", "tools", "handlers",
}


def _dep_match(content: str, dep: str) -> bool:
    """True if `dep` appears in `content` as a standalone token.

    A 'standalone token' means the dep is not adjacent to a word character,
    dot, or hyphen on either side. This prevents `"mcp"` from matching
    `mcp-server`, `mcp.go`, `pythonmcp`, etc.
    """
    pattern = rf"(?<![\w.-]){re.escape(dep)}(?![\w.-])"
    return re.search(pattern, content) is not None


class RepositoryAnalyzer:
    """Detects whether a repo implements MCP and how well it does so."""

    def __init__(self, github_client: GitHubClient):
        self.github_client = github_client

    async def analyze_repository(self, metadata: RepositoryMetadata) -> RepositoryAnalysis:
        logger.info(f"Analyzing repository: {metadata.full_name}")

        contents = await self.github_client.get_repository_contents(
            metadata.owner, metadata.name
        )

        # Step 1: gather signals from manifests and code
        manifest_signals, sdk_language = await self._scan_manifests(metadata, contents)
        readme_text = await self._fetch_readme(metadata, contents)
        readme_signals = self._extract_readme_signals(readme_text)
        code_signals, tools, resources, prompts, transports = await self._scan_code(
            metadata, contents
        )

        detected_signals = sorted(manifest_signals | readme_signals | code_signals)

        # Step 2: aggregate
        is_mcp_server = self._is_mcp_server(
            manifest_signals, readme_signals, code_signals, tools
        )
        has_install_snippet = self._has_install_snippet(readme_text)
        doc_quality = self._score_readme_quality(readme_text)
        maintenance = self._maintenance_score(metadata)
        summary = self._readme_summary(readme_text)

        return RepositoryAnalysis(
            is_mcp_server=is_mcp_server,
            mcp_sdk_language=sdk_language,
            mcp_tools_count=tools,
            mcp_resources_count=resources,
            mcp_prompts_count=prompts,
            mcp_transports=sorted(transports),
            has_install_snippet=has_install_snippet,
            documentation_quality=doc_quality,
            maintenance_score=maintenance,
            detected_signals=detected_signals,
            readme_summary=summary,
        )

    # ---------- manifests ----------

    async def _scan_manifests(
        self, metadata: RepositoryMetadata, contents: List[Dict]
    ) -> Tuple[Set[str], Optional[str]]:
        """Look for MCP SDK declarations in dependency files.

        Each manifest is scoped to its language: only Python SDKs are checked
        in Python manifests, only TS SDKs in package.json, etc. This avoids
        false-positive Python tags on Go/TS/Rust repos that happen to mention
        an MCP-related string in their manifest.

        Returns (signals, sdk_language). When multiple languages match, we
        prefer the one matching the repo's primary GitHub-detected language.
        """
        signals: Set[str] = set()
        per_language_hits: Dict[str, int] = {}

        manifest_files = [
            f for f in contents
            if f.get("type") == "file" and f.get("name", "") in _DEP_MANIFEST_NAMES
        ]

        for file_info in manifest_files:
            language = Config.MANIFEST_LANGUAGE_MAP.get(file_info["name"])
            if not language:
                continue
            deps = Config.MCP_SDK_DEPS.get(language, [])
            if not deps:
                continue

            content = await self.github_client.get_file_content(
                metadata.owner, metadata.name, file_info["path"]
            )
            if not content:
                continue

            for dep in deps:
                if _dep_match(content, dep):
                    signals.add(f"manifest:{dep}")
                    per_language_hits[language] = per_language_hits.get(language, 0) + 1

        sdk_language = self._pick_sdk_language(per_language_hits, metadata.language)
        return signals, sdk_language

    @staticmethod
    def _pick_sdk_language(
        hits: Dict[str, int], primary_language: Optional[str]
    ) -> Optional[str]:
        """Resolve detected SDK language.

        Prefer the one that matches the repo's primary GitHub language;
        otherwise pick the one with the most manifest hits.
        """
        if not hits:
            return None
        if primary_language:
            primary_lower = primary_language.lower()
            # GitHub reports TypeScript/JavaScript separately; both map to "typescript"
            primary_norm = "typescript" if primary_lower in ("javascript",) else primary_lower
            if primary_norm in hits:
                return primary_norm
        return max(hits.items(), key=lambda kv: kv[1])[0]

    # ---------- code ----------

    async def _scan_code(
        self, metadata: RepositoryMetadata, contents: List[Dict]
    ) -> Tuple[Set[str], int, int, int, Set[str]]:
        """Scan a sample of source files for MCP code patterns and counts."""
        signals: Set[str] = set()
        tools = resources = prompts = 0
        transports: Set[str] = set()

        code_files = [
            f for f in contents
            if f.get("type") == "file"
            and f.get("name", "").lower().endswith(_CODE_EXTENSIONS)
        ]

        # Walk two levels deep into the directories most likely to contain
        # MCP server code, across Python/TS/Go/Rust/Java layouts.
        candidate_dirs = [
            f for f in contents
            if f.get("type") == "dir" and f.get("name", "").lower() in _CODE_SUBDIRS
        ]
        for dir_info in candidate_dirs:
            if len(code_files) >= Config.CODE_SAMPLE_SIZE:
                break
            sub = await self.github_client.get_repository_contents(
                metadata.owner, metadata.name, dir_info["path"]
            )
            code_files.extend(
                f for f in sub
                if f.get("type") == "file"
                and f.get("name", "").lower().endswith(_CODE_EXTENSIONS)
            )
            # One more level: monorepos (packages/*/, src/*/) often have a
            # per-server src/index.ts or cmd/<name>/main.go
            sub_dirs = [
                f for f in sub
                if f.get("type") == "dir"
                and not f.get("name", "").startswith(".")
            ]
            for sub_dir in sub_dirs[:4]:
                if len(code_files) >= Config.CODE_SAMPLE_SIZE:
                    break
                deeper = await self.github_client.get_repository_contents(
                    metadata.owner, metadata.name, sub_dir["path"]
                )
                code_files.extend(
                    f for f in deeper
                    if f.get("type") == "file"
                    and f.get("name", "").lower().endswith(_CODE_EXTENSIONS)
                )

        # Cap to a reasonable budget
        code_files = code_files[: Config.CODE_SAMPLE_SIZE]

        for file_info in code_files:
            content = await self.github_client.get_file_content(
                metadata.owner, metadata.name, file_info["path"]
            )
            if not content:
                continue

            for pattern in Config.MCP_CODE_PATTERNS:
                if pattern in content:
                    signals.add(f"code:{pattern}")

            tools += sum(
                len(re.findall(p, content)) for p in Config.TOOL_REGISTRATION_PATTERNS
            )
            resources += sum(
                len(re.findall(p, content)) for p in Config.RESOURCE_REGISTRATION_PATTERNS
            )
            prompts += sum(
                len(re.findall(p, content)) for p in Config.PROMPT_REGISTRATION_PATTERNS
            )

            for transport, patterns in Config.TRANSPORT_PATTERNS.items():
                if any(p in content for p in patterns):
                    transports.add(transport)

        return signals, tools, resources, prompts, transports

    # ---------- README ----------

    async def _fetch_readme(
        self, metadata: RepositoryMetadata, contents: List[Dict]
    ) -> str:
        readme_files = [
            f for f in contents if f.get("name", "").lower().startswith("readme")
        ]
        if not readme_files:
            return ""
        content = await self.github_client.get_file_content(
            metadata.owner, metadata.name, readme_files[0]["path"]
        )
        return content or ""

    def _extract_readme_signals(self, readme: str) -> Set[str]:
        if not readme:
            return set()
        lowered = readme.lower()
        return {
            f"readme:{sig}" for sig in Config.README_MCP_SIGNALS if sig in lowered
        }

    def _has_install_snippet(self, readme: str) -> bool:
        if not readme:
            return False
        return any(s in readme for s in Config.INSTALL_SNIPPET_SIGNALS)

    def _score_readme_quality(self, readme: str) -> float:
        """Score README quality on a 0-1 scale, biased toward MCP usefulness."""
        if not readme:
            return 0.0

        score = 0.0
        lowered = readme.lower()

        if any(k in lowered for k in ("installation", "install", "setup")):
            score += 0.15
        if any(k in lowered for k in ("usage", "example", "configure")):
            score += 0.15
        if "license" in lowered:
            score += 0.1
        if "```" in readme:
            score += 0.2
        if any(s in readme for s in Config.INSTALL_SNIPPET_SIGNALS):
            score += 0.2  # explicit install snippet is gold for MCP servers
        if any(s in lowered for s in Config.README_MCP_SIGNALS):
            score += 0.1
        score += min(0.1, len(readme) / 5000)

        return min(1.0, score)

    def _readme_summary(self, readme: str) -> Optional[str]:
        if not readme:
            return None
        lines: List[str] = []
        for line in readme.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("!["):
                lines.append(stripped)
                if len(" ".join(lines)) > 200:
                    break
        summary = " ".join(lines)
        if not summary:
            return None
        return (summary[:200] + "...") if len(summary) > 200 else summary

    # ---------- aggregation ----------

    def _is_mcp_server(
        self,
        manifest: Set[str],
        readme: Set[str],
        code: Set[str],
        tools: int,
    ) -> bool:
        """A repo is considered an MCP server if it has at least two of:

        - An MCP SDK in its manifest
        - At least one MCP-flavored code pattern
        - At least one registered tool/resource/prompt
        - A README that explicitly self-identifies as MCP
        """
        evidence = 0
        if manifest:
            evidence += 1
        if code:
            evidence += 1
        if tools > 0:
            evidence += 1
        if readme:
            evidence += 1
        return evidence >= 2

    def _maintenance_score(self, metadata: RepositoryMetadata) -> float:
        now = datetime.now(timezone.utc)
        updated = metadata.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        days = (now - updated).days
        if days <= 30:
            return 1.0
        if days <= 90:
            return 0.8
        if days <= 180:
            return 0.6
        if days <= 365:
            return 0.4
        return 0.2
