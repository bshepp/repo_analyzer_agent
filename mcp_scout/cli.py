"""Command Line Interface for MCP Scout."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import sys
from typing import Any, Dict, List

from .config import Config, get_effective_token
from .models import ScoutedRepository
from .scout import MCPScout


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def export_to_jsonl(repositories: List[ScoutedRepository], output_file: str) -> None:
    """Export to JSONL (one compact JSON object per line)."""
    with open(output_file, "w", encoding="utf-8") as f:
        for repo in repositories:
            f.write(json.dumps(repo.to_dict(), ensure_ascii=False) + "\n")


def export_to_json(repositories: List[ScoutedRepository], output_file: str) -> None:
    data = [r.to_dict() for r in repositories]
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def export_to_csv(repositories: List[ScoutedRepository], output_file: str) -> None:
    if not repositories:
        return
    data = [r.to_summary_dict() for r in repositories]
    # Flatten list fields for CSV friendliness
    for row in data:
        row["tags"] = ",".join(row.get("tags", []) or [])
        row["transports"] = ",".join(row.get("transports", []) or [])
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)


def export_install_configs(repositories: List[ScoutedRepository], output_file: str) -> None:
    """Merge all generated install configs into one Claude Desktop config file."""
    merged: Dict[str, Dict[str, Any]] = {"mcpServers": {}}
    for repo in repositories:
        if not repo.install_config:
            continue
        servers = repo.install_config.get("mcpServers", {})
        for name, entry in servers.items():
            if name.startswith("_"):
                continue
            # Annotate with source URL so the user knows what came from where
            entry = dict(entry)
            entry["_source"] = repo.metadata.url
            merged["mcpServers"][name] = entry
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)


def export_repositories(
    repositories: List[ScoutedRepository], output_file: str, format: str
) -> None:
    if not repositories:
        print("No repositories to export")
        return

    if format == "jsonl":
        export_to_jsonl(repositories, output_file)
    elif format == "json":
        export_to_json(repositories, output_file)
    elif format == "csv":
        export_to_csv(repositories, output_file)
    else:
        raise ValueError(f"Unsupported format: {format}")
    print(f"Exported {len(repositories)} repositories to {output_file}")


def print_summary_statistics(stats: Dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("MCP SCOUT SUMMARY")
    print("=" * 60)

    print(f"Total Repositories Analyzed: {stats.get('total_repositories', 0)}")
    print(f"Average Score: {stats.get('average_score', 0):.1f}")
    print(f"Median Score: {stats.get('median_score', 0):.1f}")
    print(f"Score Range: {stats.get('min_score', 0):.1f} - {stats.get('max_score', 0):.1f}")
    print(f"Total Tools Exposed (sum): {stats.get('total_tools_exposed', 0)}")

    print("\nMCP Readiness Distribution:")
    dist = stats.get("mcp_readiness_distribution", {})
    print(f"  High:   {dist.get('high', 0)}")
    print(f"  Medium: {dist.get('medium', 0)}")
    print(f"  Low:    {dist.get('low', 0)}")

    print("\nTransports:")
    for transport, count in (stats.get("transports") or {}).items():
        print(f"  {transport}: {count}")

    print("\nTop SDK Languages:")
    for lang, count in stats.get("top_sdk_languages", [])[:5]:
        print(f"  {lang}: {count}")

    print("\nTop Tags:")
    for tag, count in stats.get("top_tags", [])[:10]:
        print(f"  {tag}: {count}")


async def search_and_scout(args) -> List[ScoutedRepository]:
    token = args.token or get_effective_token()
    async with MCPScout(token) as scout:
        repositories: List[ScoutedRepository] = []

        print(f"Searching repositories with query: {args.query}")
        if args.max_repositories:
            print(f"Maximum repositories to analyze: {args.max_repositories}")

        rate_limit = await scout.get_rate_limit_status()
        if rate_limit:
            core_limit = rate_limit.get("rate", {})
            print(
                "GitHub API Rate Limit: "
                f"{core_limit.get('remaining', 0)}/{core_limit.get('limit', 0)}"
            )

        async for repo in scout.scout_repositories(
            query=args.query,
            max_repositories=args.max_repositories or 100,
            min_stars=args.min_stars,
            languages=args.languages,
            exclude_archived=not args.include_archived,
            min_score=args.min_score,
            require_mcp=not args.include_non_mcp,
        ):
            repositories.append(repo)
            if len(repositories) % 10 == 0:
                print(f"Analyzed {len(repositories)} repositories...")
            if args.verbose:
                print(
                    f"  {repo.metadata.full_name}: {repo.score.total_score:.1f} "
                    f"({repo.score.mcp_readiness}) — "
                    f"tools={repo.analysis.mcp_tools_count}"
                )

        return repositories


async def scout_specific_repos(args) -> List[ScoutedRepository]:
    repo_specs: List[Dict[str, str]] = []
    for spec in args.repositories:
        if "/" in spec:
            owner, repo = spec.split("/", 1)
            repo_specs.append({"owner": owner, "repo": repo})
        else:
            print(f"Invalid repository format: {spec}. Use owner/repo format.")
            continue

    if not repo_specs:
        return []

    token = args.token or get_effective_token()
    async with MCPScout(token) as scout:
        print(f"Scouting {len(repo_specs)} specific repositories...")
        repositories = await scout.batch_scout_repositories(repo_specs, max_concurrent=5)
        for repo in repositories:
            print(
                f"  {repo.metadata.full_name}: {repo.score.total_score:.1f} "
                f"({repo.score.mcp_readiness}) — "
                f"tools={repo.analysis.mcp_tools_count}"
            )
        return repositories


async def main():
    parser = argparse.ArgumentParser(
        description="MCP Scout — discover and score Model Context Protocol servers on GitHub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                       # default query: topic:mcp ...
  %(prog)s --query "topic:mcp language:python" --max-repositories 50
  %(prog)s --repositories modelcontextprotocol/servers
  %(prog)s --query "topic:mcp" --output results.jsonl --format jsonl
  %(prog)s --query "topic:mcp" --install-config claude_desktop_config.json
        """,
    )

    search_group = parser.add_argument_group("Search Options")
    search_group.add_argument(
        "--query", "-q",
        type=str,
        help=f'GitHub search query (default: "{Config.DEFAULT_SEARCH_QUERY}")',
    )
    search_group.add_argument(
        "--max-repositories", "-m",
        type=int,
        help="Maximum number of repositories to analyze (default: 100)",
    )
    search_group.add_argument(
        "--min-stars", "-s",
        type=int,
        help="Minimum number of stars (default: 0; MCP ecosystem is young)",
    )
    search_group.add_argument(
        "--languages", "-l",
        type=str,
        nargs="+",
        help="Programming languages to filter by",
    )
    search_group.add_argument(
        "--include-archived",
        action="store_true",
        help="Include archived repositories",
    )
    search_group.add_argument(
        "--include-non-mcp",
        action="store_true",
        help="Include repos where MCP server detection was not confident (default: skip)",
    )
    search_group.add_argument(
        "--min-score",
        type=float,
        default=50.0,
        help="Minimum MCP-readiness score (default: 50.0)",
    )

    parser.add_argument(
        "--repositories", "-r",
        type=str,
        nargs="+",
        help="Specific repositories to scout (format: owner/repo)",
    )

    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument(
        "--output", "-o",
        type=str,
        help="Output file path",
    )
    output_group.add_argument(
        "--format", "-f",
        type=str,
        choices=Config.OUTPUT_FORMATS,
        default=Config.DEFAULT_OUTPUT_FORMAT,
        help=f"Output format (default: {Config.DEFAULT_OUTPUT_FORMAT})",
    )
    output_group.add_argument(
        "--install-config",
        type=str,
        help=(
            "Also write a merged claude_desktop_config.json snippet to this path "
            "containing all scouted servers' install templates."
        ),
    )
    output_group.add_argument(
        "--no-summary",
        action="store_true",
        help="Skip summary statistics",
    )

    config_group = parser.add_argument_group("Configuration")
    config_group.add_argument(
        "--token", "-t",
        type=str,
        help="GitHub API token (or set GITHUB_TOKEN; or use `gh auth login` and scout will use it)",
    )
    config_group.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    if not args.query and not args.repositories:
        args.query = Config.DEFAULT_SEARCH_QUERY

    if args.query and args.repositories:
        print("Error: Cannot use both --query and --repositories options")
        sys.exit(1)

    effective_token = args.token or get_effective_token()
    if not effective_token:
        print("Warning: No GitHub token. Set GITHUB_TOKEN, use --token, or run `gh auth login`.")
        print("Rate limits will be severely restricted without authentication.")

    try:
        if args.repositories:
            repositories = await scout_specific_repos(args)
        else:
            repositories = await search_and_scout(args)

        if not repositories:
            print("No repositories found matching criteria")
            return

        if args.output:
            export_repositories(repositories, args.output, args.format)
        else:
            if args.format == "jsonl":
                for repo in repositories:
                    print(json.dumps(repo.to_dict(), ensure_ascii=True))
            elif args.format == "json":
                data = [repo.to_dict() for repo in repositories]
                print(json.dumps(data, indent=2, ensure_ascii=True))
            elif args.format == "csv":
                print("CSV format requires --output option")
                return

        if args.install_config:
            export_install_configs(repositories, args.install_config)
            print(f"Wrote merged install config to {args.install_config}")

        if not args.no_summary:
            async with MCPScout(effective_token) as scout:
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


if __name__ == "__main__":
    asyncio.run(main())
