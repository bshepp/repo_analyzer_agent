"""Configuration for MCP Scout."""

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
    """Configuration class for MCP Scout."""

    # GitHub API settings (resolved at runtime via get_effective_token() when needed)
    GITHUB_TOKEN: Optional[str] = os.getenv("GITHUB_TOKEN")
    GITHUB_API_BASE_URL: str = "https://api.github.com"
    GITHUB_RATE_LIMIT_BUFFER: int = 100  # Keep this many requests in reserve

    # Search defaults — MCP topic-first.
    DEFAULT_SEARCH_QUERY: str = "topic:mcp OR topic:model-context-protocol OR topic:mcp-server"
    MAX_REPOSITORIES_PER_SEARCH: int = 1000
    MIN_STARS_THRESHOLD: int = 0  # MCP ecosystem is young — don't gate by stars

    # Analysis settings
    README_MAX_LENGTH: int = 50000
    CODE_SAMPLE_SIZE: int = 30  # Cap on code files we'll fetch per repo

    # Scoring weights (sum to 1.0). Tuned for "is this a real MCP server?"
    SCORING_WEIGHTS: Dict[str, float] = {
        "mcp_compliance": 0.40,      # Does it actually implement MCP?
        "tool_richness": 0.20,       # How many tools/resources/prompts does it expose?
        "install_ergonomics": 0.15,  # Can a user actually install and configure it?
        "license": 0.15,             # Permissive licenses preferred for agent use
        "maintenance": 0.10,         # Recently updated
    }

    # License scoring (same rationale: permissive licenses are best for agent use)
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
        "CC0-1.0": 0.9,
    }

    # Map manifest filename → language family. Used to scope which SDK deps
    # we check in which file, so a TS package.json containing "mcp-go" doesn't
    # get tagged as a Python repo.
    MANIFEST_LANGUAGE_MAP: Dict[str, str] = {
        "pyproject.toml": "python",
        "requirements.txt": "python",
        "setup.py": "python",
        "setup.cfg": "python",
        "Pipfile": "python",
        "package.json": "typescript",
        "go.mod": "go",
        "Cargo.toml": "rust",
        "pom.xml": "java",
        "build.gradle": "java",
        "build.gradle.kts": "java",
    }

    # MCP SDK / package signals — presence in deps is strong evidence
    MCP_SDK_DEPS: Dict[str, List[str]] = {
        "python": [
            "mcp",            # official Anthropic SDK
            "fastmcp",        # popular community SDK
            "mcp-server",
        ],
        "typescript": [
            "@modelcontextprotocol/sdk",
            "@modelcontextprotocol/server",
        ],
        "go": [
            "github.com/mark3labs/mcp-go",
            "github.com/metoro-io/mcp-golang",
        ],
        "rust": [
            "rmcp",
            "mcp-server",
        ],
        "java": [
            "io.modelcontextprotocol",
        ],
    }

    # Code-level MCP signals — substrings searched in source files
    MCP_CODE_PATTERNS: List[str] = [
        "from mcp",
        "import mcp",
        "from fastmcp",
        "@modelcontextprotocol/sdk",
        "modelcontextprotocol",
        "FastMCP(",
        "@server.tool",
        "@server.resource",
        "@server.prompt",
        "@app.tool",
        "server.addTool",
        "server.setRequestHandler",
        "register_tool",
        "list_tools",
        "call_tool",
        "ListToolsRequestSchema",
        "CallToolRequestSchema",
        "mcp-go",
        "mark3labs/mcp-go",
    ]

    # Tool/resource/prompt registration patterns — counted for richness score
    TOOL_REGISTRATION_PATTERNS: List[str] = [
        r"@\w+\.tool\b",        # Python: @server.tool, @app.tool
        r"@\w+\.add_tool\b",
        r"\.addTool\s*\(",      # TypeScript: server.addTool(
        r"register_tool\s*\(",
        r"@tool\b",
        r"server\.tool\s*\(",
        r"add_tool\s*\(",
        r"AddTool\s*\(",        # Go convention
    ]

    RESOURCE_REGISTRATION_PATTERNS: List[str] = [
        r"@\w+\.resource\b",
        r"\.addResource\s*\(",
        r"register_resource\s*\(",
        r"@resource\b",
        r"AddResource\s*\(",
    ]

    PROMPT_REGISTRATION_PATTERNS: List[str] = [
        r"@\w+\.prompt\b",
        r"\.addPrompt\s*\(",
        r"register_prompt\s*\(",
        r"@prompt\b",
        r"AddPrompt\s*\(",
    ]

    # Transport signals — stdio / sse / http
    TRANSPORT_PATTERNS: Dict[str, List[str]] = {
        "stdio": [
            "StdioServerTransport",
            "stdio_server",
            "from mcp.server.stdio",
            "ServeStdio",
        ],
        "sse": [
            "SSEServerTransport",
            "sse_server",
            "ServeSSE",
        ],
        "http": [
            "streamableHttp",
            "StreamableHTTPServerTransport",
            "http_server",
        ],
    }

    # README signals that strongly suggest this is an MCP server
    README_MCP_SIGNALS: List[str] = [
        "model context protocol",
        "mcp server",
        "mcp client",
        "claude desktop",
        "claude_desktop_config",
        "mcp.json",
        "modelcontextprotocol",
        "cursor mcp",
        "continue.dev",
    ]

    # README signals that indicate good install ergonomics
    INSTALL_SNIPPET_SIGNALS: List[str] = [
        '"mcpServers"',
        "claude_desktop_config.json",
        "mcp install",
        "uvx",
        "npx -y",
        "smithery install",
    ]

    # Tags for language detection
    LANGUAGE_TAG_MAP: Dict[str, str] = {
        "python": "python-mcp",
        "typescript": "typescript-mcp",
        "javascript": "typescript-mcp",
        "go": "go-mcp",
        "rust": "rust-mcp",
        "java": "java-mcp",
    }

    # Output settings
    DEFAULT_OUTPUT_FORMAT: str = "jsonl"
    OUTPUT_FORMATS: List[str] = ["jsonl", "json", "csv"]

    @classmethod
    def validate(cls) -> bool:
        """Validate configuration settings. Returns False only for invalid weights."""
        return abs(sum(cls.SCORING_WEIGHTS.values()) - 1.0) < 1e-9

    @classmethod
    def get_user_agent(cls) -> str:
        """Get user agent string for API requests."""
        return "MCP-Scout/0.2.0 (https://github.com/bshepp/mcp-scout)"
