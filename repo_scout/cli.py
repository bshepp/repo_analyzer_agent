"""
Command Line Interface for Repository Scout
"""

import argparse
import asyncio
import json
import csv
import logging
import sys
from typing import List, Dict, Any, Optional
from pathlib import Path

from .scout import RepositoryScout
from .models import ScoutedRepository
from .config import Config, get_effective_token


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )


def export_to_jsonl(repositories: List[ScoutedRepository], output_file: str):
    """Export repositories to JSONL format (one compact JSON object per line)."""
    with open(output_file, 'w', encoding='utf-8') as f:
        for repo in repositories:
            f.write(json.dumps(repo.to_dict(), ensure_ascii=False) + '\n')


def export_to_json(repositories: List[ScoutedRepository], output_file: str):
    """Export repositories to JSON format"""
    data = [repo.to_dict() for repo in repositories]
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def export_to_csv(repositories: List[ScoutedRepository], output_file: str):
    """Export repositories to CSV format"""
    if not repositories:
        return
    
    # Use summary format for CSV
    data = [repo.to_summary_dict() for repo in repositories]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)


def export_repositories(repositories: List[ScoutedRepository], output_file: str, format: str):
    """Export repositories in specified format"""
    if not repositories:
        print("No repositories to export")
        return
    
    if format == 'jsonl':
        export_to_jsonl(repositories, output_file)
    elif format == 'json':
        export_to_json(repositories, output_file)
    elif format == 'csv':
        export_to_csv(repositories, output_file)
    else:
        raise ValueError(f"Unsupported format: {format}")
    
    print(f"Exported {len(repositories)} repositories to {output_file}")


def print_summary_statistics(stats: Dict[str, Any]):
    """Print summary statistics"""
    print("\n" + "="*60)
    print("REPOSITORY SCOUT SUMMARY")
    print("="*60)
    
    print(f"Total Repositories Analyzed: {stats.get('total_repositories', 0)}")
    print(f"Average Score: {stats.get('average_score', 0):.1f}")
    print(f"Median Score: {stats.get('median_score', 0):.1f}")
    print(f"Score Range: {stats.get('min_score', 0):.1f} - {stats.get('max_score', 0):.1f}")
    
    print("\nAgent Friendliness Distribution:")
    friendliness = stats.get('agent_friendliness_distribution', {})
    print(f"  High: {friendliness.get('high', 0)}")
    print(f"  Medium: {friendliness.get('medium', 0)}")
    print(f"  Low: {friendliness.get('low', 0)}")
    
    print("\nTop Languages:")
    for lang, count in stats.get('top_languages', [])[:5]:
        print(f"  {lang}: {count}")
    
    print("\nTop Tags:")
    for tag, count in stats.get('top_tags', [])[:10]:
        print(f"  {tag}: {count}")


async def search_and_scout(args) -> List[ScoutedRepository]:
    """Search and scout repositories"""
    token = args.token or get_effective_token()
    async with RepositoryScout(token) as scout:
        repositories = []
        
        print(f"Searching repositories with query: {args.query}")
        if args.max_repositories:
            print(f"Maximum repositories to analyze: {args.max_repositories}")
        
        # Get rate limit status
        rate_limit = await scout.get_rate_limit_status()
        if rate_limit:
            core_limit = rate_limit.get('rate', {})
            print(f"GitHub API Rate Limit: {core_limit.get('remaining', 0)}/{core_limit.get('limit', 0)}")
        
        async for repo in scout.scout_repositories(
            query=args.query,
            max_repositories=args.max_repositories or 100,
            min_stars=args.min_stars,
            languages=args.languages,
            exclude_archived=not args.include_archived,
            min_score=args.min_score
        ):
            repositories.append(repo)
            
            # Print progress
            if len(repositories) % 10 == 0:
                print(f"Analyzed {len(repositories)} repositories...")
            
            # Print repository info
            if args.verbose:
                print(f"  {repo.metadata.full_name}: {repo.score.total_score:.1f} ({repo.score.agent_friendliness})")
        
        return repositories


