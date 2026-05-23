"""Scorer tests."""
from datetime import datetime, timedelta, timezone

import pytest

from mcp_scout.models import RepositoryAnalysis, RepositoryMetadata, RepositoryScore
from mcp_scout.scorer import RepositoryScorer


def _meta(updated_days_ago: int = 0, license_name: str = "MIT") -> RepositoryMetadata:
    now = datetime.now(timezone.utc)
    updated = now - timedelta(days=updated_days_ago)
    return RepositoryMetadata(
        url="https://github.com/a/b",
        name="b",
        full_name="a/b",
        owner="a",
        description="",
        language="Python",
        stars=100,
        forks=0,
        issues=0,
        size=1000,
        created_at=now,
        updated_at=updated,
        pushed_at=updated,
        license=license_name,
        topics=[],
        has_wiki=False,
        has_pages=False,
        archived=False,
        disabled=False,
        private=False,
        default_branch="main",
    )


def _analysis(
    is_mcp_server: bool = True,
    tools: int = 4,
    resources: int = 1,
    prompts: int = 0,
    has_install: bool = True,
    sdk: str | None = "python",
    transports=None,
    doc_quality: float = 0.8,
    maintenance: float = 1.0,
    signals=None,
) -> RepositoryAnalysis:
    return RepositoryAnalysis(
        is_mcp_server=is_mcp_server,
        mcp_sdk_language=sdk,
        mcp_tools_count=tools,
        mcp_resources_count=resources,
        mcp_prompts_count=prompts,
        mcp_transports=transports if transports is not None else ["stdio"],
        has_install_snippet=has_install,
        documentation_quality=doc_quality,
        maintenance_score=maintenance,
        detected_signals=signals if signals is not None else [
            "manifest:mcp",
            "code:from mcp",
            "readme:mcp server",
        ],
        readme_summary="Summary",
    )


def test_score_repository_returns_score():
    scorer = RepositoryScorer()
    score = scorer.score_repository(_meta(updated_days_ago=7), _analysis())
    assert isinstance(score, RepositoryScore)
    assert 0 <= score.total_score <= 100
    assert score.mcp_readiness in ("high", "medium", "low")


def test_score_high_with_full_mcp_signals():
    scorer = RepositoryScorer()
    score = scorer.score_repository(_meta(updated_days_ago=1), _analysis(tools=8))
    assert score.total_score >= 70
    assert "stdio" in score.tags
    assert "python-mcp" in score.tags
    assert score.mcp_readiness in ("high", "medium")


def test_score_license_mit_full():
    scorer = RepositoryScorer()
    score = scorer.score_repository(_meta(license_name="MIT"), _analysis())
    assert score.license_score == 100.0


def test_non_mcp_repo_categorized_low():
    """Repos that fail is_mcp_server gate are always 'low' regardless of total."""
    scorer = RepositoryScorer()
    analysis = _analysis(
        is_mcp_server=False,
        tools=0,
        resources=0,
        prompts=0,
        has_install=False,
        sdk=None,
        transports=[],
        signals=[],
    )
    score = scorer.score_repository(_meta(updated_days_ago=1), analysis)
    assert score.mcp_readiness == "low"


def test_zero_tools_gives_zero_richness():
    scorer = RepositoryScorer()
    analysis = _analysis(tools=0, resources=0, prompts=0)
    score = scorer.score_repository(_meta(), analysis)
    assert score.tool_richness_score == 0.0


def test_tool_count_buckets():
    scorer = RepositoryScorer()
    # 10+ tools should be tagged tools:10+
    score = scorer.score_repository(_meta(), _analysis(tools=12))
    assert "tools:10+" in score.tags


def test_install_snippet_tag():
    scorer = RepositoryScorer()
    score = scorer.score_repository(_meta(), _analysis(has_install=True))
    assert "has-install-snippet" in score.tags
