"""Bounded, deterministic Python file discovery without importing source.

All child symlinks are skipped, including internal links, so aliases cannot
bypass exclusions or create loops. A caller-supplied root is canonicalized.
Directories/files are opened relative to directory descriptors with NOFOLLOW
to prevent child path replacement from redirecting reads through symlinks.
This implementation targets local POSIX filesystems and a stable repository.
Returned paths are not an immutable snapshot: later readers must independently
enforce the same security boundary if repository content can change.
"""

import os
import stat
from enum import StrEnum
from itertools import islice
from pathlib import Path

from pydantic import ConfigDict, Field

from verisys.models.base import DomainModel

DEFAULT_MAX_FILE_BYTES = 1024 * 1024
DEFAULT_MAX_FILES = 1000
DEFAULT_MAX_TOTAL_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_ENTRIES = 100_000
BINARY_SAMPLE_BYTES = 4096
# Documentation paths are recorded for opt-in understanding only; never read here.
MAX_DOCUMENTS = 500
DOCUMENT_SUFFIXES = frozenset({".md", ".rst", ".txt"})
# Manifests describe components analysis cannot see (frontends, containers, dependencies).
MANIFEST_NAMES = frozenset({"package.json", "pyproject.toml", "setup.cfg", "Dockerfile", "docker-compose.yml",
                            "docker-compose.yaml", "compose.yml", "compose.yaml"})


def is_document(path: Path) -> bool:
    """Documentation or manifest paths recorded for opt-in understanding; never Python source."""
    return path.suffix != ".py" and (path.suffix in DOCUMENT_SUFFIXES or path.name in MANIFEST_NAMES
                                     or path.name.upper().startswith("README"))
EXCLUDED_DIRECTORIES = frozenset({
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".tox",
    ".pytest_cache", ".mypy_cache", "vendor", "generated", "build", "dist",
})


class DiscoveryLimits(DomainModel):
    model_config = ConfigDict(frozen=True)

    max_file_bytes: int = Field(default=DEFAULT_MAX_FILE_BYTES, ge=0, strict=True)
    max_files: int = Field(default=DEFAULT_MAX_FILES, ge=0, strict=True)
    max_total_bytes: int = Field(default=DEFAULT_MAX_TOTAL_BYTES, ge=0, strict=True)
    max_entries: int = Field(default=DEFAULT_MAX_ENTRIES, ge=0, strict=True)


class SkipReason(StrEnum):
    EXCLUDED_DIRECTORY = "EXCLUDED_DIRECTORY"
    SENSITIVE_FILE = "SENSITIVE_FILE"
    NON_PYTHON = "NON_PYTHON"
    SYMLINK = "SYMLINK"
    NON_REGULAR_FILE = "NON_REGULAR_FILE"
    BINARY = "BINARY"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    FILE_COUNT_LIMIT = "FILE_COUNT_LIMIT"
    TOTAL_SIZE_LIMIT = "TOTAL_SIZE_LIMIT"
    ENTRY_LIMIT = "ENTRY_LIMIT"
    IO_ERROR = "IO_ERROR"


class SkippedItem(DomainModel):
    path: Path
    reason: SkipReason


class DiscoveryResult(DomainModel):
    repository_root: Path
    limits: DiscoveryLimits = Field(default_factory=DiscoveryLimits, frozen=True)
    files: list[Path] = Field(default_factory=list)
    skipped: list[SkippedItem] = Field(default_factory=list)
    truncated: bool = False
    limitations: list[str] = Field(default_factory=list)
    # Separate from source scope: documents never change limitations or truncation.
    documents: list[Path] = Field(default_factory=list)
    documents_truncated: bool = False


def _open_directory(root_fd: int, relative: Path) -> int:
    """Open each component without following links, anchored to the root."""
    descriptor = os.dup(root_fd)
    try:
        for part in relative.parts:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError:
        os.close(descriptor)
        raise


def _obvious_binary(sample: bytes) -> bool:
    # Do not decode as UTF-8: Python can declare other source encodings.
    return any(byte < 32 and byte not in (9, 10, 12, 13) for byte in sample)


