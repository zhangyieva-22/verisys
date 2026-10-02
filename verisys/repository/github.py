"""Public GitHub acquisition only. No git, hooks, filters, subprocesses or execution."""
from contextlib import contextmanager
from dataclasses import dataclass
import gzip
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
from tempfile import TemporaryDirectory
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .source import GitHubRepositorySource, LocalRepositorySource, SHA_PATTERN

TRUSTED_HOSTS = frozenset({'api.github.com', 'codeload.github.com'})
DEFAULT_DOWNLOAD_BYTES = 20 * 1024 * 1024
DEFAULT_EXTRACTED_BYTES = 100 * 1024 * 1024
DEFAULT_FILE_BYTES = 5 * 1024 * 1024
DEFAULT_ARCHIVE_ENTRIES = 10000
DEFAULT_TIMEOUT_SECONDS = 30


class IntakeError(ValueError):
    """Stable categories only; never retain OS/network exception text."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class RemoteLimits:
    max_download_bytes: int = DEFAULT_DOWNLOAD_BYTES
    max_extracted_bytes: int = DEFAULT_EXTRACTED_BYTES
    max_file_bytes: int = DEFAULT_FILE_BYTES
    max_entries: int = DEFAULT_ARCHIVE_ENTRIES
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self):
        if min(self.max_download_bytes, self.max_extracted_bytes, self.max_file_bytes, self.max_entries, self.timeout_seconds) <= 0:
            raise ValueError('Remote limits must be positive')


def trusted_url(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.netloc not in TRUSTED_HOSTS or p.fragment:
        raise IntakeError('UNSAFE_REMOTE_URL')


class TrustedRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        trusted_url(newurl)
        # At most the bounded redirect count already enforced by urllib. Never forward credentials.
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class GitHubFetcher:
    """Injectable bounded HTTPS reader; no credentials or environment proxy routing."""
    def get(self, url, *, max_bytes, timeout):
        from urllib.request import ProxyHandler
        trusted_url(url)
        deadline = monotonic() + timeout
        try:
            opener = build_opener(ProxyHandler({}), TrustedRedirects())
            with opener.open(Request(url, headers={'User-Agent': 'Verisys-public-intake', 'Accept': 'application/vnd.github+json'}), timeout=timeout) as response:
                trusted_url(response.url)
                length = response.headers.get('Content-Length')
                if length and int(length) > max_bytes:
                    raise IntakeError('REPOSITORY_TOO_LARGE')
                chunks, consumed = [], 0
                while True:
                    if monotonic() >= deadline:
                        raise IntakeError('REMOTE_TIMEOUT')
                    chunk = response.read1(min(65536, max_bytes - consumed + 1))
                    if not chunk:
                        break
                    consumed += len(chunk)
                    if consumed > max_bytes:
                        raise IntakeError('REPOSITORY_TOO_LARGE')
                    chunks.append(chunk)
                return b''.join(chunks)
        except IntakeError:
            raise
        except HTTPError as failure:
            if failure.code == 404:
                raise IntakeError('REPOSITORY_NOT_FOUND_OR_PRIVATE') from None
            if failure.code in {403, 429}:
                raise IntakeError('GITHUB_RATE_LIMIT') from None
            if failure.code == 422:
                raise IntakeError('INVALID_REPOSITORY_REF') from None
            raise IntakeError('REMOTE_UNAVAILABLE') from None
        except TimeoutError:
            raise IntakeError('REMOTE_TIMEOUT') from None
        except URLError as failure:
            category = 'REMOTE_TIMEOUT' if isinstance(failure.reason, TimeoutError) else 'REMOTE_UNAVAILABLE'
            raise IntakeError(category) from None
        except (OSError, ValueError):
            raise IntakeError('REMOTE_UNAVAILABLE') from None


class BoundedDecoded:
    """Bound tar headers/padding as well as file payloads before tarfile consumes them."""
    def __init__(self, stream, limit):
        self.stream, self.remaining = stream, limit

    def read(self, size=-1):
        size = self.remaining + 1 if size < 0 else min(size, self.remaining + 1)
        data = self.stream.read(size)
        self.remaining -= len(data)
        if self.remaining < 0:
            raise IntakeError('REPOSITORY_TOO_LARGE')
        return data


def extract_archive(data, root, limits):
    """Stream regular files under one archive prefix. Links and special files fail closed."""
    if len(data) > limits.max_download_bytes:
        raise IntakeError('REPOSITORY_TOO_LARGE')
    seen, prefix, total = set(), None, 0
    try:
        stream = BoundedDecoded(gzip.GzipFile(fileobj=io.BytesIO(data)),
            limits.max_extracted_bytes + limits.max_entries * 2048 + 1024 * 1024)
        with tarfile.open(fileobj=stream, mode='r|') as archive:
            for count, member in enumerate(archive, 1):
                if count > limits.max_entries:
                    raise IntakeError('REPOSITORY_TOO_LARGE')
                name = member.name
                path = PurePosixPath(name)
                if (path.is_absolute() or '\\' in name or '\x00' in name or '..' in path.parts
                        or not path.parts or ':' in path.parts[0]):
                    raise IntakeError('UNSAFE_ARCHIVE_CONTENT')
                if prefix is None:
                    prefix = path.parts[0]
                if path.parts[0] != prefix or member.type not in {tarfile.DIRTYPE, tarfile.REGTYPE, tarfile.AREGTYPE}:
                    raise IntakeError('UNSAFE_ARCHIVE_CONTENT')
                relative = Path(*path.parts[1:])
                if not path.parts[1:]:
                    if not member.isdir():
                        raise IntakeError('UNSAFE_ARCHIVE_CONTENT')
                    continue
                if relative in seen:
                    raise IntakeError('UNSAFE_ARCHIVE_CONTENT')
                seen.add(relative)
                target = root / relative
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if member.size < 0 or member.size > limits.max_file_bytes or total + member.size > limits.max_extracted_bytes:
                    raise IntakeError('REPOSITORY_TOO_LARGE')
                total += member.size
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open('xb') as destination:
                    remaining = member.size
                    while remaining:
                        chunk = source.read(min(65536, remaining))
                        if not chunk:
                            raise IntakeError('MALFORMED_ARCHIVE')
                        destination.write(chunk)
                        remaining -= len(chunk)
            if prefix is None:
                raise IntakeError('MALFORMED_ARCHIVE')
        # Validate gzip footer and bound even trailing/concatenated compressed data.
        while stream.read(65536):
            pass
    except IntakeError:
        raise
    except (tarfile.TarError, OSError, EOFError, ValueError):
        raise IntakeError('MALFORMED_ARCHIVE') from None


@dataclass(frozen=True)
class MaterializedRepository:
    root: Path
    source: LocalRepositorySource | GitHubRepositorySource
    requested_ref: str | None = None
    resolved_commit_sha: str | None = None


class RepositoryMaterializer:
    def __init__(self, fetcher=None, *, limits=None, temp_parent=None):
        self.fetcher = fetcher or GitHubFetcher()
        self.limits = limits or RemoteLimits()
        self.temp_parent = temp_parent

    def _json(self, url):
        try:
            value = json.loads(self.fetcher.get(url, max_bytes=min(self.limits.max_download_bytes, 512 * 1024), timeout=self.limits.timeout_seconds))
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except IntakeError:
            raise
        except (ValueError, UnicodeError):
            raise IntakeError('REMOTE_INVALID_RESPONSE') from None

    @contextmanager
    def materialize(self, source):
        if isinstance(source, LocalRepositorySource):
            yield MaterializedRepository(Path(source.path), source)
            return
        metadata = self._json(f'https://api.github.com/repos/{source.owner_repo}')
        if metadata.get('private') is not False:
            raise IntakeError('PRIVATE_REPOSITORY_UNSUPPORTED')
        requested = source.ref or metadata.get('default_branch')
        if not isinstance(requested, str) or not requested or len(requested) > 256:
            raise IntakeError('INVALID_REPOSITORY_REF')
        try:
            GitHubRepositorySource(url=source.url, ref=requested)
        except ValueError:
            raise IntakeError('INVALID_REPOSITORY_REF') from None
        try:
            commit = self._json(f'https://api.github.com/repos/{source.owner_repo}/commits/{quote(requested, safe="")}')
        except IntakeError as error:
            if error.code == 'REPOSITORY_NOT_FOUND_OR_PRIVATE':
                raise IntakeError('INVALID_REPOSITORY_REF') from None
            raise
        sha = commit.get('sha')
        if not isinstance(sha, str) or not re.fullmatch(SHA_PATTERN, sha) or (re.fullmatch(SHA_PATTERN, requested) and requested != sha):
            raise IntakeError('INVALID_REPOSITORY_REF')
        # Trusted URL constructed from validated identity + server-resolved full SHA.
        data = self.fetcher.get(f'https://codeload.github.com/{source.owner_repo}/tar.gz/{sha}',
            max_bytes=self.limits.max_download_bytes, timeout=self.limits.timeout_seconds)
        with TemporaryDirectory(prefix='verisys-repository-', dir=self.temp_parent) as directory:
            root = Path(directory).resolve()
            extract_archive(data, root, self.limits)
            yield MaterializedRepository(root, GitHubRepositorySource(url=source.url, ref=sha), requested, sha)
