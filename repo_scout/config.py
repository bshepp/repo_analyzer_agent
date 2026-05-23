"""
Configuration settings for Repository Scout
"""

import os
import subprocess
from typing import Dict, List, Optional


def get_effective_token() -> Optional[str]:
    """Return GitHub token: GITHUB_TOKEN env, then `gh auth token`, else None."""
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


class Config:
    """Configuration class for Repository Scout"""

    # GitHub API settings (resolved at runtime via get_effective_token() when needed)
    GITHUB_TOKEN: Optional[str] = os.getenv("GITHUB_TOKEN")
    GITHUB_API_BASE_URL: str = "https://api.github.com"
    GITHUB_RATE_LIMIT_BUFFER: int = 100  # Keep this many requests in reserve
    
    # Search settings
    DEFAULT_SEARCH_QUERY: str = "stars:>100 language:python"
    MAX_REPOSITORIES_PER_SEARCH: int = 1000
    MIN_STARS_THRESHOLD: int = 10
    
    # Analysis settings
    README_MAX_LENGTH: int = 50000  # Max README length to analyze
    CODE_SAMPLE_SIZE: int = 10  # Number of code files to analyze
    
    # Scoring weights (should sum to 1.0)
    SCORING_WEIGHTS: Dict[str, float] = {
        "cli_api": 0.30,
        "documentation": 0.20,
        "simplicity": 0.20,
        "license": 0.20,
        "maintenance": 0.10
    }
    
    # License scoring
    LICENSE_SCORES: Dict[str, float] = {
        "MIT": 1.0,
        "Apache-2.0": 1.0,
        "BSD-2-Clause": 1.0,
        "BSD-3-Clause": 1.0,
        "ISC": 1.0,
        "Unlicense": 1.0,
        "GPL-3.0": 0.7,
        "GPL-2.0": 0.7,
        "LGPL-3.0": 0.8,
        "LGPL-2.1": 0.8,
        "MPL-2.0": 0.8,
        "AGPL-3.0": 0.5,
        "EPL-2.0": 0.7,
        "CC0-1.0": 0.9
    }
    
    # Framework detection patterns
    CLI_PATTERNS: List[str] = [
        "argparse",
        "click",
        "typer",
        "fire",
        "docopt",
        "sys.argv",
        "if __name__ == '__main__':",
        "main()",
        "parser.add_argument",
        "click.command",
        "typer.run"
    ]
    
    API_PATTERNS: List[str] = [
        "flask",
        "fastapi",
        "django",
        "tornado",
        "bottle",
        "cherrypy",
        "pyramid",
        "falcon",
        "hug",
        "sanic",
        "app.route",
        "router.get",
        "router.post",
        "@app.route",
        "from flask import",
        "from fastapi import",
        "from django import"
    ]
    
    DOCUMENTATION_INDICATORS: List[str] = [
        "README.md",
        "README.rst",
        "README.txt",
        "docs/",
        "doc/",
        "documentation/",
        "sphinx",
        "mkdocs",
        "gitbook",
        "docusaurus"
    ]
    
    # Tags for categorization
    FRAMEWORK_TAGS: Dict[str, List[str]] = {
        "web": ["flask", "django", "fastapi", "tornado", "bottle"],
        "cli": ["argparse", "click", "typer", "fire", "docopt"],
        "data": ["pandas", "numpy", "scipy", "scikit-learn", "matplotlib"],
        "ml": ["tensorflow", "pytorch", "sklearn", "keras", "transformers"],
        "api": ["requests", "httpx", "aiohttp", "urllib3"],
        "database": ["sqlalchemy", "psycopg2", "pymongo", "redis"],
        "testing": ["pytest", "unittest", "nose", "coverage"],
        "devops": ["docker", "kubernetes", "ansible", "terraform"],
        "security": ["cryptography", "hashlib", "ssl", "oauth"],
        "image": ["pillow", "opencv", "imageio", "skimage"],
        "text": ["nltk", "spacy", "textblob", "regex"],
        "config": ["configparser", "yaml", "toml", "json"],
        "logging": ["logging", "loguru", "structlog"]
    }
    
    # Output settings
    DEFAULT_OUTPUT_FORMAT: str = "jsonl"
    OUTPUT_FORMATS: List[str] = ["jsonl", "json", "csv"]

    @classmethod
    def validate(cls) -> bool:
        """Validate configuration settings. Returns False only for invalid weights."""
        if sum(cls.SCORING_WEIGHTS.values()) != 1.0:
            return False
        return True
    
    @classmethod
    def get_user_agent(cls) -> str:
        """Get user agent string for API requests"""
        return "Repository-Scout/0.1.0 (https://github.com/bshepp/repo_analyzer_agent)"