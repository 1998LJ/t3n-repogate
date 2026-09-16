"""Legacy compatibility shim for RepoGateEngine.

Enables existing scripts, historical test runners, and demos to import
directly from `repogate_engine` without breaking changes.
"""

import sys
from pathlib import Path

# Ensure src is in sys.path if not installed as package
src_dir = str(Path(__file__).parent / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from repogate.engine import RepoGateEngine
except ImportError:
    from src.repogate.engine import RepoGateEngine

__all__ = ["RepoGateEngine"]
