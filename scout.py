#!/usr/bin/env python3
"""
Repository Scout CLI Entry Point
"""

import sys
import asyncio
from repo_scout.cli import main

if __name__ == '__main__':
    asyncio.run(main())