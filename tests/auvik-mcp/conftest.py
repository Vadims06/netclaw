"""Pytest configuration for auvik-mcp tests."""

import os
import sys

# Add the auvik-mcp server package directory to sys.path so imports like
# `from utils.constants import ...` resolve correctly.
_SERVER_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "..",
    "mcp-servers",
    "auvik-mcp",
)
sys.path.insert(0, os.path.abspath(_SERVER_DIR))

# Set dummy credentials so modules that read env vars at import time don't fail.
os.environ.setdefault("AUVIK_USERNAME", "test_user")
os.environ.setdefault("AUVIK_API_KEY", "test_key")
