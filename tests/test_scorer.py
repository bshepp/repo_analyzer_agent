"""Scorer tests."""
from datetime import datetime, timezone, timedelta

import pytest

from repo_scout.models import RepositoryMetadata, RepositoryAnalysis, RepositoryScore
from repo_scout.scorer import RepositoryScorer


def _meta(updated_days_ago: int = 0, license_name: str = "MIT"):
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


def _analysis(has_cli=True, has_api=True, has_docs=True, doc_quality=0.8, maintenance=1.0):
    return RepositoryAnalysis(
        has_cli=has_cli,
        has_api=has_api,
        has_documentation=has_docs,
        documentation_quality=doc_quality,
        code_complexity=0.2,
        modularity_score=0.8,
        maintenance_score=maintenance,
        detected_frameworks=["flask", "click"],
        detected_patterns=["api", "cli"],
        readme_summary="Summary",
    )


def test_score_repository_returns_score():
    scorer = RepositoryScorer()
    meta = _meta(updated_days_ago=7)
    analysis = _analysis()
    score = scorer.score_repository(meta, analysis)
    assert isinstance(score, RepositoryScore)
    assert 0 <= score.total_score <= 100
    assert score.agent_friendliness in ("high", "medium", "low")


def test_score_high_with_cli_api_docs():
    scorer = RepositoryScorer()
    meta = _meta(updated_days_ago=1)
    analysis = _analysis(has_cli=True, has_api=True, has_docs=True, doc_quality=0.9)
    score = scorer.score_repository(meta, analysis)
    assert score.total_score >= 70
    assert "cli" in score.tags and "api" in score.tags


def test_score_license_mit_full():
    scorer = RepositoryScorer()
    meta = _meta(license_name="MIT")
    analysis = _analysis()
    score = scorer.score_repository(meta, analysis)
    assert score.license_score == 100.0


def test_categorize_high_medium_low():
    scorer = RepositoryScorer()
    meta_old = _meta(updated_days_ago=400)
    analysis_low = _analysis(has_cli=False, has_api=False, has_docs=False, doc_quality=0.0)
    score_low = scorer.score_repository(meta_old, analysis_low)
    assert score_low.agent_friendliness == "low"
