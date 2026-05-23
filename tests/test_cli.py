"""CLI and export tests."""
import csv
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mcp_scout.cli import (
    export_install_configs,
    export_to_csv,
    export_to_json,
    export_to_jsonl,
)
from mcp_scout.config import Config
from mcp_scout.models import (
    RepositoryAnalysis,
    RepositoryMetadata,
    RepositoryScore,
    ScoutedRepository,
)


def _make_scouted_repo(
    name: str = "owner/repo",
    score: float = 75.0,
    tags: list | None = None,
    with_install_config: bool = True,
) -> ScoutedRepository:
    if tags is None:
        tags = ["python-mcp", "stdio"]
    now = datetime.now(timezone.utc)
    owner, repo_name = name.split("/")
    meta = RepositoryMetadata(
        url=f"https://github.com/{name}",
        name=repo_name,
        full_name=name,
        owner=owner,
        description="A test MCP server",
        language="Python",
        stars=100,
        forks=10,
        issues=2,
        size=500,
        created_at=now,
        updated_at=now,
        pushed_at=now,
        license="MIT",
        topics=["mcp"],
        has_wiki=False,
        has_pages=False,
        archived=False,
        disabled=False,
        private=False,
        default_branch="main",
    )
    analysis = RepositoryAnalysis(
        is_mcp_server=True,
        mcp_sdk_language="python",
        mcp_tools_count=3,
        mcp_resources_count=1,
        mcp_prompts_count=0,
        mcp_transports=["stdio"],
        has_install_snippet=True,
        documentation_quality=0.8,
        maintenance_score=0.9,
        detected_signals=["manifest:mcp", "code:from mcp"],
        readme_summary="A short summary.",
    )
    score_obj = RepositoryScore(
        total_score=score,
        mcp_compliance_score=85.0,
        tool_richness_score=70.0,
        install_ergonomics_score=80.0,
        license_score=100.0,
        maintenance_score=90.0,
        tags=tags,
        mcp_readiness="high",
    )
    install = (
        {"mcpServers": {repo_name: {"command": "uvx", "args": [repo_name]}}}
        if with_install_config
        else None
    )
    return ScoutedRepository(
        metadata=meta,
        analysis=analysis,
        score=score_obj,
        analyzed_at=now,
        install_config=install,
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
            obj = json.loads(line)
            assert "metadata" in obj and "score" in obj and "analysis" in obj
    finally:
        Path(path).unlink(missing_ok=True)


def test_export_json_valid():
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
        assert data[0]["analysis"]["is_mcp_server"] is True
    finally:
        Path(path).unlink(missing_ok=True)


def test_export_csv_has_headers_and_rows():
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
        assert "mcp_readiness" in rows[0]
    finally:
        Path(path).unlink(missing_ok=True)


def test_export_csv_empty_no_file_write():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        path = f.name
    try:
        export_to_csv([], path)
        assert Path(path).stat().st_size == 0
    finally:
        Path(path).unlink(missing_ok=True)


def test_export_install_configs_merges_servers():
    """Merged install config should have one entry per repo with install_config."""
    repos = [
        _make_scouted_repo("a/b", with_install_config=True),
        _make_scouted_repo("c/d", with_install_config=True),
        _make_scouted_repo("e/f", with_install_config=False),
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = f.name
    try:
        export_install_configs(repos, path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert "mcpServers" in data
        # Two should be present (one has no install_config)
        assert len(data["mcpServers"]) == 2
        # Source URLs should be annotated
        for entry in data["mcpServers"].values():
            assert "_source" in entry
    finally:
        Path(path).unlink(missing_ok=True)


def test_config_weights_sum_to_one():
    """Scoring weights must sum to 1.0."""
    assert abs(sum(Config.SCORING_WEIGHTS.values()) - 1.0) < 1e-9


def test_config_validate_weights():
    assert Config.validate() is True


def test_cli_help_exits_zero():
    """CLI --help runs and exits with 0."""
    result = subprocess.run(
        [sys.executable, "-m", "mcp_scout.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0
    assert "MCP Scout" in result.stdout or "mcp" in result.stdout.lower()
