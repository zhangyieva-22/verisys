"""Local result store: reuse a saved result only when every input that determines it matches.

A result is saved after a successful operation and returned for an identical later
request instead of repeating it. The key holds every input that determines the result
(repository identity, pinned commit, architecture_id, operation parameters, model
and prompt versions); the full key is stored in the file and compared on read, so a
digest collision can never return another request's result.

Saved results are reproductions of earlier runs, not new evidence. Files live outside
repositories, are private to the user, and an unreadable or invalid file is a miss.
"""
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

STORE_VERSION = "result-store-v1"
MAX_FILE_BYTES = 4 * 1024 * 1024
KINDS = frozenset({"discovery", "verification", "understanding"})


def default_root() -> Path:
    configured = os.getenv("VERISYS_RESULTS_DIR", "").strip()
    return Path(configured).expanduser() if configured else Path.home() / ".verisys" / "results"


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class ResultStore:
    def __init__(self, root: Path | None = None):
        self.root = root if root is not None else default_root()

    def _path(self, kind: str, key: dict) -> Path:
        if kind not in KINDS:
            raise ValueError("Unknown result kind")
        digest = hashlib.sha256(_canonical([STORE_VERSION, kind, key]).encode()).hexdigest()
        return self.root / kind / f"{digest}.json"

    def get(self, kind: str, key: dict) -> tuple[dict, str] | None:
        """(payload, saved_at) for an exact key match, else None. Never raises for bad files."""
        path = self._path(kind, key)
        try:
            with path.open("rb") as handle:
                data = handle.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                return None
            record = json.loads(data)
        except (OSError, ValueError):
            return None
        if (not isinstance(record, dict) or record.get("store_version") != STORE_VERSION or record.get("kind") != kind
                or record.get("key") != json.loads(_canonical(key)) or not isinstance(record.get("payload"), dict)
                or not isinstance(record.get("saved_at"), str)):
            return None
        return record["payload"], record["saved_at"]

    def put(self, kind: str, key: dict, payload: dict) -> str | None:
        """Atomically save; returns saved_at, or None if the store is unavailable. Saving never fails a request."""
        path = self._path(kind, key)
        saved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        record = {"store_version": STORE_VERSION, "kind": kind, "key": key, "saved_at": saved_at, "payload": payload}
        encoded = _canonical(record).encode()
        if len(encoded) > MAX_FILE_BYTES:
            return None
        try:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            for directory in (self.root, path.parent):
                os.chmod(directory, 0o700)
            descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(encoded)
                os.chmod(temporary, 0o600)
                os.replace(temporary, path)
            except BaseException:
                Path(temporary).unlink(missing_ok=True)
                raise
        except OSError:
            return None
        return saved_at
