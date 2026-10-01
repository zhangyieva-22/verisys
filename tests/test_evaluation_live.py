"""Opt-in only: sends normalized architecture to OpenAI, never executes verification."""
import os
from pathlib import Path

import pytest

from verisys.architecture import analyze_architecture
from verisys.repository import discover_repository
from verisys.evaluation import OpenAIClient, OpenAIConfig, discover_evaluations, normalize_architecture


@pytest.mark.skipif(os.getenv('VERISYS_LIVE_DISCOVERY') != '1', reason='Explicit live discovery opt-in required')
def test_live_evaluation_discovery():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    # All three inputs must be supplied deliberately. No implicit fixture fallback.
    repository = os.environ['VERISYS_LIVE_REPOSITORY']
    model = os.environ['VERISYS_DISCOVERY_MODEL']
    assert os.environ.get('OPENAI_API_KEY'), 'OPENAI_API_KEY must be configured outside the repository'
    architecture = analyze_architecture(discover_repository(repository))
    response = discover_evaluations(architecture, OpenAIClient(OpenAIConfig(model=model)))
    subjects = {subject.id for subject in normalize_architecture(architecture).subjects}
    assert all(set(candidate.architecture_subject_ids) <= subjects for candidate in response.candidates)
    assert response.diagnostics['provider'] == 'openai'
    assert response.diagnostics['outcome'] == 'SUCCESS'
    print(response.model_dump_json(indent=2))
