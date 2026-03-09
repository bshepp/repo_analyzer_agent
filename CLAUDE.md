# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Core Commands
```bash
# Install in development mode (includes pytest, black, ruff)
pip install -e ".[dev]"

# Run the main CLI tool
python scout.py --help
python scout.py --query "machine learning" --max-repositories 20

# Alternative entry points
python -m repo_scout.cli --help
repo-scout --help  # If installed via pip install -e .
```

### Repository Analysis Examples
```bash
# Search with specific criteria
python scout.py --query "stars:>100 language:python" --min-score 60 --output results.jsonl

# Scout specific repositories
python scout.py --repositories numpy/numpy pandas-dev/pandas --format json

# Export results in different formats
python scout.py --query "cli tool" --output results.csv --format csv
```

## Architecture Overview

This is a **Repository Scout** tool that discovers and analyzes GitHub repositories for AI agent compatibility. The codebase follows a modular, async-first architecture:

### Core Components

1. **repo_scout/scout.py** - Main orchestrator class `RepositoryScout` that coordinates the entire analysis pipeline
2. **repo_scout/github_client.py** - Async GitHub API client with rate limiting and error handling
3. **repo_scout/analyzer.py** - `RepositoryAnalyzer` that performs NLP analysis on repository structure and documentation
4. **repo_scout/scorer.py** - `RepositoryScorer` that calculates agent-friendliness scores based on weighted metrics
5. **repo_scout/models.py** - Data models (`RepositoryMetadata`, `RepositoryAnalysis`, `RepositoryScore`, `ScoutedRepository`)
6. **repo_scout/cli.py** - Command-line interface with argparse
7. **repo_scout/config.py** - Configuration management and constants

### Data Flow
```
GitHub Search → Repository Analysis → Scoring → Export
     ↑              ↑                   ↑         ↑
GitHubClient  RepositoryAnalyzer  RepositoryScorer  CLI
```

### Scoring System
The tool evaluates repositories on 5 weighted criteria:
- CLI/API Interface (30%) - Detects argparse, Flask, FastAPI patterns
- Documentation Quality (20%) - Analyzes README and docs/ quality  
- Code Simplicity (20%) - Evaluates modularity and complexity
- License Compatibility (20%) - Prefers MIT, BSD, Apache licenses
- Maintenance Activity (10%) - Recent commits and updates

## Key Design Patterns

### Async/Await Architecture
- All API calls and I/O operations use async/await
- Concurrent repository processing with semaphore-based rate limiting
- Async context managers for resource management

### Data Models
- Uses `@dataclass` for structured data representation
- Consistent `to_dict()` and `to_json()` methods for serialization
- Separation between metadata, analysis, and scoring concerns

### Configuration
- **Token resolution:** `get_effective_token()` in config.py tries, in order: `--token`, `GITHUB_TOKEN` env, then `gh auth token` (if GitHub CLI is installed and logged in).
- Configurable scoring weights and thresholds in `Config`.
- Multiple output formats (JSON, JSONL, CSV).

## Entry Points

- **scout.py** - Direct CLI entry point (calls `repo_scout.cli:main`)
- **repo_scout.cli:main** - Async main entry point
- **repo-scout** - Console script (defined in `pyproject.toml` [project.scripts])

## Dependencies

- **aiohttp** - Async HTTP client for GitHub API
- **typing-extensions** - Enhanced type hints

See `pyproject.toml` for optional dev deps (pytest, black, ruff).

## Development Notes

- Uses async generators (`AsyncIterator`) for memory-efficient streaming
- GitHub API rate limiting handled automatically
- Comprehensive error handling with detailed logging
- Modular design allows easy extension of analysis criteria