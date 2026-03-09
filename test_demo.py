#!/usr/bin/env python3
"""
Demo script for Repository Scout
"""

import asyncio
import json
from repo_scout.scout import RepositoryScout
from repo_scout.config import Config

async def demo_scout():
    """Demo the Repository Scout functionality"""
    
    # Mock a simple repository analysis without hitting the API
    print("Repository Scout Demo")
    print("="*50)
    
    # Show configuration
    print(f"Default search query: {Config.DEFAULT_SEARCH_QUERY}")
    print(f"Scoring weights: {Config.SCORING_WEIGHTS}")
    print(f"Supported output formats: {Config.OUTPUT_FORMATS}")
    
    # Show CLI patterns
    print(f"\nCLI patterns detected: {Config.CLI_PATTERNS[:3]}...")
    print(f"API patterns detected: {Config.API_PATTERNS[:3]}...")
    
    # Show license scoring
    print(f"\nLicense scoring examples:")
    for license, score in list(Config.LICENSE_SCORES.items())[:5]:
        print(f"  {license}: {score}")
    
    # Show framework tags
    print(f"\nFramework categories:")
    for category, frameworks in list(Config.FRAMEWORK_TAGS.items())[:5]:
        print(f"  {category}: {frameworks[:3]}...")
    
    print("\n" + "="*50)
    print("Repository Scout is ready to use!")
    print("Example usage:")
    print("  python scout.py --query 'stars:>100 language:python' --max-repositories 5")
    print("  python scout.py --repositories numpy/numpy pandas-dev/pandas")
    print("  python scout.py --query 'cli tool' --output results.jsonl")
    print("\nNote: Set GITHUB_TOKEN environment variable for higher rate limits")

if __name__ == "__main__":
    asyncio.run(demo_scout())