"""MCP-friendliness scoring."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from .config import Config
from .models import RepositoryAnalysis, RepositoryMetadata, RepositoryScore

logger = logging.getLogger(__name__)


class RepositoryScorer:
    """Scores repositories on how good they are as MCP servers."""

    def __init__(self) -> None:
        self.weights = Config.SCORING_WEIGHTS
        self.license_scores = Config.LICENSE_SCORES

    def score_repository(
        self, metadata: RepositoryMetadata, analysis: RepositoryAnalysis
    ) -> RepositoryScore:
        logger.info(f"Scoring repository: {metadata.full_name}")

        mcp_compliance = self._score_mcp_compliance(analysis)
        tool_richness = self._score_tool_richness(analysis)
        install_ergo = self._score_install_ergonomics(analysis)
        license_s = self._score_license(metadata)
        maintenance = analysis.maintenance_score

        total = (
            mcp_compliance * self.weights["mcp_compliance"]
            + tool_richness * self.weights["tool_richness"]
            + install_ergo * self.weights["install_ergonomics"]
            + license_s * self.weights["license"]
            + maintenance * self.weights["maintenance"]
        ) * 100

        tags = self._generate_tags(metadata, analysis)
        readiness = self._categorize_readiness(total, analysis.is_mcp_server)

        return RepositoryScore(
            total_score=round(total, 1),
            mcp_compliance_score=round(mcp_compliance * 100, 1),
            tool_richness_score=round(tool_richness * 100, 1),
            install_ergonomics_score=round(install_ergo * 100, 1),
            license_score=round(license_s * 100, 1),
            maintenance_score=round(maintenance * 100, 1),
            tags=tags,
            mcp_readiness=readiness,
        )

    # ---------- component scores ----------

    def _score_mcp_compliance(self, analysis: RepositoryAnalysis) -> float:
        """How confidently is this an MCP server?"""
        if not analysis.is_mcp_server:
            # Non-MCP repos get a small partial score if there's any signal,
            # so the ranking is monotonic for borderline cases.
            return 0.1 if analysis.detected_signals else 0.0

        score = 0.5  # base for crossing the is_mcp_server bar

        if analysis.mcp_sdk_language is not None:
            score += 0.2  # explicit SDK dep is the strongest signal
        if analysis.mcp_transports:
            score += min(0.15, 0.05 + 0.05 * len(analysis.mcp_transports))
        signal_count = len(analysis.detected_signals)
        if signal_count >= 5:
            score += 0.15
        elif signal_count >= 3:
            score += 0.1

        return min(1.0, score)

    def _score_tool_richness(self, analysis: RepositoryAnalysis) -> float:
        """Tool/resource/prompt count, weighted toward tools."""
        # Tools count fully; resources & prompts half.
        effective = (
            analysis.mcp_tools_count
            + 0.5 * analysis.mcp_resources_count
            + 0.5 * analysis.mcp_prompts_count
        )
        if effective <= 0:
            return 0.0
        if effective < 2:
            return 0.4
        if effective < 4:
            return 0.6
        if effective < 8:
            return 0.8
        return 1.0

    def _score_install_ergonomics(self, analysis: RepositoryAnalysis) -> float:
        """Can a user actually wire this up?"""
        score = 0.0
        if analysis.has_install_snippet:
            score += 0.5
        score += 0.5 * analysis.documentation_quality
        return min(1.0, score)

    def _score_license(self, metadata: RepositoryMetadata) -> float:
        if not metadata.license:
            return 0.3  # unknown license discounted
        return self.license_scores.get(metadata.license, 0.5)

    # ---------- tags ----------

    def _generate_tags(
        self, metadata: RepositoryMetadata, analysis: RepositoryAnalysis
    ) -> List[str]:
        tags: List[str] = []

        # Language / SDK
        if analysis.mcp_sdk_language:
            sdk_tag = Config.LANGUAGE_TAG_MAP.get(analysis.mcp_sdk_language)
            if sdk_tag:
                tags.append(sdk_tag)
        elif metadata.language:
            tags.append(metadata.language.lower())

        # Transports
        for transport in analysis.mcp_transports:
            tags.append(transport)

        # Tool count buckets
        total_tools = analysis.mcp_tools_count
        if total_tools >= 10:
            tags.append("tools:10+")
        elif total_tools >= 5:
            tags.append("tools:5+")
        elif total_tools >= 1:
            tags.append(f"tools:{total_tools}")

        if analysis.mcp_resources_count > 0:
            tags.append("has-resources")
        if analysis.mcp_prompts_count > 0:
            tags.append("has-prompts")
        if analysis.has_install_snippet:
            tags.append("has-install-snippet")

        # Popularity
        if metadata.stars > 5000:
            tags.append("popular")
        elif metadata.stars > 500:
            tags.append("well-known")

        # Activity
        now = datetime.now(timezone.utc)
        updated = metadata.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        days = (now - updated).days
        if days <= 30:
            tags.append("active")
        elif days > 365:
            tags.append("inactive")

        # License category
        if metadata.license:
            cat = self._license_category(metadata.license)
            if cat:
                tags.append(cat)

        return sorted(set(tags))

    def _license_category(self, license_name: str) -> str:
        permissive = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unlicense"}
        copyleft = {"GPL-3.0", "GPL-2.0", "AGPL-3.0"}
        weak_copyleft = {"LGPL-3.0", "LGPL-2.1", "MPL-2.0"}
        if license_name in permissive:
            return "permissive"
        if license_name in copyleft:
            return "copyleft"
        if license_name in weak_copyleft:
            return "weak-copyleft"
        return "other-license"

    # ---------- readiness ----------

    def _categorize_readiness(self, total: float, is_mcp_server: bool) -> str:
        """Map total score to a readiness bucket.

        Non-MCP repos are always 'low' regardless of total, since the rubric
        is *for* MCP servers.
        """
        if not is_mcp_server:
            return "low"
        if total >= 75:
            return "high"
        if total >= 55:
            return "medium"
        return "low"

    # ---------- collection helpers (unchanged shape) ----------

    def filter_by_score(
        self, repositories: List[Dict[str, Any]], min_score: float = 50.0
    ) -> List[Dict[str, Any]]:
        return [r for r in repositories if r.get("score", 0) >= min_score]

    def sort_by_score(
        self, repositories: List[Dict[str, Any]], reverse: bool = True
    ) -> List[Dict[str, Any]]:
        return sorted(repositories, key=lambda x: x.get("score", 0), reverse=reverse)

    def get_top_repositories(
        self, repositories: List[Dict[str, Any]], limit: int = 100
    ) -> List[Dict[str, Any]]:
        return self.sort_by_score(repositories)[:limit]

    def get_statistics(self, repositories: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not repositories:
            return {}
        scores = [r.get("score", 0) for r in repositories]
        return {
            "total_repositories": len(repositories),
            "average_score": sum(scores) / len(scores),
            "median_score": sorted(scores)[len(scores) // 2],
            "min_score": min(scores),
            "max_score": max(scores),
            "high_count": len([s for s in scores if s >= 75]),
            "medium_count": len([s for s in scores if 55 <= s < 75]),
            "low_count": len([s for s in scores if s < 55]),
        }
