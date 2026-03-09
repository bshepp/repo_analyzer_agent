"""
Main Repository Scout orchestrator
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime, timezone

from .config import Config
from .models import RepositoryMetadata, ScoutedRepository
from .github_client import GitHubClient
from .analyzer import RepositoryAnalyzer
from .scorer import RepositoryScorer


logger = logging.getLogger(__name__)


class RepositoryScout:
    """Main orchestrator for repository discovery and analysis"""
    
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token or Config.GITHUB_TOKEN
        self.github_client = None
        self.analyzer = None
        self.scorer = RepositoryScorer()
        
        # Validate configuration
        if not Config.validate():
            logger.warning("Configuration validation failed")
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.github_client = GitHubClient(self.github_token)
        await self.github_client.__aenter__()
        self.analyzer = RepositoryAnalyzer(self.github_client)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.github_client:
            await self.github_client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def scout_repositories(
        self,
        query: str = None,
        max_repositories: int = 100,
        min_stars: int = None,
        languages: List[str] = None,
        exclude_archived: bool = True,
        min_score: float = 50.0
    ) -> AsyncIterator[ScoutedRepository]:
        """
        Scout repositories based on criteria
        
        Args:
            query: GitHub search query
            max_repositories: Maximum number of repositories to analyze
            min_stars: Minimum star count
            languages: List of programming languages to filter by
            exclude_archived: Whether to exclude archived repositories
            min_score: Minimum agent-friendliness score
        """
        if not self.github_client or not self.analyzer:
            raise RuntimeError("Scout not initialized. Use async with statement.")
        
        # Build search query
        search_query = self._build_search_query(query, min_stars, languages, exclude_archived)
        logger.info(f"Searching repositories with query: {search_query}")
        
        analyzed_count = 0
        
        async for repo_data in self.github_client.search_repositories(
            search_query,
            per_page=100,
            max_pages=max_repositories // 100 + 1
        ):
            if analyzed_count >= max_repositories:
                break
            
            try:
                # Parse repository metadata
                metadata = GitHubClient.parse_repository_metadata(repo_data)
                
                # Skip if doesn't meet criteria
                if not self._meets_criteria(metadata, min_stars, exclude_archived):
                    continue
                
                # Analyze repository
                analysis = await self.analyzer.analyze_repository(metadata)
                
                # Score repository
                score = self.scorer.score_repository(metadata, analysis)
                
                # Filter by minimum score
                if score.total_score < min_score:
                    logger.debug(f"Skipping {metadata.full_name} (score: {score.total_score})")
                    continue
                
                # Create scouted repository
                scouted_repo = ScoutedRepository(
                    metadata=metadata,
                    analysis=analysis,
                    score=score,
                    analyzed_at=datetime.now(timezone.utc),
                )
                
                logger.info(f"Scouted {metadata.full_name} - Score: {score.total_score}")
                yield scouted_repo
                
                analyzed_count += 1
                
            except (KeyboardInterrupt, asyncio.CancelledError):
                raise
            except Exception as e:
                logger.error(f"Error analyzing repository {repo_data.get('full_name', 'unknown')}: {e}")
                continue
    
    async def scout_single_repository(self, owner: str, repo: str) -> Optional[ScoutedRepository]:
        """Scout a single repository by owner/repo"""
        if not self.github_client or not self.analyzer:
            raise RuntimeError("Scout not initialized. Use async with statement.")
        
        try:
            # Get repository data
            repo_data = await self.github_client.get_repository(owner, repo)
            if not repo_data:
                logger.error(f"Repository {owner}/{repo} not found")
                return None
            
            # Parse metadata
            metadata = GitHubClient.parse_repository_metadata(repo_data)
            
            # Analyze repository
            analysis = await self.analyzer.analyze_repository(metadata)
            
            # Score repository
            score = self.scorer.score_repository(metadata, analysis)
            
            # Create scouted repository
            scouted_repo = ScoutedRepository(
                metadata=metadata,
                analysis=analysis,
                score=score,
                analyzed_at=datetime.now(timezone.utc),
            )
            
            logger.info(f"Scouted {metadata.full_name} - Score: {score.total_score}")
            return scouted_repo
            
        except Exception as e:
            logger.error(f"Error scouting repository {owner}/{repo}: {e}")
            return None
    
    async def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get GitHub API rate limit status"""
        if not self.github_client:
            raise RuntimeError("Scout not initialized. Use async with statement.")
        
        return await self.github_client.get_rate_limit_status()
    
    def _build_search_query(
        self,
        query: Optional[str],
        min_stars: Optional[int],
        languages: Optional[List[str]],
        exclude_archived: bool
    ) -> str:
        """Build GitHub search query"""
        parts = []
        
        if query:
            parts.append(query)
        else:
            parts.append(Config.DEFAULT_SEARCH_QUERY)
        
        if min_stars is not None:
            parts.append(f"stars:>{min_stars}")
        elif Config.MIN_STARS_THRESHOLD > 0:
            parts.append(f"stars:>{Config.MIN_STARS_THRESHOLD}")
        
        if languages:
            for lang in languages:
                parts.append(f"language:{lang}")
        
        if exclude_archived:
            parts.append("archived:false")
        
        return " ".join(parts)
    
    def _meets_criteria(
        self,
        metadata: RepositoryMetadata,
        min_stars: Optional[int],
        exclude_archived: bool
    ) -> bool:
        """Check if repository meets filtering criteria"""
        if exclude_archived and metadata.archived:
            return False
        
        if metadata.disabled:
            return False
        
        if min_stars is not None and metadata.stars < min_stars:
            return False
        
        return True
    
    async def batch_scout_repositories(
        self,
        repo_specs: List[Dict[str, str]],
        max_concurrent: int = 5
    ) -> List[ScoutedRepository]:
        """
        Scout multiple specific repositories concurrently
        
        Args:
            repo_specs: List of dicts with 'owner' and 'repo' keys
            max_concurrent: Maximum concurrent requests
        """
        if not self.github_client or not self.analyzer:
            raise RuntimeError("Scout not initialized. Use async with statement.")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scout_one(repo_spec: Dict[str, str]) -> Optional[ScoutedRepository]:
            async with semaphore:
                return await self.scout_single_repository(
                    repo_spec["owner"], repo_spec["repo"]
                )
        
        # Execute all scouts concurrently
        tasks = [scout_one(spec) for spec in repo_specs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None results and exceptions (re-raise cancellation so caller can exit)
        scouted_repos = []
        for result in results:
            if isinstance(result, ScoutedRepository):
                scouted_repos.append(result)
            elif isinstance(result, BaseException):
                if isinstance(result, (KeyboardInterrupt, asyncio.CancelledError)):
                    raise result
                logger.error(f"Error in batch scouting: {result}")
        
        return scouted_repos
    
    def get_summary_statistics(self, scouted_repos: List[ScoutedRepository]) -> Dict[str, Any]:
        """Get summary statistics for scouted repositories"""
        if not scouted_repos:
            return {"total_repositories": 0}
        
        repo_dicts = [repo.to_summary_dict() for repo in scouted_repos]
        stats = self.scorer.get_statistics(repo_dicts)
        
        # Add additional statistics
        languages = [repo.metadata.language for repo in scouted_repos if repo.metadata.language]
        language_counts = {}
        for lang in languages:
            language_counts[lang] = language_counts.get(lang, 0) + 1
        
        tags = []
        for repo in scouted_repos:
            tags.extend(repo.score.tags)
        
        tag_counts = {}
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        stats.update({
            "top_languages": sorted(language_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            "top_tags": sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:15],
            "agent_friendliness_distribution": {
                "high": len([r for r in scouted_repos if r.score.agent_friendliness == "high"]),
                "medium": len([r for r in scouted_repos if r.score.agent_friendliness == "medium"]),
                "low": len([r for r in scouted_repos if r.score.agent_friendliness == "low"])
            }
        })
        
        return stats