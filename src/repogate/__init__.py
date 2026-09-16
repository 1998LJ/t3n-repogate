"""RepoGate package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("t3n-repogate")
except PackageNotFoundError:
    try:
        __version__ = version("repogate")
    except PackageNotFoundError:
        __version__ = "1.1.0.dev0"

from .engine import RepoGateEngine

__all__ = ["RepoGateEngine", "__version__"]
