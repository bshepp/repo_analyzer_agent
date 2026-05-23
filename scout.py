#!/usr/bin/env python3
"""MCP Scout CLI Entry Point."""

import sys
import asyncio
from mcp_scout.cli import main

if __name__ == '__main__':
    asyncio.run(main())