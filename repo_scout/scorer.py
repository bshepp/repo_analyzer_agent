"""
Repository scoring system based on agent-friendliness criteria
"""

import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone

from .config import Config
from .models import RepositoryMetadata, RepositoryAnalysis, RepositoryScore


logger = logging.getLogger(__name__)


class RepositoryScorer:
    """Scores repositories based on agent-friendliness criteria"""
    
    def __init__(self):
        self.weights = Config.SCORING_WEIGHTS
        self.license_scores = Config.LICENSE_SCORES
    
    def score_repository(self, metadata: RepositoryMetadata, analysis: RepositoryAnalysis) -> RepositoryScore:
        """Calculate comprehensive score for a repository"""
        logger.info(f"Scoring repository: {metadata.full_name}")
        
        # Calculate individual scores
        cli_api_score = self._score_cli_api(analysis)
        documentation_score = self._score_documentation(analysis)
        simplicity_score = self._score_simplicity(analysis)
        license_score = self._score_license(metadata)
        maintenance_score = self._score_maintenance(analysis)
        
        # Calculate weighted total score
        total_score = (
            cli_api_score * self.weights["cli_api"] +
            documentation_score * self.weights["documentation"] +
            simplicity_score * self.weights["simplicity"] +
            license_score * self.weights["license"] +
            maintenance_score * self.weights["maintenance"]
        ) * 100  # Convert to 0-100 scale
        
        # Generate tags
        tags = self._generate_tags(metadata, analysis)
        
        # Determine agent friendliness category
        agent_friendliness = self._categorize_agent_friendliness(total_score)
        
        return RepositoryScore(
            total_score=round(total_score, 1),
            cli_api_score=round(cli_api_score * 100, 1),
            documentation_score=round(documentation_score * 100, 1),
            simplicity_score=round(simplicity_score * 100, 1),
            license_score=round(license_score * 100, 1),
            maintenance_score=round(maintenance_score * 100, 1),
            tags=tags,
            agent_friendliness=agent_friendliness
        )
    
    def _score_cli_api(self, analysis: RepositoryAnalysis) -> float:
        """Score CLI/API availability (30% weight)"""
        score = 0.0
        
        # CLI interface
        if analysis.has_cli:
            score += 0.6
        
        # API interface
        if analysis.has_api:
            score += 0.4
        
        # Bonus for having both
        if analysis.has_cli and analysis.has_api:
            score += 0.2
        
        # Framework bonus
        web_frameworks = ["flask", "fastapi", "django", "tornado", "bottle"]
        cli_frameworks = ["click", "typer", "argparse", "fire"]
        
        has_web_framework = any(fw in analysis.detected_frameworks for fw in web_frameworks)
        has_cli_framework = any(fw in analysis.detected_frameworks for fw in cli_frameworks)
        
        if has_web_framework:
            score += 0.1
        if has_cli_framework:
            score += 0.1
        
        return min(1.0, score)
    
    def _score_documentation(self, analysis: RepositoryAnalysis) -> float:
        """Score documentation quality (20% weight)"""
        score = 0.0
        
        # Base documentation score
        if analysis.has_documentation:
            score += 0.4
        
        # Quality multiplier
        score += analysis.documentation_quality * 0.6
        
        # Pattern bonuses
        if "documentation" in analysis.detected_patterns:
            score += 0.1
        if "testing" in analysis.detected_patterns:
            score += 0.05
        
        return min(1.0, score)
    
    def _score_simplicity(self, analysis: RepositoryAnalysis) -> float:
        """Score simplicity and modularity (20% weight)"""
        score = 0.0
        
        # Code complexity (lower is better, so invert)
        complexity_score = 1.0 - analysis.code_complexity
        score += complexity_score * 0.5
        
        # Modularity score
        score += analysis.modularity_score * 0.5
        
        # Pattern bonuses for good structure
        good_patterns = ["packaging", "configuration", "testing"]
        pattern_bonus = sum(0.05 for pattern in good_patterns if pattern in analysis.detected_patterns)
        score += min(0.2, pattern_bonus)
        
        return min(1.0, score)
    
    def _score_license(self, metadata: RepositoryMetadata) -> float:
        """Score license compatibility (20% weight)"""
        if not metadata.license:
            return 0.3  # Unknown license gets low score
        
        return self.license_scores.get(metadata.license, 0.5)
    
    def _score_maintenance(self, analysis: RepositoryAnalysis) -> float:
        """Score maintenance activity (10% weight)"""
        return analysis.maintenance_score
    
    def _generate_tags(self, metadata: RepositoryMetadata, analysis: RepositoryAnalysis) -> List[str]:
        """Generate descriptive tags for the repository"""
        tags = []
        
        # Language tag
        if metadata.language:
            tags.append(metadata.language.lower())
        
        # Interface tags
        if analysis.has_cli:
            tags.append("cli")
        if analysis.has_api:
            tags.append("api")
        
        # Framework tags
        for framework in analysis.detected_frameworks:
            # Map frameworks to categories
            for category, frameworks in Config.FRAMEWORK_TAGS.items():
                if framework in frameworks:
                    if category not in tags:
                        tags.append(category)
        
        # Size tags
        if metadata.stars > 10000:
            tags.append("popular")
        elif metadata.stars > 1000:
            tags.append("well-known")
        
        if metadata.size < 1000:  # KB
            tags.append("lightweight")
        elif metadata.size > 50000:  # KB
            tags.append("large")
        
        # Activity tags (use UTC for consistent comparison)
        now = datetime.now(timezone.utc)
        updated = metadata.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        days_since_update = (now - updated).days
        if days_since_update <= 30:
            tags.append("active")
        elif days_since_update > 365:
            tags.append("inactive")
        
        # Pattern tags
        tags.extend(analysis.detected_patterns)
        
        # License tag
        if metadata.license:
            license_category = self._get_license_category(metadata.license)
            if license_category:
                tags.append(license_category)
        
        # Remove duplicates and sort
        return sorted(list(set(tags)))
    
    def _get_license_category(self, license_name: str) -> str:
        """Get license category for tagging"""
        permissive = ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unlicense"]
        copyleft = ["GPL-3.0", "GPL-2.0", "AGPL-3.0"]
        weak_copyleft = ["LGPL-3.0", "LGPL-2.1", "MPL-2.0"]
        
        if license_name in permissive:
            return "permissive"
        elif license_name in copyleft:
            return "copyleft"
        elif license_name in weak_copyleft:
            return "weak-copyleft"
        else:
            return "other-license"
    
    def _categorize_agent_friendliness(self, total_score: float) -> str:
        """Categorize repository based on total score"""
        if total_score >= 80:
            return "high"
        elif total_score >= 60:
            return "medium"
        else:
            return "low"
    
    def filter_by_score(self, repositories: List[Dict[str, Any]], min_score: float = 50.0) -> List[Dict[str, Any]]:
        """Filter repositories by minimum score"""
        return [repo for repo in repositories if repo.get("score", 0) >= min_score]
    
    def sort_by_score(self, repositories: List[Dict[str, Any]], reverse: bool = True) -> List[Dict[str, Any]]:
        """Sort repositories by score"""
        return sorted(repositories, key=lambda x: x.get("score", 0), reverse=reverse)
    
    def get_top_repositories(self, repositories: List[Dict[str, Any]], limit: int = 100) -> List[Dict[str, Any]]:
        """Get top N repositories by score"""
        sorted_repos = self.sort_by_score(repositories)
        return sorted_repos[:limit]
    
    def get_statistics(self, repositories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get scoring statistics"""
        if not repositories:
            return {}
        
        scores = [repo.get("score", 0) for repo in repositories]
        
        return {
            "total_repositories": len(repositories),
            "average_score": sum(scores) / len(scores),
            "median_score": sorted(scores)[len(scores) // 2],
            "min_score": min(scores),
            "max_score": max(scores),
            "high_quality_count": len([s for s in scores if s >= 80]),
            "medium_quality_count": len([s for s in scores if 60 <= s < 80]),
            "low_quality_count": len([s for s in scores if s < 60])
        }