"""Explicitly selected static verification; no runtime execution."""
from .run import verify_http_timeout_coverage, verify_timeout_coverage

__all__ = ["verify_http_timeout_coverage", "verify_timeout_coverage"]
