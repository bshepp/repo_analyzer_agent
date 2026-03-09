"""CLI and export tests."""
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from repo_scout.cli import export_to_jsonl, export_to_json, export_to_csv
from repo_scout.models import (
    RepositoryMetadata,
    RepositoryAnalysis,
    RepositoryScore,
    ScoutedRepository,
)
from repo_scout.config import Config
from datetime import datetime, timezone


def _make_scouted_repo(
    name: str = "owner/repo",
    score: float = 75.0,
    tags: list | None = None,
) -> ScoutedRepository:
    if tags is None:
        tags = ["python", "cli"]
    now = datetime.now(timezone.utc)
    meta = RepositoryMetadata(
        url=f"https://github.com/{name}",
        name=name.split("/")[-1],
        full_name=name,
        owner=name.split("/")[0],
        description="A test repo",
        language="Python",
        stars=100,
        forks=10,
        issues=2,
        size=500,
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
    analysis = RepositoryAnalysis(
        has_cli=True,
        has_api=False,
        has_documentation=True,
        documentation_quality=0.8,
        code_complexity=0.3,
        modularity_score=0.7,
        maintenance_score=0.9,
        detected_frameworks=["click"],
        detected_patterns=["cli"],
        readme_summary="A short summary.",
    )
    score_obj = RepositoryScore(
        total_score=score,
        cli_api_score=80.0,
        documentation_score=70.0,
        simplicity_score=75.0,
        license_score=100.0,
        maintenance_score=90.0,
        tags=tags,
        agent_friendliness="high",
    )
    return ScoutedRepository(
        metadata=meta,
        analysis=analysis,
        score=score_obj,
        analyzed_at=now,
    )


def test_export_jsonl_one_line_per_repo():
    """JSONL must be one compact JSON object per line."""
    repos = [_make_scouted_repo("a/b"), _make_scouted_repo("c/d")]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        export_to_jsonl(repos, path)
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2
        for line in lines:
            line = line.strip()
            assert "\n" not in line
            obj = json.loads(line)
            assert "metadata" in obj and "score" in obj
    finally:
        Path(path).unlink(missing_ok=True)


def test_export_json_valid():
    """JSON export produces valid JSON array."""
    repos = [_make_scouted_repo()]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = f.name
    try:
        export_to_json(repos, path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["metadata"]["full_name"] == "owner/repo"
    finally:
        Path(path).unlink(missing_ok=True)


def test_export_csv_has_headers_and_rows():
    """CSV export has header row and one data row per repo."""
    repos = [_make_scouted_repo(), _make_scouted_repo("x/y")]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        path = f.name
    try:
        export_to_csv(repos, path)
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        assert "url" in rows[0] and "score" in rows[0]
    finally:
        Path(path).unlink(missing_ok=True)


def test_export_csv_empty_no_file_write():
    """CSV export with no repos does not write a file with invalid CSV."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        path = f.name
    try:
        export_to_csv([], path)
        # Should return without opening/writing invalid CSV
        assert Path(path).stat().st_size == 0
    finally:
        Path(path).unlink(missing_ok=True)


def test_config_weights_sum_to_one():
    """Scoring weights must sum to 1.0."""
    assert sum(Config.SCORING_WEIGHTS.values()) == 1.0


def test_config_validate_weights():
    """Config.validate fails only when weights are wrong (tested indirectly via sum)."""
    assert Config.validate() is True


def test_cli_help_exits_zero():
    """CLI --help runs and exits with 0."""
    result = subprocess.run(
        [sys.executable, "-m", "repo_scout.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0
    assert "Repository Scout" in result.stdout or "repository" in result.stdout.lower()
