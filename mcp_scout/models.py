"""Data models for MCP Scout."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
import json


@dataclass
class RepositoryMetadata:
    """Core repository metadata from GitHub API."""
    url: str
    name: str
    full_name: str
    owner: str
    description: Optional[str]
    language: Optional[str]
    stars: int
    forks: int
    issues: int
    size: int
    created_at: datetime
    updated_at: datetime
    pushed_at: datetime
    license: Optional[str]
    topics: List[str]
    has_wiki: bool
    has_pages: bool
    archived: bool
    disabled: bool
    private: bool
    default_branch: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "name": self.name,
            "full_name": self.full_name,
            "owner": self.owner,
            "description": self.description,
            "language": self.language,
            "stars": self.stars,
            "forks": self.forks,
            "issues": self.issues,
            "size": self.size,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "pushed_at": self.pushed_at.isoformat(),
            "license": self.license,
            "topics": self.topics,
            "has_wiki": self.has_wiki,
            "has_pages": self.has_pages,
            "archived": self.archived,
            "disabled": self.disabled,
            "private": self.private,
            "default_branch": self.default_branch,
        }


@dataclass
class RepositoryAnalysis:
    """MCP-specific analysis results for a repository."""

    is_mcp_server: bool                       # Strong evidence this implements MCP
    mcp_sdk_language: Optional[str]           # python | typescript | go | rust | java | None
    mcp_tools_count: int                      # Detected tool registrations
    mcp_resources_count: int                  # Detected resource registrations
    mcp_prompts_count: int                    # Detected prompt registrations
    mcp_transports: List[str]                 # ["stdio", "sse", "http"] subset
    has_install_snippet: bool                 # README has claude_desktop_config / uvx / npx snippet
    documentation_quality: float              # 0.0 to 1.0
    maintenance_score: float                  # 0.0 to 1.0
    detected_signals: List[str]               # Raw MCP signals found (for debugging/tags)
    readme_summary: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_mcp_server": self.is_mcp_server,
            "mcp_sdk_language": self.mcp_sdk_language,
            "mcp_tools_count": self.mcp_tools_count,
            "mcp_resources_count": self.mcp_resources_count,
            "mcp_prompts_count": self.mcp_prompts_count,
            "mcp_transports": self.mcp_transports,
            "has_install_snippet": self.has_install_snippet,
            "documentation_quality": self.documentation_quality,
            "maintenance_score": self.maintenance_score,
            "detected_signals": self.detected_signals,
            "readme_summary": self.readme_summary,
        }


@dataclass
class RepositoryScore:
    """Final MCP-friendliness scoring for a repository."""

    total_score: float                # 0.0 to 100.0
    mcp_compliance_score: float       # 40% weight
    tool_richness_score: float        # 20% weight
    install_ergonomics_score: float   # 15% weight
    license_score: float              # 15% weight
    maintenance_score: float          # 10% weight
    tags: List[str]
    mcp_readiness: str                # "high", "medium", "low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_score": self.total_score,
            "mcp_compliance_score": self.mcp_compliance_score,
            "tool_richness_score": self.tool_richness_score,
            "install_ergonomics_score": self.install_ergonomics_score,
            "license_score": self.license_score,
            "maintenance_score": self.maintenance_score,
            "tags": self.tags,
            "mcp_readiness": self.mcp_readiness,
        }


@dataclass
class ScoutedRepository:
    """Complete repository analysis result."""
    metadata: RepositoryMetadata
    analysis: RepositoryAnalysis
    score: RepositoryScore
    analyzed_at: datetime
    install_config: Optional[Dict[str, Any]] = None  # Generated Claude Desktop config snippet

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "metadata": self.metadata.to_dict(),
            "analysis": self.analysis.to_dict(),
            "score": self.score.to_dict(),
            "analyzed_at": self.analyzed_at.isoformat(),
        }
        if self.install_config is not None:
            d["install_config"] = self.install_config
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_summary_dict(self) -> Dict[str, Any]:
        """Compact summary format suitable for CSV / quick scanning."""
        return {
            "url": self.metadata.url,
            "score": self.score.total_score,
            "tags": self.score.tags,
            "mcp_readiness": self.score.mcp_readiness,
            "tools": self.analysis.mcp_tools_count,
            "resources": self.analysis.mcp_resources_count,
            "prompts": self.analysis.mcp_prompts_count,
            "transports": self.analysis.mcp_transports,
            "sdk_language": self.analysis.mcp_sdk_language,
            "summary": self.analysis.readme_summary or (self.metadata.description or ""),
            "last_updated": self.metadata.updated_at.isoformat()[:10],
            "license": self.metadata.license,
        }
