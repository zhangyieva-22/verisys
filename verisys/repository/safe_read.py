"""Read one discovered Python file without crawling or executing source.

All child symlinks are rejected. POSIX descriptors and NOFOLLOW protect child
opens against symlink replacement. In-place writes and arbitrary directory
renames are not a snapshot guarantee; the repository/root ancestors should be
stable during inspection. Exceptions expose categories, never OS error text.
"""

import errno
import os
import stat
from enum import StrEnum
from pathlib import Path

from .discovery import DEFAULT_MAX_FILE_BYTES, EXCLUDED_DIRECTORIES, _obvious_binary, _open_directory


class ReadReason(StrEnum):
    OUTSIDE_ROOT = "outside_root"
    SYMLINK = "symlink"
    NON_REGULAR_FILE = "non_regular_file"
    FILE_TOO_LARGE = "file_too_large"
    AGGREGATE_BUDGET_EXHAUSTED = "aggregate_budget_exhausted"
    READ_ERROR = "read_error"
    INVALID_PATH = "invalid_path"
    EXCLUDED_PATH = "excluded_path"
    BINARY = "binary"


class UnsafeSourceError(ValueError):
    """One sanitized read error, with consumption for aggregate accounting."""

    def __init__(self, reason: ReadReason, *, bytes_read: int = 0):
        self.reason = reason
        self.bytes_read = bytes_read
        super().__init__(reason.value)


def read_python_source(
    root: Path, relative: Path, *, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    remaining_bytes: int | None = None,
) -> bytes:
    """Read at most the remaining budget, including when a file grows.

    Known oversize files are rejected before reading. Without an aggregate
    budget, one extra byte detects per-file growth. With a budget, fstat after
    reading detects growth without exceeding that budget. Python encoding
    cookies are left to the standard-library parser.
    """
    if max_file_bytes < 0 or (remaining_bytes is not None and remaining_bytes < 0):
        raise ValueError("Read limits must be nonnegative")
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".py":
        raise UnsafeSourceError(ReadReason.INVALID_PATH)
    if any(part in EXCLUDED_DIRECTORIES or part == ".env" or part.startswith(".env.")
           for part in relative.parts):
        raise UnsafeSourceError(ReadReason.EXCLUDED_PATH)
    if remaining_bytes == 0:
        raise UnsafeSourceError(ReadReason.AGGREGATE_BUDGET_EXHAUSTED)
    consumed = 0
    try:
        if not (root / relative).resolve(strict=True).is_relative_to(root):
            raise UnsafeSourceError(ReadReason.OUTSIDE_ROOT)
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            parent_fd = _open_directory(root_fd, relative.parent)
            try:
                descriptor = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                     dir_fd=parent_fd)
                try:
                    info = os.fstat(descriptor)
                    if not stat.S_ISREG(info.st_mode):
                        raise UnsafeSourceError(ReadReason.NON_REGULAR_FILE)
                    if info.st_size > max_file_bytes:
                        raise UnsafeSourceError(ReadReason.FILE_TOO_LARGE)
                    if remaining_bytes is not None and info.st_size > remaining_bytes:
                        raise UnsafeSourceError(ReadReason.AGGREGATE_BUDGET_EXHAUSTED)
                    chunks = []
                    allowance = max_file_bytes + 1
                    if remaining_bytes is not None:
                        allowance = min(allowance, remaining_bytes)
                    while consumed < allowance:
                        chunk = os.read(descriptor, min(allowance - consumed, 64 * 1024))
                        if not chunk:
                            break
                        chunks.append(chunk)
                        consumed += len(chunk)
                    actual_size = os.fstat(descriptor).st_size
                    if consumed > max_file_bytes or actual_size > max_file_bytes:
                        raise UnsafeSourceError(ReadReason.FILE_TOO_LARGE, bytes_read=consumed)
                    if remaining_bytes is not None and actual_size > remaining_bytes:
                        raise UnsafeSourceError(ReadReason.AGGREGATE_BUDGET_EXHAUSTED, bytes_read=consumed)
                    data = b"".join(chunks)
                    if _obvious_binary(data):
                        raise UnsafeSourceError(ReadReason.BINARY, bytes_read=consumed)
                    return data
                finally:
                    os.close(descriptor)
            finally:
                os.close(parent_fd)
        finally:
            os.close(root_fd)
    except (OSError, RuntimeError) as error:
        reason = ReadReason.SYMLINK if isinstance(error, OSError) and error.errno == errno.ELOOP else ReadReason.READ_ERROR
        raise UnsafeSourceError(reason, bytes_read=consumed) from None
