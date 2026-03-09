"""
Data models for Repository Scout
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
import json


@dataclass
class RepositoryMetadata:
    """Core repository metadata from GitHub API"""
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
        """Convert to dictionary for JSON serialization"""
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
            "default_branch": self.default_branch
        }


@dataclass
class RepositoryAnalysis:
    """Analysis results for a repository"""
    has_cli: bool
    has_api: bool
    has_documentation: bool
    documentation_quality: float  # 0.0 to 1.0
    code_complexity: float  # 0.0 to 1.0 (lower is better)
    modularity_score: float  # 0.0 to 1.0
    maintenance_score: float  # 0.0 to 1.0
    detected_frameworks: List[str]
    detected_patterns: List[str]
    readme_summary: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "has_cli": self.has_cli,
            "has_api": self.has_api,
            "has_documentation": self.has_documentation,
            "documentation_quality": self.documentation_quality,
            "code_complexity": self.code_complexity,
            "modularity_score": self.modularity_score,
            "maintenance_score": self.maintenance_score,
            "detected_frameworks": self.detected_frameworks,
            "detected_patterns": self.detected_patterns,
            "readme_summary": self.readme_summary
        }


@dataclass
class RepositoryScore:
    """Final scoring results for a repository"""
    total_score: float  # 0.0 to 100.0
    cli_api_score: float  # 30% weight
    documentation_score: float  # 20% weight
    simplicity_score: float  # 20% weight
    license_score: float  # 20% weight
    maintenance_score: float  # 10% weight
    tags: List[str]
    agent_friendliness: str  # "high", "medium", "low"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "total_score": self.total_score,
            "cli_api_score": self.cli_api_score,
            "documentation_score": self.documentation_score,
            "simplicity_score": self.simplicity_score,
            "license_score": self.license_score,
            "maintenance_score": self.maintenance_score,
            "tags": self.tags,
            "agent_friendliness": self.agent_friendliness
        }


@dataclass
class ScoutedRepository:
    """Complete repository analysis result"""
    metadata: RepositoryMetadata
    analysis: RepositoryAnalysis
    score: RepositoryScore
    analyzed_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "metadata": self.metadata.to_dict(),
            "analysis": self.analysis.to_dict(),
            "score": self.score.to_dict(),
            "analyzed_at": self.analyzed_at.isoformat()
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert to summary format matching the project spec"""
        return {
            "url": self.metadata.url,
            "score": self.score.total_score,
            "tags": self.score.tags,
            "summary": self.analysis.readme_summary or f"{self.metadata.description or 'Repository'} - {self.metadata.language or 'Unknown'} project",
            "last_updated": self.metadata.updated_at.isoformat()[:10],  # YYYY-MM-DD format
            "license": self.metadata.license,
            "agent_friendliness": self.score.agent_friendliness
        }