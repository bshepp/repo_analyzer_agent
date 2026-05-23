# Origin Story

This project began life as **Repository Scout**, not MCP Scout. The pivot happened on a feature branch called `mcp-scout`, which was merged into `main` on 2026-05-23 (PR #1). This document records what the project originally tried to do, why that premise weakened, and what the branch changed — for anyone reading the git history and wondering why the package name and pyproject metadata look like they had a previous life.

## What Repository Scout was trying to do

Repository Scout was scaffolded in July 2025 with a simple thesis: **AI agents would need a curated catalog of GitHub repositories to choose from**. The thinking was that as agents became more capable, they'd want to wrap or call existing tools rather than re-implement everything from scratch — and somebody had to do the discovery work of "given a problem, which open-source repo is the best fit?"

The original scoring rubric reflected this generic-tool framing:

| Metric | Weight |
|---|---|
| CLI / API Interface | 30% |
| Documentation Quality | 20% |
| Code Simplicity | 20% |
| License Compatibility | 20% |
| Maintenance Activity | 10% |

The detector looked for `argparse`, `click`, `flask`, `fastapi`, and similar markers. The output was a JSONL list of "agent-friendly" repos with a `high` / `medium` / `low` rating.

There was also a sibling vision — a never-built three-component ecosystem called the **Research-Code Bridge** that would connect Repository Scout to a "Knowledge Connector" (arXiv paper analysis) via a bridge layer. Five docs describing that ecosystem (`BRIDGE_INTEGRATION.md`, `RESEARCH_CODE_BRIDGE_SPECIFICATION.md`, `STRATEGIC_QUESTIONS.md`, `STYLE_GUIDE.md`, `UNIFIED_FRAMEWORK.md`) lived in the repo until commit `d3e2704` (2026-05-23) removed them.

## Why the premise weakened

Two things shifted between July 2025 and May 2026 that made the original framing feel dated:

1. **Code-aware agents stopped needing a curated catalog.** Claude Code, Cursor, and similar tools can read repos directly and write integration glue on the fly. The "agent goes to a discovery service to find a CLI wrapper" workflow turned out to be the worse path; agents just clone and use whatever they need.

2. **MCP became the integration standard.** The Model Context Protocol (Anthropic, late 2024) gave the ecosystem a real answer to "how does an agent call a tool that lives in another process." Once that standard existed, the interesting "agent-ready" signal for a repo wasn't "does it have a CLI?" — it was "does it expose an MCP server?"

The original code wasn't bad. The premise just shrank.

## What the `mcp-scout` branch changed

The pivot kept the engineering and replaced the rubric:

**Kept**
- The async GitHub crawler (`github_client.py`) — battle-tested rate-limit handling, token resolution via `gh auth token` fallback
- The pipeline shape: search → analyze → score → export
- The output formats (JSONL / JSON / CSV)
- The CLI structure
- The dataclass-based serialization model

**Replaced**
- Detection patterns: from `argparse`/`flask`/etc. to MCP SDK imports (`mcp`, `fastmcp`, `@modelcontextprotocol/sdk`, `mcp-go`, `rmcp`), code patterns, and tool/resource/prompt registrations
- Scoring rubric: MCP compliance 40% / Tool richness 20% / Install ergonomics 15% / License 15% / Maintenance 10%
- Data shape: `RepositoryAnalysis` swapped `has_cli`/`has_api`/`detected_frameworks` for `is_mcp_server`/`mcp_sdk_language`/`mcp_tools_count`/`mcp_transports`; `RepositoryScore.agent_friendliness` became `mcp_readiness`
- Default search query: from `stars:>100 language:python` to `topic:mcp OR topic:model-context-protocol OR topic:mcp-server`

**Added**
- Transport detection (stdio / SSE / streamable HTTP)
- `mcp_config_gen.py` — generates `claude_desktop_config.json` snippet templates per scouted server, with a `--install-config` CLI flag that writes a merged config across all hits
- Two-of-four evidence rule for the `is_mcp_server` gate (manifest signal, code signal, ≥1 tool, README self-identification)

**Renamed**
- Python package `repo_scout/` → `mcp_scout/`
- Console script `repo-scout` → `mcp-scout`
- GitHub repo `repo_analyzer_agent` → `mcp-scout`
- `RepositoryScout` class kept as an alias of `MCPScout` for any external callers still using the old name

## The branch itself

The pivot was developed on a branch named `mcp-scout` and merged to `main` in PR #1 on 2026-05-23. After this document was written, the branch was deleted from both the local clone and the remote — its content lives on as commit `d71a754` ("Pivot to MCP Scout: detect and score MCP servers on GitHub") on the main branch history.

If you're spelunking the history and wondering why version 0.2.0 looks so different from 0.1.0, this is why.
