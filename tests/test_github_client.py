"""GitHub client tests (parsing and rate limit helper)."""
from datetime import datetime, timezone

import pytest

from mcp_scout.github_client import GitHubClient, RateLimitInfo
from mcp_scout.models import RepositoryMetadata


def test_parse_repository_metadata():
    """Parse typical GitHub API repo response into RepositoryMetadata."""
    repo_data = {
        "html_url": "https://github.com/owner/repo",
        "name": "repo",
        "full_name": "owner/repo",
        "owner": {"login": "owner"},
        "description": "A repo",
        "language": "Python",
        "stargazers_count": 42,
        "forks_count": 1,
        "open_issues_count": 0,
        "size": 100,
        "created_at": "2020-01-01T00:00:00Z",
        "updated_at": "2024-06-01T12:00:00Z",
        "pushed_at": "2024-06-01T12:00:00Z",
        "license": {"spdx_id": "MIT"},
        "topics": ["cli"],
        "has_wiki": False,
        "has_pages": False,
        "archived": False,
        "disabled": False,
        "private": False,
        "default_branch": "main",
    }
    meta = GitHubClient.parse_repository_metadata(repo_data)
    assert isinstance(meta, RepositoryMetadata)
    assert meta.full_name == "owner/repo"
    assert meta.stars == 42
    assert meta.license == "MIT"
    assert meta.updated_at.tzinfo is not None


def test_parse_repository_metadata_no_license():
    repo_data = {
        "html_url": "https://github.com/a/b",
        "name": "b",
        "full_name": "a/b",
        "owner": {"login": "a"},
        "description": None,
        "language": None,
        "stargazers_count": 0,
        "forks_count": 0,
        "open_issues_count": 0,
        "size": 0,
        "created_at": "2020-01-01T00:00:00Z",
        "updated_at": "2020-01-01T00:00:00Z",
        "pushed_at": "2020-01-01T00:00:00Z",
        "license": None,
        "topics": [],
        "has_wiki": False,
        "has_pages": False,
        "archived": False,
        "disabled": False,
        "private": False,
        "default_branch": "main",
    }
    meta = GitHubClient.parse_repository_metadata(repo_data)
    assert meta.license is None


def test_rate_limit_info_seconds_until_reset():
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    reset_at = now + timedelta(seconds=90)
    info = RateLimitInfo(limit=5000, remaining=100, reset_at=reset_at, used=100)
    secs = info.seconds_until_reset
    assert 80 <= secs <= 92
