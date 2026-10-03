"""Shared test isolation."""
import pytest


@pytest.fixture(autouse=True)
def isolated_result_store(tmp_path_factory, monkeypatch):
    # Saved results go to a per-test directory, never the user's ~/.verisys.
    monkeypatch.setenv("VERISYS_RESULTS_DIR", str(tmp_path_factory.mktemp("results")))
