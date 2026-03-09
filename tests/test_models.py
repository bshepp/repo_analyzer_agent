"""Data model tests."""
from datetime import datetime, timezone

import pytest

from repo_scout.models import (
    RepositoryMetadata,
    RepositoryAnalysis,
    RepositoryScore,
    ScoutedRepository,
)


def test_metadata_to_dict_iso_dates():
    now = datetime.now(timezone.utc)
    meta = RepositoryMetadata(
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
    d = meta.to_dict()
    assert d["full_name"] == "a/b"
    assert "T" in d["created_at"] and "Z" in d["created_at"] or "+" in d["created_at"]


def test_scouted_repo_to_summary_dict():
    now = datetime.now(timezone.utc)
    meta = RepositoryMetadata(
        url="https://github.com/x/y",
        name="y",
        full_name="x/y",
        owner="x",
        description=None,
        language="Go",
        stars=5,
        forks=0,
        issues=0,
        size=0,
        created_at=now,
        updated_at=now,
        pushed_at=now,
        license=None,
        topics=[],
        has_wiki=False,
        has_pages=False,
        archived=False,
        disabled=False,
        private=False,
        default_branch="main",
    )
    analysis = RepositoryAnalysis(
        has_cli=False,
        has_api=True,
        has_documentation=False,
        documentation_quality=0.0,
        code_complexity=0.5,
        modularity_score=0.5,
        maintenance_score=0.5,
        detected_frameworks=[],
        detected_patterns=[],
        readme_summary=None,
    )
    score = RepositoryScore(
        total_score=60.0,
        cli_api_score=50.0,
        documentation_score=50.0,
        simplicity_score=50.0,
        license_score=50.0,
        maintenance_score=50.0,
        tags=["api"],
        agent_friendliness="medium",
    )
    repo = ScoutedRepository(metadata=meta, analysis=analysis, score=score, analyzed_at=now)
    summary = repo.to_summary_dict()
    assert summary["url"] == "https://github.com/x/y"
    assert summary["score"] == 60.0
    assert "summary" in summary
    assert summary["agent_friendliness"] == "medium"
