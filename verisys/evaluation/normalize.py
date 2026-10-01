"""Pure bounded projection of ArchitectureIR; no source reads or inference."""
import hashlib
import json
from pathlib import PurePosixPath

from verisys.architecture.graph import _id, project_architecture_graph
from verisys.models import ArchitectureIR
from .options import build_options
from .catalog import CATALOG_VERSION, DEFINITIONS
from .contracts import ArchitectureSubject, DiscoveryError, DiscoveryInput, DiscoveryLimits


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_lists(value):
    if isinstance(value, dict):
        return {key: _canonical_lists(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return sorted((_canonical_lists(item) for item in value), key=canonical)
    return value


def _objects(value):
    if isinstance(value, dict):
        return 1 + sum(_objects(item) for item in value.values())
    if isinstance(value, list):
        return sum(_objects(item) for item in value)
    return 0


def _safe_strings(value, maximum):
    if isinstance(value, str):
        return len(value) <= maximum
    if isinstance(value, dict):
        # Source paths are relative references, never local absolute filesystem paths.
        if 'file' in value and isinstance(value['file'], str) and PurePosixPath(value['file']).is_absolute():
            return False
        return all(_safe_strings(item, maximum) for item in value.values())
    if isinstance(value, list):
        return all(_safe_strings(item, maximum) for item in value)
    return True


def normalize_architecture(architecture: ArchitectureIR, *, limits: DiscoveryLimits | None = None) -> DiscoveryInput:
    limits = limits or DiscoveryLimits()
    graph = project_architecture_graph(architecture)
    routes = {_id("route", route.method, route.path, route.handler, route.source_location.file,
                  str(route.source_location.line), "none" if route.source_location.column is None else str(route.source_location.column)):
              route.model_dump(mode="json") for route in architecture.api_routes}
    records = []
    for node in graph.nodes:
        facts = {"name": node.label, "source_locations": [loc.model_dump(mode="json") for loc in node.source_locations]}
        if node.type == "API_ROUTE":
            facts = routes[node.id]
        elif node.type == "EXTERNAL_SERVICE":
            facts.update(client_library=node.subtitle, call_sites=node.metadata.get("call_sites", []))
        elif node.type == "TOOL":
            facts.update(handler=node.metadata["handler"], module=node.metadata["module"])
        elif node.type == "DATASTORE":
            facts["engine"] = node.subtitle
        records.append(ArchitectureSubject(id=node.id, kind=node.type.value, facts=_canonical_lists(facts)))
    for flow in graph.execution_flows:
        facts = flow.model_dump(mode="json")
        facts.pop("id")
        records.append(ArchitectureSubject(id=flow.id, kind="EXECUTION_FLOW", facts=_canonical_lists(facts)))
    records.sort(key=lambda record: record.id)
    if len({record.id for record in records}) != len(records):
        raise DiscoveryError("architecture_id_collision")
    root = architecture.repository_root
    limitations = sorted({text.replace(root, "[repository]") if root and root.startswith('/') else text
                          for text in graph.limitations})
    truncated = False
    kept_limits = []
    for text in limitations:
        if len(text) <= limits.max_string_chars and len(kept_limits) < limits.max_objects:
            kept_limits.append(text)
        else:
            truncated = True
    languages = sorted(set(architecture.languages))
    kept_languages = [text for text in languages[:limits.max_objects] if len(text) <= limits.max_string_chars]
    truncated |= languages != kept_languages
    result = DiscoveryInput(architecture_id="0" * 64, catalog_version=CATALOG_VERSION,
        languages=kept_languages, subjects=[], architecture_limitations=kept_limits,
        input_truncated=truncated, discovery_limitations=[],
        catalog=json.loads(canonical([entry.input_record() for entry in DEFINITIONS])))
    object_count = _objects(result.model_dump(mode="json"))
    for record in records:
        data = record.model_dump(mode="json")
        cost = _objects(data)
        if (len(result.subjects) >= limits.max_subjects or object_count + cost > limits.max_objects
                or not _safe_strings(data, limits.max_string_chars)):
            result.input_truncated = True
            continue
        result.subjects.append(record)
        if len(canonical(result.model_dump(mode="json")).encode()) + 256 > limits.max_input_bytes:
            result.subjects.pop()
            result.input_truncated = True
        else:
            object_count += cost
    # Whole flows are omitted if their component/tool references were omitted.
    known = {subject.id for subject in result.subjects if subject.kind != "EXECUTION_FLOW"}
    filtered = []
    for subject in result.subjects:
        if subject.kind == "EXECUTION_FLOW":
            steps = subject.facts["steps"]
            refs = [step.get('component_id') for step in steps if step.get('component_id')]
            refs += [identifier for step in steps for identifier in step['candidate_tool_ids']]
            if any(identifier not in known for identifier in refs):
                result.input_truncated = True
                continue
        filtered.append(subject)
    result.subjects = filtered
    if result.input_truncated:
        result.discovery_limitations = ["Discovery input was truncated; omitted facts do not establish absence."]
    # Options count toward the same budgets. Drop whole options, never identifiers.
    allowed = None
    while True:
        data = result.model_dump(mode="json")
        data.pop("architecture_id")
        data.pop("eligible_options")
        result.architecture_id = hashlib.sha256(canonical(data).encode()).hexdigest()
        options = build_options(result)
        if allowed is not None:
            options = [option for option in options if (option.evaluation_id, option.relevance_reason) in allowed]
        result.eligible_options = options
        data = result.model_dump(mode="json")
        if _objects(data) <= limits.max_objects and len(canonical(data).encode()) <= limits.max_input_bytes:
            break
        if not options:
            raise DiscoveryError("input_budget_too_small")
        allowed = {(option.evaluation_id, option.relevance_reason) for option in options[:-1]}
        result.input_truncated = True
        result.discovery_limitations = ["Discovery input was truncated; omitted facts do not establish absence."]
    return result