def discover_repository(
    root: str | os.PathLike[str], *, limits: DiscoveryLimits | None = None,
) -> DiscoveryResult:
    """Return sorted relative .py paths and explicit skips/scan limitations.

    Missing roots raise FileNotFoundError; non-directories raise
    NotADirectoryError. Non-Python and environment files are never read.
    Binary sampling reads at most 4096 bytes per candidate, not source code
    semantics. Reaching a limit stops the scan with a visible truncation;
    unvisited descendants are covered by that limitation, not enumerated.
    """
    limits = limits if limits is not None else DiscoveryLimits()
    repository_root = Path(root).resolve(strict=True)
    if not repository_root.is_dir():
        raise NotADirectoryError(f"Repository root is not a directory: {repository_root}")
    result = DiscoveryResult(repository_root=repository_root, limits=limits)
    total_bytes = visited = 0
    pending = [Path(".")]

    def skip(path: Path, reason: SkipReason) -> None:
        result.skipped.append(SkippedItem(path=path, reason=reason))

    def truncate(path: Path, reason: SkipReason) -> None:
        skip(path, reason)
        result.truncated = True
        result.limitations.append(f"{reason.value}: scan stopped; remaining entries were not inspected.")

    root_fd = os.open(repository_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        while pending and not result.truncated:
            directory = pending.pop()
            try:
                directory_fd = _open_directory(root_fd, directory)
            except OSError:
                skip(directory, SkipReason.IO_ERROR)
                result.limitations.append(f"Could not inspect directory: {directory.as_posix()}")
                continue
            try:
                try:
                    with os.scandir(directory_fd) as iterator:
                        # Bound directory listing itself, not just source reads.
                        # If it exceeds the budget, discard the entire listing
                        # rather than selecting a filesystem-order-dependent subset.
                        entries = list(islice(iterator, limits.max_entries - visited + 1))
                except OSError:
                    skip(directory, SkipReason.IO_ERROR)
                    result.limitations.append(f"Could not list directory: {directory.as_posix()}")
                    continue
                if len(entries) > limits.max_entries - visited:
                    truncate(directory, SkipReason.ENTRY_LIMIT)
                    break
                entries.sort(key=lambda entry: entry.name)
                subdirectories = []
                for entry in entries:
                    relative = directory / entry.name
                    if visited >= limits.max_entries:
                        truncate(relative, SkipReason.ENTRY_LIMIT)
                        break
                    visited += 1
                    if entry.name == ".env" or entry.name.startswith(".env."):
                        skip(relative, SkipReason.SENSITIVE_FILE)
                        continue
                    try:
                        info = os.stat(entry.name, dir_fd=directory_fd, follow_symlinks=False)
                        if stat.S_ISLNK(info.st_mode):
                            skip(relative, SkipReason.SYMLINK)
                        elif stat.S_ISDIR(info.st_mode):
                            if entry.name in EXCLUDED_DIRECTORIES:
                                skip(relative, SkipReason.EXCLUDED_DIRECTORY)
                            else:
                                subdirectories.append(relative)
                        elif not stat.S_ISREG(info.st_mode):
                            skip(relative, SkipReason.NON_REGULAR_FILE)
                        elif relative.suffix != ".py":
                            skip(relative, SkipReason.NON_PYTHON)
                            if is_document(relative):
                                if len(result.documents) < MAX_DOCUMENTS:
                                    result.documents.append(relative)
                                else:
                                    result.documents_truncated = True
                        else:
                            # NONBLOCK avoids hanging if a regular file is replaced by a FIFO.
                            descriptor = os.open(entry.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                                 dir_fd=directory_fd)
                            try:
                                actual = os.fstat(descriptor)
                                if not stat.S_ISREG(actual.st_mode):
                                    skip(relative, SkipReason.NON_REGULAR_FILE)
                                elif actual.st_size > limits.max_file_bytes:
                                    skip(relative, SkipReason.FILE_TOO_LARGE)
                                elif len(result.files) >= limits.max_files:
                                    truncate(relative, SkipReason.FILE_COUNT_LIMIT)
                                elif total_bytes + actual.st_size > limits.max_total_bytes:
                                    truncate(relative, SkipReason.TOTAL_SIZE_LIMIT)
                                elif _obvious_binary(os.read(descriptor, min(BINARY_SAMPLE_BYTES, actual.st_size))):
                                    skip(relative, SkipReason.BINARY)
                                else:
                                    result.files.append(relative)
                                    total_bytes += actual.st_size
                            finally:
                                os.close(descriptor)
                    except OSError:
                        skip(relative, SkipReason.IO_ERROR)
                        result.limitations.append(f"Could not inspect item: {relative.as_posix()}")
                    if result.truncated:
                        break
                pending.extend(reversed(subdirectories))
            finally:
                os.close(directory_fd)
    finally:
        os.close(root_fd)
    result.files.sort(key=lambda path: path.as_posix())
    result.documents.sort(key=lambda path: path.as_posix())
    result.skipped.sort(key=lambda item: (item.path.as_posix(), item.reason.value))
    return result
