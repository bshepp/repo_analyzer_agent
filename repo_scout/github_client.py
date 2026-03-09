"""
GitHub API client with rate limiting and caching
"""

import asyncio
import aiohttp
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, AsyncIterator
from dataclasses import dataclass
import logging
import json
import base64

from .config import Config
from .models import RepositoryMetadata


logger = logging.getLogger(__name__)


@dataclass
class RateLimitInfo:
    """GitHub API rate limit information"""
    limit: int
    remaining: int
    reset_at: datetime
    used: int
    
    @property
    def seconds_until_reset(self) -> int:
        """Seconds until rate limit resets."""
        now = datetime.now(timezone.utc)
        reset = self.reset_at if self.reset_at.tzinfo else self.reset_at.replace(tzinfo=timezone.utc)
        return max(0, int((reset - now).total_seconds()))


class GitHubClient:
    """Async GitHub API client with rate limiting"""
    
    def __init__(self, token: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None):
        self.token = token or Config.GITHUB_TOKEN
        self.session = session
        self.base_url = Config.GITHUB_API_BASE_URL
        self.rate_limit_info: Optional[RateLimitInfo] = None
        self._own_session = session is None
        
        if not self.token:
            logger.warning("No GitHub token provided. Rate limits will be severely restricted.")
    
    async def __aenter__(self):
        if self.session is None:
            self.session = aiohttp.ClientSession(
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._own_session and self.session:
            await self.session.close()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for GitHub API requests"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": Config.get_user_agent()
        }
        
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        
        return headers
    
    async def _update_rate_limit_info(self, response: aiohttp.ClientResponse) -> None:
        """Update rate limit information from response headers"""
        if "X-RateLimit-Limit" in response.headers:
            self.rate_limit_info = RateLimitInfo(
                limit=int(response.headers["X-RateLimit-Limit"]),
                remaining=int(response.headers["X-RateLimit-Remaining"]),
                reset_at=datetime.fromtimestamp(int(response.headers["X-RateLimit-Reset"])),
                used=int(response.headers["X-RateLimit-Used"])
            )
    
    async def _check_rate_limit(self) -> None:
        """Check if we should wait for rate limit reset"""
        if not self.rate_limit_info:
            return
        
        if self.rate_limit_info.remaining <= Config.GITHUB_RATE_LIMIT_BUFFER:
            wait_time = self.rate_limit_info.seconds_until_reset + 1
            logger.warning(f"Rate limit approaching. Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
    
    async def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make a rate-limited request to GitHub API"""
        await self._check_rate_limit()
        
        if not self.session:
            raise RuntimeError("Client not initialized. Use async with statement.")
        
        full_url = f"{self.base_url}/{url.lstrip('/')}"
        
        try:
            async with self.session.request(method, full_url, **kwargs) as response:
                await self._update_rate_limit_info(response)
                
                if response.status == 403 and "rate limit" in response.headers.get("X-RateLimit-Remaining", ""):
                    logger.error("Rate limit exceeded")
                    raise Exception("GitHub API rate limit exceeded")
                
                if response.status == 404:
                    return {}
                
                response.raise_for_status()
                return await response.json()
        
        except aiohttp.ClientError as e:
            logger.error(f"GitHub API request failed: {e}")
            raise
    
    async def search_repositories(self, query: str, per_page: int = 100, max_pages: int = 10) -> AsyncIterator[Dict[str, Any]]:
        """Search repositories using GitHub API"""
        page = 1
        
        while page <= max_pages:
            params = {
                "q": query,
                "per_page": per_page,
                "page": page,
                "sort": "stars",
                "order": "desc"
            }
            
            try:
                result = await self._make_request("GET", "/search/repositories", params=params)
                
                if not result or "items" not in result:
                    break
                
                items = result["items"]
                if not items:
                    break
                
                for item in items:
                    yield item
                
                # Check if we have more pages
                if len(items) < per_page:
                    break
                
                page += 1
                
            except Exception as e:
                logger.error(f"Error searching repositories: {e}")
                break
    
    async def get_repository(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Get detailed repository information"""
        try:
            return await self._make_request("GET", f"/repos/{owner}/{repo}")
        except Exception as e:
            logger.error(f"Error fetching repository {owner}/{repo}: {e}")
            return None
    
    async def get_repository_contents(self, owner: str, repo: str, path: str = "", ref: str = None) -> List[Dict[str, Any]]:
        """Get repository contents (files/directories)"""
        try:
            params = {}
            if ref:
                params["ref"] = ref
            
            result = await self._make_request("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params)
            
            if isinstance(result, dict) and "type" in result:
                return [result]
            elif isinstance(result, list):
                return result
            else:
                return []
        
        except Exception as e:
            logger.error(f"Error fetching contents for {owner}/{repo}/{path}: {e}")
            return []
    
    async def get_file_content(self, owner: str, repo: str, path: str, ref: str = None) -> Optional[str]:
        """Get file content as string"""
        try:
            params = {}
            if ref:
                params["ref"] = ref
            
            result = await self._make_request("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params)
            
            if result and result.get("type") == "file" and result.get("encoding") == "base64":
                content = base64.b64decode(result["content"]).decode("utf-8", errors="ignore")
                return content
            
            return None
        
        except Exception as e:
            logger.error(f"Error fetching file {owner}/{repo}/{path}: {e}")
            return None
    
    async def get_languages(self, owner: str, repo: str) -> Dict[str, int]:
        """Get repository language statistics"""
        try:
            return await self._make_request("GET", f"/repos/{owner}/{repo}/languages")
        except Exception as e:
            logger.error(f"Error fetching languages for {owner}/{repo}: {e}")
            return {}
    
    @staticmethod
    def parse_repository_metadata(repo_data: Dict[str, Any]) -> RepositoryMetadata:
        """Parse GitHub API response into RepositoryMetadata"""
        return RepositoryMetadata(
            url=repo_data["html_url"],
            name=repo_data["name"],
            full_name=repo_data["full_name"],
            owner=repo_data["owner"]["login"],
            description=repo_data.get("description"),
            language=repo_data.get("language"),
            stars=repo_data["stargazers_count"],
            forks=repo_data["forks_count"],
            issues=repo_data["open_issues_count"],
            size=repo_data["size"],
            created_at=datetime.fromisoformat(repo_data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(repo_data["updated_at"].replace("Z", "+00:00")),
            pushed_at=datetime.fromisoformat(repo_data["pushed_at"].replace("Z", "+00:00")),
            license=repo_data.get("license", {}).get("spdx_id") if repo_data.get("license") else None,
            topics=repo_data.get("topics", []),
            has_wiki=repo_data.get("has_wiki", False),
            has_pages=repo_data.get("has_pages", False),
            archived=repo_data.get("archived", False),
            disabled=repo_data.get("disabled", False),
            private=repo_data.get("private", False),
            default_branch=repo_data.get("default_branch", "main")
        )
    
    async def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        try:
            return await self._make_request("GET", "/rate_limit")
        except Exception as e:
            logger.error(f"Error fetching rate limit status: {e}")
            return {}