"""Generate Claude Desktop config snippets for scouted MCP servers.

The output is a best-guess JSON block users can paste into
`claude_desktop_config.json` under `mcpServers`. We can never know
the exact invocation, so this provides a starting template based on
the SDK language and repository name.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .models import RepositoryAnalysis, RepositoryMetadata


def generate_install_config(
    metadata: RepositoryMetadata, analysis: RepositoryAnalysis
) -> Optional[Dict[str, Any]]:
    """Return a `mcpServers` entry template, or None if we can't guess.

    Returns a single-key dict shaped like:
        {"mcpServers": {"<server-name>": {"command": "...", "args": [...]}}}
    """
    if not analysis.is_mcp_server:
        return None

    name = _server_name(metadata)
    template = _command_template(metadata, analysis)
    if template is None:
        return None

    return {
        "mcpServers": {
            name: template,
            # User-facing hint that this is a starting point, not a guarantee
            "_source": metadata.url,
        }
    }


def _server_name(metadata: RepositoryMetadata) -> str:
    """Slug suitable for the mcpServers key."""
    name = metadata.name.lower()
    # Strip common prefixes/suffixes for nicer keys
    for prefix in ("mcp-server-", "mcp-", "server-"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    for suffix in ("-mcp-server", "-mcp", "-server"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name or metadata.name.lower()


def _command_template(
    metadata: RepositoryMetadata, analysis: RepositoryAnalysis
) -> Optional[Dict[str, Any]]:
    """Best-effort invocation per SDK language."""
    sdk = analysis.mcp_sdk_language

    if sdk == "python":
        # Most python MCP servers ship as a uvx-installable package or a
        # python -m entry point. uvx is the more common install pattern.
        return {
            "command": "uvx",
            "args": [metadata.name],
            "_note": "Verify package name on PyPI; some repos publish under a different name.",
        }

    if sdk in ("typescript", "javascript"):
        # npx pattern is canonical for typescript MCP servers
        return {
            "command": "npx",
            "args": ["-y", metadata.name],
            "_note": "Verify npm package name; replace with @scope/name if scoped.",
        }

    if sdk == "go":
        return {
            "command": metadata.name,
            "args": [],
            "_note": "Build with `go install` first; binary name may differ.",
        }

    if sdk == "rust":
        return {
            "command": metadata.name,
            "args": [],
            "_note": "Install with `cargo install`; binary name may differ.",
        }

    if sdk == "java":
        return {
            "command": "java",
            "args": ["-jar", f"{metadata.name}.jar"],
            "_note": "Replace with actual jar path after build.",
        }

    # Unknown SDK but is_mcp_server was true — emit a placeholder
    return {
        "command": "<unknown>",
        "args": [],
        "_note": (
            "SDK language not detected. See the repo's README for install "
            "instructions: " + metadata.url
        ),
    }
