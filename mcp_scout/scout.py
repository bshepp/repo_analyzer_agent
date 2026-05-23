"""Main MCP Scout orchestrator."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional

from .analyzer import RepositoryAnalyzer
from .config import Config
from .github_client import GitHubClient
from .mcp_config_gen import generate_install_config
from .models import RepositoryMetadata, ScoutedRepository
from .scorer import RepositoryScorer

logger = logging.getLogger(__name__)


class MCPScout:
    """Discover and score MCP servers on GitHub."""

    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token or Config.GITHUB_TOKEN
        self.github_client: Optional[GitHubClient] = None
        self.analyzer: Optional[RepositoryAnalyzer] = None
        self.scorer = RepositoryScorer()

        if not Config.validate():
            logger.warning("Configuration validation failed")

    async def __aenter__(self):
        self.github_client = GitHubClient(self.github_token)
        await self.github_client.__aenter__()
        self.analyzer = RepositoryAnalyzer(self.github_client)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.github_client:
            await self.github_client.__aexit__(exc_type, exc_val, exc_tb)

    async def scout_repositories(
        self,
        query: Optional[str] = None,
        max_repositories: int = 100,
        min_stars: Optional[int] = None,
        languages: Optional[List[str]] = None,
        exclude_archived: bool = True,
        min_score: float = 50.0,
        require_mcp: bool = True,
    ) -> AsyncIterator[ScoutedRepository]:
        """Scout repositories matching `query`.

        require_mcp: if True (default), only yield repos where
        analysis.is_mcp_server is True. Set False to surface
        adjacent/near-miss repos for inspection.
        """
        if not self.github_client or not self.analyzer:
            raise RuntimeError("Scout not initialized. Use async with statement.")

        search_query = self._build_search_query(
            query, min_stars, languages, exclude_archived
        )
        logger.info(f"Searching repositories with query: {search_query}")

        analyzed_count = 0

        async for repo_data in self.github_client.search_repositories(
            search_query,
            per_page=100,
            max_pages=max_repositories // 100 + 1,
        ):
            if analyzed_count >= max_repositories:
                break
            try:
                metadata = GitHubClient.parse_repository_metadata(repo_data)
                if not self._meets_criteria(metadata, min_stars, exclude_archived):
                    continue

                analysis = await self.analyzer.analyze_repository(metadata)

                if require_mcp and not analysis.is_mcp_server:
                    logger.debug(f"Skipping {metadata.full_name} — not an MCP server")
                    continue

                score = self.scorer.score_repository(metadata, analysis)
                if score.total_score < min_score:
                    logger.debug(f"Skipping {metadata.full_name} (score: {score.total_score})")
                    continue

                install_config = generate_install_config(metadata, analysis)
                scouted = ScoutedRepository(
                    metadata=metadata,
                    analysis=analysis,
                    score=score,
                    analyzed_at=datetime.now(timezone.utc),
                    install_config=install_config,
                )
                logger.info(
                    f"Scouted {metadata.full_name} — score {score.total_score}, "
                    f"readiness {score.mcp_readiness}"
                )
                yield scouted
                analyzed_count += 1

            except (KeyboardInterrupt, asyncio.CancelledError):
                raise
            except Exception as e:
                logger.error(
                    f"Error analyzing {repo_data.get('full_name', 'unknown')}: {e}"
                )
                continue

    async def scout_single_repository(
        self, owner: str, repo: str
    ) -> Optional[ScoutedRepository]:
        """Scout a single repository by owner/repo."""
        if not self.github_client or not self.analyzer:
            raise RuntimeError("Scout not initialized. Use async with statement.")
        try:
            repo_data = await self.github_client.get_repository(owner, repo)
            if not repo_data:
                logger.error(f"Repository {owner}/{repo} not found")
                return None

            metadata = GitHubClient.parse_repository_metadata(repo_data)
            analysis = await self.analyzer.analyze_repository(metadata)
            score = self.scorer.score_repository(metadata, analysis)
            install_config = generate_install_config(metadata, analysis)

            return ScoutedRepository(
                metadata=metadata,
                analysis=analysis,
                score=score,
                analyzed_at=datetime.now(timezone.utc),
                install_config=install_config,
            )
        except Exception as e:
            logger.error(f"Error scouting {owner}/{repo}: {e}")
            return None

    async def get_rate_limit_status(self) -> Dict[str, Any]:
        if not self.github_client:
            raise RuntimeError("Scout not initialized. Use async with statement.")
        return await self.github_client.get_rate_limit_status()

    def _build_search_query(
        self,
        query: Optional[str],
        min_stars: Optional[int],
        languages: Optional[List[str]],
        exclude_archived: bool,
    ) -> str:
        parts: List[str] = []
        parts.append(query if query else Config.DEFAULT_SEARCH_QUERY)

        if min_stars is not None:
            parts.append(f"stars:>{min_stars}")
        elif Config.MIN_STARS_THRESHOLD > 0:
            parts.append(f"stars:>{Config.MIN_STARS_THRESHOLD}")

        if languages:
            for lang in languages:
                parts.append(f"language:{lang}")

        if exclude_archived:
            parts.append("archived:false")

        return " ".join(parts)

    def _meets_criteria(
        self,
        metadata: RepositoryMetadata,
        min_stars: Optional[int],
        exclude_archived: bool,
    ) -> bool:
        if exclude_archived and metadata.archived:
            return False
        if metadata.disabled:
            return False
        if min_stars is not None and metadata.stars < min_stars:
            return False
        return True

    async def batch_scout_repositories(
        self,
        repo_specs: List[Dict[str, str]],
        max_concurrent: int = 5,
    ) -> List[ScoutedRepository]:
        """Scout multiple specific repositories concurrently."""
        if not self.github_client or not self.analyzer:
            raise RuntimeError("Scout not initialized. Use async with statement.")

        semaphore = asyncio.Semaphore(max_concurrent)

        async def scout_one(spec: Dict[str, str]) -> Optional[ScoutedRepository]:
            async with semaphore:
                return await self.scout_single_repository(spec["owner"], spec["repo"])

        tasks = [scout_one(spec) for spec in repo_specs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        scouted: List[ScoutedRepository] = []
        for result in results:
            if isinstance(result, ScoutedRepository):
                scouted.append(result)
            elif isinstance(result, BaseException):
                if isinstance(result, (KeyboardInterrupt, asyncio.CancelledError)):
                    raise result
                logger.error(f"Error in batch scouting: {result}")
        return scouted

    def get_summary_statistics(
        self, scouted_repos: List[ScoutedRepository]
    ) -> Dict[str, Any]:
        if not scouted_repos:
            return {"total_repositories": 0}

        repo_dicts = [r.to_summary_dict() for r in scouted_repos]
        stats = self.scorer.get_statistics(repo_dicts)

        languages: Dict[str, int] = {}
        for r in scouted_repos:
            lang = r.analysis.mcp_sdk_language or (
                r.metadata.language.lower() if r.metadata.language else None
            )
            if lang:
                languages[lang] = languages.get(lang, 0) + 1

        tag_counts: Dict[str, int] = {}
        for r in scouted_repos:
            for tag in r.score.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        transports: Dict[str, int] = {}
        for r in scouted_repos:
            for t in r.analysis.mcp_transports:
                transports[t] = transports.get(t, 0) + 1

        stats.update({
            "top_sdk_languages": sorted(
                languages.items(), key=lambda x: x[1], reverse=True
            )[:10],
            "top_tags": sorted(
                tag_counts.items(), key=lambda x: x[1], reverse=True
            )[:15],
            "transports": transports,
            "mcp_readiness_distribution": {
                "high": len([r for r in scouted_repos if r.score.mcp_readiness == "high"]),
                "medium": len([r for r in scouted_repos if r.score.mcp_readiness == "medium"]),
                "low": len([r for r in scouted_repos if r.score.mcp_readiness == "low"]),
            },
            "total_tools_exposed": sum(
                r.analysis.mcp_tools_count for r in scouted_repos
            ),
        })

        return stats


# Backward-compat alias for code that still imports RepositoryScout
RepositoryScout = MCPScout
