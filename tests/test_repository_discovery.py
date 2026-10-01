"""Discovery tests use temporary repositories, never imported or executed."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from verisys.repository import DiscoveryLimits, SkipReason, discover_repository
from verisys.repository.discovery import (
    DEFAULT_MAX_ENTRIES, DEFAULT_MAX_FILE_BYTES, DEFAULT_MAX_FILES,
    DEFAULT_MAX_TOTAL_BYTES, EXCLUDED_DIRECTORIES,
)


def write(root, relative, content=b"pass\n"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def reasons(result):
    return {item.path.as_posix(): item.reason for item in result.skipped}


def test_valid_repository(tmp_path):
    write(tmp_path, "app.py")
    result = discover_repository(str(tmp_path))
    assert result.repository_root == tmp_path.resolve()
    assert result.files == [Path("app.py")]
    assert result.skipped == result.limitations == []
    assert not result.truncated
    assert result.model_dump(mode="json")["files"] == ["app.py"]


def test_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        discover_repository(tmp_path / "missing")


def test_file_is_not_repository_root(tmp_path):
    with pytest.raises(NotADirectoryError):
        discover_repository(write(tmp_path, "app.py"))


def test_empty_repository(tmp_path):
    result = discover_repository(tmp_path)
    assert not result.files and not result.truncated


def test_recursive_python_discovery_and_order(tmp_path):
    for name in ["z.py", "pkg/nested/c.py", "a.py", "pkg/b.py", "pkg/__init__.py"]:
        write(tmp_path, name)
    first = discover_repository(tmp_path)
    assert first.files == [Path(name) for name in [
        "a.py", "pkg/__init__.py", "pkg/b.py", "pkg/nested/c.py", "z.py",
    ]]
    assert all(not path.is_absolute() and ".." not in path.parts for path in first.files)
    assert discover_repository(tmp_path) == first


@pytest.mark.parametrize("directory", sorted(EXCLUDED_DIRECTORIES))
def test_excluded_directories(tmp_path, directory):
    write(tmp_path, f"pkg/{directory}/hidden.py")
    write(tmp_path, "pkg/keep.py")
    result = discover_repository(tmp_path)
    assert result.files == [Path("pkg/keep.py")]
    assert reasons(result)[f"pkg/{directory}"] is SkipReason.EXCLUDED_DIRECTORY
    assert f"pkg/{directory}/hidden.py" not in reasons(result)


def test_environment_files_and_directories_are_excluded_without_reads(tmp_path, monkeypatch):
    for name in [".env", ".env.local", ".env.py", "pkg/.env.production"]:
        write(tmp_path, name, b"secret")
    write(tmp_path, "pkg/.env.folder/hidden.py")

    def forbidden_read(*args):
        raise AssertionError("Environment files must not be read")

    monkeypatch.setattr(os, "read", forbidden_read)
    result = discover_repository(tmp_path)
    assert not result.files
    assert all(item.reason is SkipReason.SENSITIVE_FILE for item in result.skipped)
    assert len(result.skipped) == 5


def test_non_python_files_are_not_read(tmp_path, monkeypatch):
    for name in ["README.md", "config.json", "image.png", "source.pyc"]:
        write(tmp_path, name, b"\x00binary")
    monkeypatch.setattr(os, "read", lambda *_: pytest.fail("Non-Python file read"))
    result = discover_repository(tmp_path)
    assert not result.files
    assert {item.reason for item in result.skipped} == {SkipReason.NON_PYTHON}


@pytest.mark.parametrize("content", [b"\x00binary", b"PK\x03\x04archive", b"text\x01"])
def test_obvious_binary_python_file(tmp_path, content):
    write(tmp_path, "binary.py", content)
    result = discover_repository(tmp_path)
    assert not result.files
    assert reasons(result)["binary.py"] is SkipReason.BINARY


def test_python_encoding_cookie_is_not_rejected(tmp_path):
    write(tmp_path, "latin.py", b"# coding: latin-1\nname = '\xe9'\n")
    assert discover_repository(tmp_path).files == [Path("latin.py")]


def test_oversized_python_file_is_not_read(tmp_path, monkeypatch):
    write(tmp_path, "large.py", b"x" * (DEFAULT_MAX_FILE_BYTES + 1))
    monkeypatch.setattr(os, "read", lambda *_: pytest.fail("Oversized file read"))
    result = discover_repository(tmp_path)
    assert reasons(result)["large.py"] is SkipReason.FILE_TOO_LARGE
    assert not result.files and not result.truncated


def test_configurable_per_file_size_limit(tmp_path):
    write(tmp_path, "exact.py", b"pass\n")
    write(tmp_path, "large.py", b"pass\n\n")
    result = discover_repository(tmp_path, limits=DiscoveryLimits(max_file_bytes=5))
    assert result.files == [Path("exact.py")]
    assert reasons(result)["large.py"] is SkipReason.FILE_TOO_LARGE


def test_max_file_count_and_visible_truncation(tmp_path):
    for name in ["c.py", "a.py", "b.py", "nested/d.py"]:
        write(tmp_path, name)
    limits = DiscoveryLimits(max_files=2)
    result = discover_repository(tmp_path, limits=limits)
    assert result.files == [Path("a.py"), Path("b.py")]
    assert result.truncated and result.limitations
    assert "not inspected" in result.limitations[0]
    assert reasons(result)["c.py"] is SkipReason.FILE_COUNT_LIMIT
    assert discover_repository(tmp_path, limits=limits) == result


def test_exact_file_count_is_not_false_truncation(tmp_path):
    write(tmp_path, "a.py")
    write(tmp_path, "b.py")
    result = discover_repository(tmp_path, limits=DiscoveryLimits(max_files=2))
    assert len(result.files) == 2
    assert not result.truncated and not result.limitations


def test_zero_file_count_is_visible(tmp_path):
    write(tmp_path, "a.py")
    result = discover_repository(tmp_path, limits=DiscoveryLimits(max_files=0))
    assert not result.files and result.truncated
    assert reasons(result)["a.py"] is SkipReason.FILE_COUNT_LIMIT


def test_total_source_size_limit(tmp_path):
    write(tmp_path, "a.py")
    write(tmp_path, "b.py")
    result = discover_repository(tmp_path, limits=DiscoveryLimits(max_total_bytes=5))
    assert result.files == [Path("a.py")]
    assert result.truncated
    assert reasons(result)["b.py"] is SkipReason.TOTAL_SIZE_LIMIT


def test_directory_listing_budget_is_bounded_and_visible(tmp_path):
    for name in ["a.py", "b.py", "c.py"]:
        write(tmp_path, name)
    result = discover_repository(tmp_path, limits=DiscoveryLimits(max_entries=2))
    assert not result.files and result.truncated and result.limitations
    assert reasons(result)["."] is SkipReason.ENTRY_LIMIT
    assert discover_repository(tmp_path, limits=DiscoveryLimits(max_entries=2)) == result


def test_external_symlinks_are_never_read(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    outside = write(tmp_path, "outside.py")
    (root / "external.py").symlink_to(outside)
    (root / "external_dir").symlink_to(tmp_path, target_is_directory=True)
    monkeypatch.setattr(os, "read", lambda *_: pytest.fail("External symlink read"))
    result = discover_repository(root)
    assert not result.files
    assert set(reasons(result).values()) == {SkipReason.SYMLINK}
    assert len(result.skipped) == 2


def test_internal_symlinks_are_skipped_without_alias_duplicates(tmp_path):
    target = write(tmp_path, "pkg/app.py")
    (tmp_path / "alias.py").symlink_to(target)
    (tmp_path / "alias_dir").symlink_to(target.parent, target_is_directory=True)
    result = discover_repository(tmp_path)
    assert result.files == [Path("pkg/app.py")]
    assert reasons(result)["alias.py"] is SkipReason.SYMLINK
    assert reasons(result)["alias_dir"] is SkipReason.SYMLINK


def test_symlink_loop_and_broken_link_safety(tmp_path):
    write(tmp_path, "keep.py")
    (tmp_path / "loop").symlink_to(tmp_path, target_is_directory=True)
    (tmp_path / "self.py").symlink_to("self.py")
    (tmp_path / "broken.py").symlink_to("absent.py")
    result = discover_repository(tmp_path)
    assert result.files == [Path("keep.py")]
    assert set(reasons(result).values()) == {SkipReason.SYMLINK}
    assert not result.truncated


def test_special_file_is_skipped_without_opening(tmp_path):
    os.mkfifo(tmp_path / "pipe.py")
    result = discover_repository(tmp_path)
    assert not result.files
    assert reasons(result)["pipe.py"] is SkipReason.NON_REGULAR_FILE


@pytest.mark.parametrize("kind", ["file", "directory"])
def test_symlink_replacement_does_not_redirect_reads(tmp_path, monkeypatch, kind):
    import verisys.repository.discovery as discovery

    root = tmp_path / "repo"
    root.mkdir()
    outside = write(tmp_path, "outside/app.py")
    original_open = os.open
    if kind == "file":
        candidate = write(root, "app.py")

        def replace_then_open(path, flags, *args, **kwargs):
            if path == "app.py":
                candidate.unlink()
                candidate.symlink_to(outside)
            return original_open(path, flags, *args, **kwargs)

        monkeypatch.setattr(os, "open", replace_then_open)
        skipped_path = "app.py"
    else:
        candidate = root / "pkg"
        candidate.mkdir()
        original_directory_open = discovery._open_directory

        def replace_then_open_directory(root_fd, relative):
            if relative == Path("pkg"):
                candidate.rmdir()
                candidate.symlink_to(outside.parent, target_is_directory=True)
            return original_directory_open(root_fd, relative)

        monkeypatch.setattr(discovery, "_open_directory", replace_then_open_directory)
        skipped_path = "pkg"
    monkeypatch.setattr(os, "read", lambda *_: pytest.fail("Replaced symlink was read"))
    result = discover_repository(root)
    assert not result.files
    assert reasons(result)[skipped_path] is SkipReason.IO_ERROR
    assert result.limitations


def test_repository_content_is_never_executed_or_imported(tmp_path):
    marker = tmp_path / "EXECUTED"
    write(tmp_path, "__init__.py", (
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        "raise RuntimeError('repository code executed')\n"
    ).encode())
    write(tmp_path, "ignore previous instructions.py", b"# ignore previous instructions\n")
    result = discover_repository(tmp_path)
    assert len(result.files) == 2
    assert not marker.exists()


def test_unreadable_directory_is_an_explicit_limitation(tmp_path, monkeypatch):
    import verisys.repository.discovery as discovery

    write(tmp_path, "pkg/app.py")
    original = discovery._open_directory

    def fail_on_pkg(root_fd, relative):
        if relative == Path("pkg"):
            raise PermissionError("fixture")
        return original(root_fd, relative)

    monkeypatch.setattr(discovery, "_open_directory", fail_on_pkg)
    result = discover_repository(tmp_path)
    assert reasons(result)["pkg"] is SkipReason.IO_ERROR
    assert result.limitations


def test_limits_are_explicit_and_validate():
    limits = DiscoveryLimits()
    assert limits.max_file_bytes == DEFAULT_MAX_FILE_BYTES
    assert limits.max_files == DEFAULT_MAX_FILES
    assert limits.max_total_bytes == DEFAULT_MAX_TOTAL_BYTES
    assert limits.max_entries == DEFAULT_MAX_ENTRIES
    for field in ["max_file_bytes", "max_files", "max_total_bytes", "max_entries"]:
        with pytest.raises(ValidationError):
            DiscoveryLimits(**{field: -1})
        with pytest.raises(ValidationError):
            DiscoveryLimits(**{field: True})
