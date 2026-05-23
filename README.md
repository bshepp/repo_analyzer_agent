# MCP Scout

**Model Context Protocol server discovery and scoring across GitHub.**

MCP Scout is an async Python CLI that crawls GitHub, detects which repositories are real MCP servers, and ranks them on how usable they are. Output is JSONL/JSON/CSV plus an optional `claude_desktop_config.json` snippet you can paste straight into your client.

It is a pivot from the original *Repository Scout* (generic AI-agent repo discovery). The MCP ecosystem grew up, "does it have a CLI" stopped being the interesting question, and "does it expose an MCP server" became one. See [`ORIGIN.md`](./ORIGIN.md) for the full backstory.

## Scoring System

MCP Scout evaluates repos on five criteria:

| Metric | Weight | What it checks |
|---|---|---|
| **MCP compliance** | 40% | SDK in deps (`mcp`, `fastmcp`, `@modelcontextprotocol/sdk`, `mcp-go`, `rmcp`), code patterns, transports |
| **Tool richness** | 20% | Count of `@tool` / `@resource` / `@prompt` registrations |
| **Install ergonomics** | 15% | README has a `claude_desktop_config.json` snippet / uvx / npx instructions |
| **License** | 15% | Permissive (MIT/Apache/BSD) scored highest |
| **Maintenance** | 10% | Recency of last update |

A repo only counts as an MCP server if it shows at least **two** of: MCP SDK in manifest, MCP code patterns, ≥1 registered tool, README self-identifying as MCP. Non-MCP repos always get a `low` readiness regardless of score.

## Installation

```bash
git clone https://github.com/bshepp/mcp-scout.git
cd mcp-scout

python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

pip install -e ".[dev]"
```

## Configuration

A GitHub token is optional but **strongly recommended** (unauthenticated requests are ~60/hour).

- **Easiest**: if you use [GitHub CLI](https://cli.github.com/), run `gh auth login` — Scout will use your token automatically.
- Or set `GITHUB_TOKEN` (`.env`, shell export, etc.).
- Or pass `--token` on the command line.

## Usage

```bash
# Default query: topic:mcp OR topic:model-context-protocol OR topic:mcp-server
python scout.py

# Restrict to a language
python scout.py --query "topic:mcp language:python" --max-repositories 50

# Score a specific candidate
python scout.py --repositories modelcontextprotocol/servers

# Export JSONL + a merged Claude Desktop config snippet
python scout.py --output mcp_servers.jsonl --install-config claude_desktop_config.json

# Show low-confidence/near-miss repos too
python scout.py --include-non-mcp
```

## Output formats

- **JSONL** (default): one repo per line, including full analysis and install template
- **JSON**: array of repo objects
- **CSV**: compact summary, one row per repo
- **`--install-config <path>`**: merged `claude_desktop_config.json` snippet with one entry per scouted server

### Example summary row

```json
{
  "url": "https://github.com/example/repo",
  "score": 82.5,
  "mcp_readiness": "high",
  "tools": 5,
  "resources": 2,
  "prompts": 0,
  "transports": ["stdio"],
  "sdk_language": "python",
  "summary": "An MCP server that exposes ...",
  "last_updated": "2026-04-12",
  "license": "MIT"
}
```

## Architecture

```
GitHub Search → Repository Analysis → Scoring → Export
     ↑              ↑                   ↑          ↑
GitHubClient  RepositoryAnalyzer   RepositoryScorer  CLI
                  └─ MCP signal detection
                  └─ Tool/resource/prompt counting
                  └─ Transport detection
                  └─ Install snippet detection
```

## What counts as an MCP server?

MCP Scout looks for:

- **Manifest signals** — SDK packages declared in `pyproject.toml` / `package.json` / `go.mod` / `Cargo.toml`
- **Code signals** — imports, decorators, `Server()` constructors, request-handler patterns
- **Tool registrations** — `@server.tool` / `server.addTool` / `register_tool` / `AddTool`
- **Transport detection** — stdio, SSE, streamable HTTP
- **README self-identification** — phrases like "MCP server", "Model Context Protocol", "Claude Desktop"
- **Install ergonomics** — presence of a `claude_desktop_config.json` snippet, uvx/npx invocation, or `mcp install`

## Ethics

- Uses only **public repositories** through the official GitHub API
- Respects **rate limits**
- **No private data** access

## Development

```bash
pytest                                  # 22 tests
ruff check mcp_scout tests
black mcp_scout tests
```

See `CLAUDE.md` for the architecture map and entry points.

## Roadmap

- **Cache layer** — sqlite-backed memo of analyses so re-runs only re-score stale repos
- **Validation against existing registries** — cross-check with `mcp.so`, `smithery.ai`, Anthropic's official list to flag false positives/negatives
- **More accurate install templates** — read `pyproject.toml`/`package.json` to derive the real install command, not just the repo name
- **Per-tool extraction** — extract tool names and JSON schemas, not just counts
- **GitHub Actions CI** — pytest + ruff + black on PRs
- **Additional hosts** — extend beyond GitHub to GitLab, Codeberg, Gitea

## Contributing

1. Fork
2. Create a feature branch
3. Make your changes (`pytest` should still pass)
4. Submit a pull request

## License

MIT — see `LICENSE`.

## Support

- **Issues**: <https://github.com/bshepp/mcp-scout/issues>
- **Documentation**: this README and `CLAUDE.md`
