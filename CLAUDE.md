# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**MCP Scout** — async Python CLI that crawls GitHub, detects which repos are real Model Context Protocol servers, and scores them on how usable they are as MCP integrations.

This is a pivot of an earlier "Repository Scout" (generic AI-agent repo discovery). When working in here, treat the MCP focus as the load-bearing premise: scoring, detection, and output all assume the target is "MCP server quality."

## Development Commands

```bash
# Install in development mode (includes pytest, black, ruff)
pip install -e ".[dev]"

# Run the main CLI tool
python scout.py --help
python scout.py --query "topic:mcp language:python" --max-repositories 20

# Alternative entry points
python -m mcp_scout.cli --help
mcp-scout --help  # If installed via pip install -e .

# Tests / lint / format
pytest
ruff check mcp_scout tests
black mcp_scout tests
```

## Architecture Overview

The codebase follows a modular, async-first architecture:

1. **mcp_scout/scout.py** — `MCPScout` orchestrator (also aliased as `RepositoryScout` for back-compat). Pipelines search → analyze → score → emit.
2. **mcp_scout/github_client.py** — Async GitHub API client with rate-limit handling.
3. **mcp_scout/analyzer.py** — `RepositoryAnalyzer` detects MCP server signals across manifests, code, README, and transports.
4. **mcp_scout/scorer.py** — `RepositoryScorer` produces the five-component weighted score and tags.
5. **mcp_scout/models.py** — Dataclasses: `RepositoryMetadata`, `RepositoryAnalysis` (MCP-specific fields), `RepositoryScore`, `ScoutedRepository`.
6. **mcp_scout/mcp_config_gen.py** — Generates `claude_desktop_config.json` snippets per scouted server.
7. **mcp_scout/cli.py** — CLI surface (argparse), export functions for JSONL/JSON/CSV plus merged install config.
8. **mcp_scout/config.py** — All patterns, weights, SDK lists, transport signals.

### Data Flow

```
GitHub Search → Repository Analysis → Scoring → (optional install snippet) → Export
     ↑              ↑                   ↑                                       ↑
GitHubClient  RepositoryAnalyzer   RepositoryScorer                            CLI
```

### Scoring System (in `config.py`)

The tool evaluates repositories on 5 weighted criteria:

| Metric | Weight | Source |
|---|---|---|
| **MCP compliance** | 40% | `mcp_compliance_score` — SDK + code + transports + signal count |
| **Tool richness** | 20% | `tool_richness_score` — tools + 0.5·(resources + prompts) |
| **Install ergonomics** | 15% | `install_ergonomics_score` — install snippet + doc quality |
| **License** | 15% | `license_score` — permissive licenses scored highest |
| **Maintenance** | 10% | `maintenance_score` — recency of last update |

A repo is "an MCP server" only when at least 2 of {manifest signal, code signal, ≥1 tool, README signal} are present (`RepositoryAnalyzer._is_mcp_server`). Non-MCP repos are always categorized `low` regardless of total.

## Key Design Patterns

### Async/Await Architecture
- All API calls and I/O operations use async/await
- Concurrent repository processing with semaphore-based rate limiting (`batch_scout_repositories`)
- Async context managers for resource management

### Data Models
- `@dataclass` for structured data
- `to_dict()` / `to_json()` / `to_summary_dict()` methods for serialization
- `ScoutedRepository.install_config` carries the generated Claude Desktop snippet

### Configuration
- **Token resolution**: `get_effective_token()` in `config.py` tries, in order: `--token` arg, `GITHUB_TOKEN` env, then `gh auth token` (if GitHub CLI is installed and logged in).
- All pattern lists (`MCP_CODE_PATTERNS`, `TRANSPORT_PATTERNS`, etc.) live in `config.py` — extend there rather than scattering literals.

## Entry Points

- **scout.py** — Top-level CLI shim, calls `mcp_scout.cli:main`
- **mcp_scout.cli:main** — Async main entry point
- **mcp-scout** — Console script (defined in `pyproject.toml` [project.scripts])

## Dependencies

- **aiohttp** — Async HTTP client for GitHub API
- **typing-extensions** — Enhanced type hints

See `pyproject.toml` for optional dev deps (pytest, black, ruff).

## Development Notes

- The async generator (`scout_repositories`) yields one repo at a time — memory stays flat even on large crawls.
- GitHub API rate limiting handled automatically; budget reserved via `GITHUB_RATE_LIMIT_BUFFER`.
- To add a new MCP SDK signal: extend `Config.MCP_SDK_DEPS` and (if relevant) `Config.MCP_CODE_PATTERNS`. No analyzer change needed.
- To add a brand-new language family: also add the manifest filename(s) to `Config.MANIFEST_LANGUAGE_MAP` so per-language scoping in `_scan_manifests` picks them up.
- To add a new transport: extend `Config.TRANSPORT_PATTERNS` and add a tag in scorer if you want it surfaced.
- Code recursion in `_scan_code` walks two levels deep through directories in the local `_CODE_SUBDIRS` set in `analyzer.py`; extend that set if MCP servers in a new ecosystem put their code somewhere unexpected.
- `RepositoryScout` is kept as an alias of `MCPScout` for any external callers that still import the old name.
