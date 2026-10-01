"""Safe local repository inputs, separate from architecture state."""

from .discovery import (
    DiscoveryLimits, DiscoveryResult, SkipReason, SkippedItem, discover_repository,
)

__all__ = [
    "DiscoveryLimits", "DiscoveryResult", "SkipReason", "SkippedItem",
    "discover_repository",
]