async def scout_specific_repos(args) -> List[ScoutedRepository]:
    """Scout specific repositories"""
    repo_specs = []
    
    for repo_spec in args.repositories:
        if '/' in repo_spec:
            owner, repo = repo_spec.split('/', 1)
            repo_specs.append({"owner": owner, "repo": repo})
        else:
            print(f"Invalid repository format: {repo_spec}. Use owner/repo format.")
            continue
    
    if not repo_specs:
        return []
    
    token = args.token or get_effective_token()
    async with RepositoryScout(token) as scout:
        print(f"Scouting {len(repo_specs)} specific repositories...")
        
        repositories = await scout.batch_scout_repositories(repo_specs, max_concurrent=5)
        
        for repo in repositories:
            print(f"  {repo.metadata.full_name}: {repo.score.total_score:.1f} ({repo.score.agent_friendliness})")
        
        return repositories


async def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Repository Scout - AI Agent-Friendly Repository Discovery Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --query "stars:>100 language:python"
  %(prog)s --query "machine learning" --min-stars 500 --max-repositories 50
  %(prog)s --repositories numpy/numpy pandas-dev/pandas
  %(prog)s --query "cli tool" --output results.jsonl --format jsonl
        """
    )
    
    # Search options
    search_group = parser.add_argument_group('Search Options')
    search_group.add_argument(
        '--query', '-q',
        type=str,
        help=f'GitHub search query (default: "{Config.DEFAULT_SEARCH_QUERY}")'
    )
    search_group.add_argument(
        '--max-repositories', '-m',
        type=int,
        help='Maximum number of repositories to analyze (default: 100)'
    )
    search_group.add_argument(
        '--min-stars', '-s',
        type=int,
        help='Minimum number of stars (default: from config)'
    )
    search_group.add_argument(
        '--languages', '-l',
        type=str,
        nargs='+',
        help='Programming languages to filter by'
    )
    search_group.add_argument(
        '--include-archived',
        action='store_true',
        help='Include archived repositories'
    )
    search_group.add_argument(
        '--min-score',
        type=float,
        default=50.0,
        help='Minimum agent-friendliness score (default: 50.0)'
    )
    
    # Specific repositories
    parser.add_argument(
        '--repositories', '-r',
        type=str,
        nargs='+',
        help='Specific repositories to scout (format: owner/repo)'
    )
    
    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        '--output', '-o',
        type=str,
        help='Output file path'
    )
    output_group.add_argument(
        '--format', '-f',
        type=str,
        choices=Config.OUTPUT_FORMATS,
        default=Config.DEFAULT_OUTPUT_FORMAT,
        help=f'Output format (default: {Config.DEFAULT_OUTPUT_FORMAT})'
    )
    output_group.add_argument(
        '--no-summary',
        action='store_true',
        help='Skip summary statistics'
    )
    
    # Configuration
    config_group = parser.add_argument_group('Configuration')
    config_group.add_argument(
        '--token', '-t',
        type=str,
        help='GitHub API token (or set GITHUB_TOKEN; or use `gh auth login` and scout will use it)'
    )
    config_group.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Validate arguments
    if not args.query and not args.repositories:
        args.query = Config.DEFAULT_SEARCH_QUERY
    
    if args.query and args.repositories:
        print("Error: Cannot use both --query and --repositories options")
        sys.exit(1)
    
    # Check for GitHub token (env, --token, or gh auth token)
    effective_token = args.token or get_effective_token()
    if not effective_token:
        print("Warning: No GitHub token. Set GITHUB_TOKEN, use --token, or run `gh auth login`.")
        print("Rate limits will be severely restricted without authentication.")
    
    try:
        # Scout repositories
        if args.repositories:
            repositories = await scout_specific_repos(args)
        else:
            repositories = await search_and_scout(args)
        
        if not repositories:
            print("No repositories found matching criteria")
            return
        
        # Export results
        if args.output:
            export_repositories(repositories, args.output, args.format)
        else:
            # Print to stdout (ensure_ascii=True for Windows console compatibility)
            if args.format == 'jsonl':
                for repo in repositories:
                    print(json.dumps(repo.to_dict(), ensure_ascii=True))
            elif args.format == 'json':
                data = [repo.to_dict() for repo in repositories]
                print(json.dumps(data, indent=2, ensure_ascii=True))
            elif args.format == 'csv':
                print("CSV format requires --output option")
                return
        
        # Print summary statistics
        if not args.no_summary:
            async with RepositoryScout(effective_token) as scout:
                stats = scout.get_summary_statistics(repositories)
                print_summary_statistics(stats)
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())