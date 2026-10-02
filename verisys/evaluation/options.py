"""Deterministic legal opportunities, bound to the normalized architecture hash."""
import hashlib
import json
from types import SimpleNamespace

from .catalog import DEFINITIONS
from .contracts import EligibleOption
from .rules import _rationale


def build_options(normalized):
    index = {subject.id: subject for subject in normalized.subjects}
    options = []
    for definition in DEFINITIONS:
        for code in definition.rationale_codes:
            subjects = []
            for subject in normalized.subjects:
                if subject.kind not in definition.allowed_signals or subject.kind == 'TOOL':
                    continue
                valid, *_ = _rationale(SimpleNamespace(relevance_reason=code), [subject])
                if valid:
                    subjects.append(subject)
            if not subjects:
                continue
            # Tool definitions remain supplied subjects; steps are supporting data only.
            if code == 'tool_candidates_in_workflow':
                ids = {identifier for flow in subjects for step in flow.facts['steps']
                       if step['type'] == 'TOOL_EXECUTION' for identifier in step['candidate_tool_ids']}
                subjects += [index[identifier] for identifier in sorted(ids) if identifier in index and index[identifier].kind == 'TOOL']
            subject_ids = sorted({subject.id for subject in subjects})
            identity = [normalized.architecture_id, definition.id, code, subject_ids]
            digest = hashlib.sha256(json.dumps(identity, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
            summaries = {
                'supported_openai_calls': 'Supported concrete OpenAI calls: investigate explicit per-call timeouts.',
                'openai_wrapper_presence': 'OpenAI presence without supported concrete calls: timeout scope is uncertain.',
                'supported_http_client_calls': 'Supported concrete requests/httpx calls: investigate finite timeouts.',
                'http_client_presence': 'requests/httpx presence without supported concrete calls: timeout scope is uncertain.',
                'http_api_routes': 'Detected HTTP routes: investigate latency under a defined workload; none measured.',
                'source_declared_retry_loop': 'Source-declared conditional loop: investigate repeat-action safety; actual retries unproven.',
                'tool_candidates_in_workflow': 'Workflow tool candidates: investigate potential side effects; effects and selection unproven.',
            }
            options.append(EligibleOption(option_id='option:' + digest, architecture_id=normalized.architecture_id,
                evaluation_id=definition.id, relevance_reason=code, allowed_subject_ids=subject_ids,
                architecture_summary=summaries[code]))
    return sorted(options, key=lambda option: option.option_id)
