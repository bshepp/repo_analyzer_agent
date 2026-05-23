"""Data model tests."""
from datetime import datetime, timezone

import pytest

from mcp_scout.models import (
    RepositoryAnalysis,
    RepositoryMetadata,
    RepositoryScore,
    ScoutedRepository,
)


def _meta(now: datetime, **overrides) -> RepositoryMetadata:
    defaults = dict(
        url="https://github.com/a/b",
        name="b",
        full_name="a/b",
        owner="a",
        description="Desc",
        language="Python",
        stars=1,
        forks=0,
        issues=0,
        size=0,
        created_at=now,
        updated_at=now,
        pushed_at=now,
        license="MIT",
        topics=[],
        has_wiki=False,
        has_pages=False,
        archived=False,
        disabled=False,
        private=False,
        default_branch="main",
    )
    defaults.update(overrides)
    return RepositoryMetadata(**defaults)


def _analysis(**overrides) -> RepositoryAnalysis:
    defaults = dict(
        is_mcp_server=True,
        mcp_sdk_language="python",
        mcp_tools_count=3,
        mcp_resources_count=1,
        mcp_prompts_count=0,
        mcp_transports=["stdio"],
        has_install_snippet=True,
        documentation_quality=0.8,
        maintenance_score=0.9,
        detected_signals=["manifest:mcp", "code:from mcp", "readme:mcp server"],
        readme_summary="A short summary.",
    )
    defaults.update(overrides)
    return RepositoryAnalysis(**defaults)


def test_metadata_to_dict_iso_dates():
    now = datetime.now(timezone.utc)
    d = _meta(now).to_dict()
    assert d["full_name"] == "a/b"
    assert "T" in d["created_at"]


def test_analysis_to_dict_has_mcp_fields():
    d = _analysis().to_dict()
    assert d["is_mcp_server"] is True
    assert d["mcp_sdk_language"] == "python"
    assert d["mcp_tools_count"] == 3
    assert d["mcp_transports"] == ["stdio"]


def test_scouted_repo_to_summary_dict():
    now = datetime.now(timezone.utc)
    meta = _meta(now, language="Go", license=None, url="https://github.com/x/y",
                 name="y", full_name="x/y", owner="x", description=None)
    analysis = _analysis(
        is_mcp_server=False,
        mcp_sdk_language=None,
        mcp_tools_count=0,
        mcp_resources_count=0,
        mcp_prompts_count=0,
        mcp_transports=[],
        has_install_snippet=False,
        documentation_quality=0.0,
        maintenance_score=0.5,
        detected_signals=[],
        readme_summary=None,
    )
    score = RepositoryScore(
        total_score=20.0,
        mcp_compliance_score=0.0,
        tool_richness_score=0.0,
        install_ergonomics_score=0.0,
        license_score=30.0,
        maintenance_score=50.0,
        tags=["go"],
        mcp_readiness="low",
    )
    repo = ScoutedRepository(metadata=meta, analysis=analysis, score=score, analyzed_at=now)
    summary = repo.to_summary_dict()
    assert summary["url"] == "https://github.com/x/y"
    assert summary["score"] == 20.0
    assert summary["mcp_readiness"] == "low"
    assert summary["tools"] == 0
    assert summary["sdk_language"] is None


def test_scouted_repo_with_install_config_serializes():
    now = datetime.now(timezone.utc)
    repo = ScoutedRepository(
        metadata=_meta(now),
        analysis=_analysis(),
        score=RepositoryScore(
            total_score=85.0,
            mcp_compliance_score=90.0,
            tool_richness_score=80.0,
            install_ergonomics_score=90.0,
            license_score=100.0,
            maintenance_score=100.0,
            tags=["python-mcp", "stdio"],
            mcp_readiness="high",
        ),
        analyzed_at=now,
        install_config={"mcpServers": {"b": {"command": "uvx", "args": ["b"]}}},
    )
    d = repo.to_dict()
    assert "install_config" in d
    assert d["install_config"]["mcpServers"]["b"]["command"] == "uvx"
