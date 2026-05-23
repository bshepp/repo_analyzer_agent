# 🛰️ Repository Scout

**AI Agent-Friendly Repository Discovery Tool**

Repository Scout is a polite, legally compliant crawler and analyzer that scans public repositories (e.g., GitHub) to identify and rank projects that would be useful tools for AI agents — even if they are not explicitly designed for that purpose.

## 🎯 Features

- **GitHub Repository Crawling**: Uses official GitHub API with rate limiting
- **NLP-Based Analysis**: Analyzes repository structure, documentation, and code
- **Agent-Friendliness Scoring**: Ranks repositories based on CLI/API availability, documentation quality, and more
- **Multiple Export Formats**: Export results as JSON, JSONL, or CSV
- **Comprehensive CLI**: Easy-to-use command-line interface
- **Async Architecture**: Efficient concurrent processing

## 📊 Scoring System

Repository Scout evaluates repositories based on:

| Metric | Weight | Description |
|--------|--------|-------------|
| **CLI/API Interface** | 30% | Detects argparse, Flask, FastAPI, etc. |
| **Documentation Quality** | 20% | Analyzes README, docs/, and code comments |
| **Code Simplicity** | 20% | Evaluates modularity and complexity |
| **License Compatibility** | 20% | Prefers MIT, BSD, Apache licenses |
| **Maintenance Activity** | 10% | Recent commits and updates |

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/bshepp/repo_analyzer_agent.git
cd repo_analyzer_agent

# Create a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# Install in development mode (includes dev deps for testing/linting)
pip install -e ".[dev]"

# Or runtime only
pip install -e .
# pip install -r requirements.txt
```

## 🔧 Configuration

A GitHub token is optional but **strongly recommended** (without it, API rate limits are ~60/hour).

- **Easiest:** If you use [GitHub CLI](https://cli.github.com/), run `gh auth login`—the scout will use your token automatically.
- Or set `GITHUB_TOKEN`: copy `.env.example` to `.env` and set it, or export it (`export GITHUB_TOKEN=...` / Windows: `set GITHUB_TOKEN=...`).
- Or pass `--token` on the command line.

## 📖 Usage

### Basic Usage

```bash
# Search for Python repositories with >100 stars
python scout.py --query "stars:>100 language:python"

# Search with specific criteria
python scout.py --query "machine learning" --min-stars 500 --max-repositories 50

# Scout specific repositories
python scout.py --repositories numpy/numpy pandas-dev/pandas

# Export results to file
python scout.py --query "cli tool" --output results.jsonl --format jsonl
```

### Advanced Usage

```bash
# Filter by multiple languages
python scout.py --query "data science" --languages python r --min-score 60

# Include archived repositories
python scout.py --query "web framework" --include-archived

# Verbose output with detailed logging
python scout.py --query "api" --verbose --max-repositories 25
```

### Output Formats

- **JSONL**: One repository per line (default)
- **JSON**: Complete array of repositories
- **CSV**: Tabular format with summary data

### Example Output

```json
{
  "url": "https://github.com/user/repo",
  "score": 82.5,
  "tags": ["cli", "python", "api", "documentation"],
  "summary": "A command-line tool for image processing with Flask API",
  "last_updated": "2024-07-01",
  "license": "MIT",
  "agent_friendliness": "high"
}
```

## 🏗️ Architecture

```
┌─────────────────────┐
│  GitHub API Client  │
│  (Rate Limited)     │
└─────────┬───────────┘
          │
          v
┌─────────────────────┐
│  Repository         │
│  Analyzer           │
└─────────┬───────────┘
          │
          v
┌─────────────────────┐
│  Scoring Engine     │
└─────────┬───────────┘
          │
          v
┌─────────────────────┐
│  CLI / Export       │
└─────────────────────┘
```

## 🔍 What Makes a Repository Agent-Friendly?

Repository Scout looks for:

- **Command-line interfaces** (argparse, click, typer)
- **Web APIs** (Flask, FastAPI, Django)
- **Clear documentation** (README, docs/, examples)
- **Simple, modular code structure**
- **Permissive licenses** (MIT, BSD, Apache)
- **Active maintenance** (recent commits, issue activity)

## 🧠 Use Cases for AI Agents

AI agents can use Repository Scout to:

- **Discover Tools**: Find PDF parsers, web scrapers, image processors
- **Generate Wrappers**: Create integration code for existing tools
- **Suggest Improvements**: Identify repositories that could be made more agent-friendly
- **Build Workflows**: Chain together multiple agent-friendly tools

## ⚖️ Ethics & Compliance

- Uses only **public repositories** through official GitHub API
- Respects **rate limits** and API guidelines
- **No private data** access
- Allows repository owners to opt-out (planned feature)

## 🧪 Development

```bash
# Run tests
pytest

# Lint and format
ruff check repo_scout tests
black repo_scout tests
```

See `CLAUDE.md` for architecture and entry points.

## 🗺️ Roadmap

Ideas for continued development:

- **MCP server detection** — flag repos that expose a Model Context Protocol server (a strong "agent-ready" signal).
- **Additional Git hosts** — extend beyond GitHub to GitLab, Codeberg, and Gitea.
- **Local caching layer** — persist analyses (sqlite) so re-runs only re-analyze stale repos.
- **More languages** — current detection patterns are Python-centric; add JS/TS, Go, Rust signal sets.
- **Examples directory** — committed sample runs (JSONL outputs) for common queries.
- **CI workflow** — GitHub Actions to run pytest + ruff + black on PRs.
- **Web dashboard** — read JSONL output into a small static UI for browsing/filtering scored repos.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 📬 Support

- **Issues**: [GitHub Issues](https://github.com/bshepp/repo_analyzer_agent/issues)
- **Documentation**: This README and inline code documentation

---

**Repository Scout** - Making the open source ecosystem more accessible to AI agents 🤖