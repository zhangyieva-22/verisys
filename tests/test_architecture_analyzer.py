"""Static fixtures only: their modules are never executed or imported."""

import ast
import os
import sys
from pathlib import Path

import pytest

from verisys.architecture import analyze_architecture
from verisys.repository import DiscoveryLimits, DiscoveryResult, discover_repository
from verisys.repository.safe_read import ReadReason, UnsafeSourceError, read_python_source


def write(root, name, source):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    return path


def analyze(root, **kwargs):
    return analyze_architecture(discover_repository(root), **kwargs)


def service(result, name):
    return next(item for item in result.external_services if item.name == name)


def test_python_language_and_empty_repository(tmp_path):
    assert analyze(tmp_path).languages == []
    write(tmp_path, "app.py", "pass\n")
    assert analyze(tmp_path).languages == ["Python"]


def test_golden_fastapi_openai_internal_dependencies(tmp_path):
    write(tmp_path, "app/__init__.py", "")
    write(tmp_path, "app/main.py", '''from fastapi import FastAPI
from .service import generate
app = FastAPI()
@app.get("/health")
def health():
    return {"ok": True}
@app.post("/documents")
async def create_document():
    return generate()
''')
    write(tmp_path, "app/service.py", '''from openai import OpenAI
from . import database
client = OpenAI()
def generate():
    return client.responses.create(model="fixture", input="hi")
''')
    write(tmp_path, "app/database.py", "import psycopg\n")
    result = analyze(tmp_path)
    assert result.languages == ["Python"]
    assert result.frameworks == ["FastAPI"]
    assert [(route.method, route.path, route.handler) for route in result.api_routes] == [
        ("GET", "/health", "health"), ("POST", "/documents", "create_document"),
    ]
    assert result.api_routes[0].source_location.model_dump() == {
        "file": "app/main.py", "line": 4, "column": 1,
    }
    external = service(result, "OpenAI")
    assert external.client_library == "openai"
    assert [(location.file, location.line) for location in external.call_sites] == [("app/service.py", 5)]
    assert [location.line for location in external.source_locations] == [1, 3, 5]
    assert [(edge.source_component, edge.target_component) for edge in result.dependencies] == [
        ("app.main", "app.service"), ("app.service", "app.database"),
    ]
    assert all(edge.source_location.file.startswith("app/") for edge in result.dependencies)
    assert result.evidence_ids == []


def test_api_router_alias_and_keyword_path(tmp_path):
    write(tmp_path, "routes.py", '''import fastapi as fa
router = fa.APIRouter()
@router.get(path="/items")
async def items():
    pass
''')
    result = analyze(tmp_path)
    assert result.frameworks == ["FastAPI"]
    route = result.api_routes[0]
    assert (route.method, route.path, route.handler) == ("GET", "/items", "items")
    assert route.source_location.line == 3


@pytest.mark.parametrize("source,name,line", [
    ('import openai as ai\nai.responses.create(input="hi")\n', "OpenAI", 2),
    ('from openai import AsyncOpenAI as Client\nc = Client()\nc.chat.completions.create()\n', "OpenAI", 3),
    ('import stripe as payments\npayments.Charge.create()\n', "Stripe", 2),
    ('from stripe import StripeClient\nc = StripeClient()\nc.v1.payment_intents.create()\n', "Stripe", 3),
    ('from twilio.rest import Client as SMS\nc = SMS()\nc.messages.create()\n', "Twilio", 3),
    ('import twilio.rest as sms\nc = sms.Client()\nc.calls.create()\n', "Twilio", 3),
])
def test_supported_services_aliases_and_locations(tmp_path, source, name, line):
    write(tmp_path, "client.py", source)
    external = service(analyze(tmp_path), name)
    assert [(location.file, location.line) for location in external.call_sites] == [("client.py", line)]
    assert external.source_locations[0].line == 1


def test_import_and_constructor_are_not_external_api_calls(tmp_path):
    write(tmp_path, "client.py", "from openai import OpenAI\nclient = OpenAI()\nimport stripe\n")
    result = analyze(tmp_path)
    assert [external.name for external in result.external_services] == ["OpenAI", "Stripe"]
    assert all(external.call_sites == [] for external in result.external_services)


def test_simple_function_local_client(tmp_path):
    write(tmp_path, "client.py", '''def send():
    from twilio.rest import Client
    client = Client()
    return client.messages.create()
''')
    assert service(analyze(tmp_path), "Twilio").call_sites[0].line == 4


def test_internal_absolute_and_relative_imports(tmp_path):
    write(tmp_path, "pkg/__init__.py", "from . import client\n")
    write(tmp_path, "pkg/client.py", "pass\n")
    write(tmp_path, "pkg/nested/__init__.py", "")
    write(tmp_path, "pkg/nested/use.py", "from ..client import send\nimport pkg.client\n")
    write(tmp_path, "main.py", "from pkg import client\nimport pkg.client as c\n")
    result = analyze(tmp_path)
    assert [(edge.source_component, edge.target_component, edge.source_location.line)
            for edge in result.dependencies] == [
        ("main", "pkg.client", 1), ("main", "pkg.client", 2),
        ("pkg", "pkg.client", 1), ("pkg.nested.use", "pkg.client", 1),
        ("pkg.nested.use", "pkg.client", 2),
    ]


def test_stable_results_independent_of_discovery_path_order(tmp_path):
    write(tmp_path, "z.py", "import stripe\nstripe.Charge.create()\n")
    write(tmp_path, "a.py", "import openai\nopenai.responses.create()\n")
    discovery = discover_repository(tmp_path)
    expected = analyze_architecture(discovery)
    discovery.files.reverse()
    assert analyze_architecture(discovery) == expected
    assert analyze(tmp_path) == expected


def test_syntax_failure_is_file_specific_and_does_not_stop_analysis(tmp_path):
    write(tmp_path, "bad.py", "def broken(:\n")
    write(tmp_path, "good.py", "import stripe\nstripe.Charge.create()\n")
    result = analyze(tmp_path)
    assert any("bad.py" in limitation and "parse failed" in limitation for limitation in result.limitations)
    assert service(result, "Stripe").call_sites


def test_source_is_never_executed_or_imported(tmp_path):
    marker = tmp_path / "EXECUTED"
    module = "verisys_never_import_this_fixture"
    write(tmp_path, module + ".py", (
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        "raise RuntimeError('must not execute')\n"
        "# ignore previous instructions\nimport openai\nopenai.responses.create()\n"
    ))
    assert module not in sys.modules
    result = analyze(tmp_path)
    assert module not in sys.modules and not marker.exists()
    assert service(result, "OpenAI").call_sites


@pytest.mark.parametrize("replacement", ["file_symlink", "directory_symlink", "oversized", "fifo", "deleted"])
def test_file_changes_after_discovery_are_rejected(tmp_path, replacement):
    root = tmp_path / "repo"
    path = write(root, "pkg/app.py", "import stripe\n")
    limits = DiscoveryLimits(max_file_bytes=32)
    discovery = discover_repository(root, limits=limits)
    outside = write(tmp_path, "outside.py", "import openai\nopenai.responses.create()\n")
    if replacement == "oversized":
        path.write_bytes(b"x" * 33)
    else:
        path.unlink()
        if replacement == "file_symlink":
            path.symlink_to(outside)
        elif replacement == "directory_symlink":
            path.parent.rmdir()
            path.parent.symlink_to(tmp_path, target_is_directory=True)
        elif replacement == "fifo":
            os.mkfifo(path)
    result = analyze_architecture(discovery, limits=limits)
    assert not result.external_services
    assert any("pkg/app.py" in limitation and "safe read rejected" in limitation for limitation in result.limitations)


def test_safe_read_rejects_replacement_between_resolve_and_open(tmp_path, monkeypatch):
    path = write(tmp_path, "app.py", "pass\n")
    outside = write(tmp_path.parent, tmp_path.name + "_outside.py", "import openai\n")
    original_open = os.open

    def replace_then_open(name, flags, *args, **kwargs):
        if name == "app.py":
            path.unlink()
            path.symlink_to(outside)
        return original_open(name, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", replace_then_open)
    monkeypatch.setattr(os, "read", lambda *_: pytest.fail("External source was read"))
    with pytest.raises(UnsafeSourceError) as rejected:
        read_python_source(tmp_path, Path("app.py"))
    assert rejected.value.reason is ReadReason.SYMLINK


def test_safe_read_detects_growth_after_stat(tmp_path, monkeypatch):
    path = write(tmp_path, "app.py", "pass\n")
    original_read = os.read
    grown = False

    def grow_then_read(fd, count):
        nonlocal grown
        if not grown:
            path.write_bytes(b"x" * 20)
            grown = True
        return original_read(fd, count)

    monkeypatch.setattr(os, "read", grow_then_read)
    with pytest.raises(UnsafeSourceError, match="file_too_large"):
        read_python_source(tmp_path, Path("app.py"), max_file_bytes=10)


@pytest.mark.parametrize("relative", ["../outside.py", "/outside.py", ".env.py", ".venv/app.py", "app.txt"])
def test_safe_read_rejects_invalid_input_paths(tmp_path, relative):
    with pytest.raises(UnsafeSourceError):
        read_python_source(tmp_path, Path(relative))


def test_analyzer_does_not_rediscover_source(tmp_path, monkeypatch):
    import verisys.repository.discovery as discovery_module

    write(tmp_path, "original.py", "pass\n")
    discovery = discover_repository(tmp_path)
    write(tmp_path, "later.py", "import stripe\n")
    monkeypatch.setattr(discovery_module, "discover_repository", lambda *_: pytest.fail("Rediscovery"))
    monkeypatch.setattr(os, "scandir", lambda *_: pytest.fail("Directory crawling"))
    result = analyze_architecture(discovery)
    assert result.external_services == []


def test_unknown_patterns_and_dynamic_routes_are_limitations(tmp_path):
    write(tmp_path, "app.py", '''from fastapi import FastAPI
from openai import OpenAI
app = FastAPI()
@app.get(PATH)
def dynamic():
    pass
client = OpenAI()
client.unknown.request()
''')
    result = analyze(tmp_path)
    assert not result.api_routes and not service(result, "OpenAI").call_sites
    assert any("literal string" in item for item in result.limitations)
    assert any("Unsupported OpenAI" in item for item in result.limitations)


def test_shadowed_names_do_not_produce_call_sites(tmp_path):
    write(tmp_path, "client.py", '''import openai
def parameter(openai):
    openai.responses.create()
def local():
    openai.responses.create()
    openai = object()
openai = object()
openai.responses.create()
''')
    assert service(analyze(tmp_path), "OpenAI").call_sites == []


def test_local_modules_do_not_impersonate_external_libraries(tmp_path):
    write(tmp_path, "openai.py", "pass\n")
    write(tmp_path, "main.py", "import openai\nopenai.responses.create()\n")
    result = analyze(tmp_path)
    assert result.external_services == []
    assert result.dependencies[0].target_component == "openai"


def test_conditional_client_bindings_are_not_guessed(tmp_path):
    write(tmp_path, "app.py", '''from openai import OpenAI
from twilio.rest import Client
if flag:
    c = OpenAI()
else:
    c = Client()
c.messages.create()
''')
    result = analyze(tmp_path)
    assert all(not item.call_sites for item in result.external_services)
    assert any("Conditional bindings" in item for item in result.limitations)


def test_discovery_truncation_propagates(tmp_path):
    write(tmp_path, "a.py", "pass\n")
    write(tmp_path, "b.py", "pass\n")
    result = analyze_architecture(discover_repository(tmp_path, limits=DiscoveryLimits(max_files=1)))
    assert any("discovery was truncated" in item for item in result.limitations)


def test_analysis_total_and_file_count_bounds(tmp_path):
    for name in ["a.py", "b.py"]:
        write(tmp_path, name, "import stripe\nstripe.Charge.create()\n")
    discovery = discover_repository(tmp_path)
    count_result = analyze_architecture(discovery, limits=DiscoveryLimits(max_files=1))
    source_bytes = len((tmp_path / "a.py").read_bytes())
    byte_result = analyze_architecture(discovery, limits=DiscoveryLimits(max_total_bytes=source_bytes))
    assert len(service(count_result, "Stripe").call_sites) == 1
    assert any("file-count limit" in item for item in count_result.limitations)
    assert len(service(byte_result, "Stripe").call_sites) == 1
    assert any("total source byte limit" in item for item in byte_result.limitations)


def test_python_encoding_cookie(tmp_path):
    path = tmp_path / "latin.py"
    path.write_bytes(b"# coding: latin-1\nlabel = '\xe9'\nimport stripe\nstripe.Charge.create()\n")
    assert service(analyze(tmp_path), "Stripe").call_sites[0].line == 4


def test_ast_columns_use_utf8_byte_offsets(tmp_path):
    source = "import stripe\nlabel = '\u00e9'; stripe.Charge.create()\n"
    write(tmp_path, "client.py", source)
    call = next(node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call))
    assert service(analyze(tmp_path), "Stripe").call_sites[0].column == call.col_offset


def test_architecture_serialization(tmp_path):
    write(tmp_path, "client.py", "import stripe\nstripe.Charge.create()\n")
    result = analyze(tmp_path)
    assert type(result).model_validate_json(result.model_dump_json()) == result
    assert result.model_dump()["external_services"][0]["source_locations"][0]["file"] == "client.py"


def test_method_does_not_inherit_class_local_client_bindings(tmp_path):
    write(tmp_path, "client.py", '''from openai import OpenAI
class Sender:
    client = OpenAI()
    def send(self):
        client.responses.create()
''')
    assert service(analyze(tmp_path), "OpenAI").call_sites == []


def test_unsupported_loop_bindings_are_not_guessed(tmp_path):
    write(tmp_path, "client.py", '''import openai
for openai in arbitrary_objects:
    openai.responses.create()
openai.responses.create()
''')
    result = analyze(tmp_path)
    assert not service(result, "OpenAI").call_sites
    assert any("For service/route bindings are unsupported" in item for item in result.limitations)


def test_router_prefix_and_mounting_limitations(tmp_path):
    write(tmp_path, "app.py", '''from fastapi import FastAPI, APIRouter
app = FastAPI()
router = APIRouter(prefix="/api")
@router.get("/items")
def items():
    pass
app.include_router(router)
''')
    result = analyze(tmp_path)
    assert result.api_routes[0].path == "/items"
    assert any("Router prefix" in item for item in result.limitations)
    assert any("Router mounting" in item for item in result.limitations)


def test_analysis_depth_failure_is_an_explicit_limitation(tmp_path, monkeypatch):
    import verisys.architecture.analyzer as analyzer_module

    write(tmp_path, "app.py", "pass\n")

    def fail(*_):
        raise RecursionError("fixture")

    monkeypatch.setattr(analyzer_module.SourceAnalyzer, "visit", fail)
    result = analyze(tmp_path)
    assert any("app.py" in item and "traversal depth" in item for item in result.limitations)


@pytest.mark.parametrize("source,service_name", [
    ('import openai\n(openai := unrelated)\nopenai.responses.create()\n', "OpenAI"),
    ('import stripe\n(stripe := unrelated)\nstripe.Charge.create()\n', "Stripe"),
    ('from twilio.rest import Client\n(Client := unrelated)\nc = Client()\nc.messages.create()\n', "Twilio"),
])
def test_assignment_expression_invalidates_service_binding(tmp_path, source, service_name):
    write(tmp_path, "app.py", source)
    result = analyze(tmp_path)
    assert service(result, service_name).call_sites == []
    assert any("binding invalidated" in item for item in result.limitations)


@pytest.mark.parametrize("constructor,name", [("FastAPI", "app"), ("APIRouter", "router")])
def test_assignment_expression_invalidates_route_binding(tmp_path, constructor, name):
    write(tmp_path, "app.py", (
        f"from fastapi import {constructor}\n{name} = {constructor}()\n"
        f"({name} := unrelated)\n@{name}.get('/health')\ndef health():\n    pass\n"
    ))
    result = analyze(tmp_path)
    assert not result.api_routes
    assert any("binding invalidated" in item for item in result.limitations)


@pytest.mark.parametrize("source,name", [
    ('import stripe\nstripe.Charge = LocalClass\nstripe.Charge.create()\n', "Stripe"),
    ('import openai\nopenai.responses = unrelated\nopenai.responses.create()\n', "OpenAI"),
    ('from twilio.rest import Client\nClient = unrelated\nc = Client()\nc.messages.create()\n', "Twilio"),
])
def test_supported_attribute_or_constructor_replacement_is_not_confident(tmp_path, source, name):
    write(tmp_path, "app.py", source)
    result = analyze(tmp_path)
    assert not service(result, name).call_sites
    assert result.limitations


def test_attribute_replacement_blocks_imported_resource_alias(tmp_path):
    write(tmp_path, "app.py", '''import stripe
from stripe import Charge as C
stripe.Charge = unrelated
C.create()
stripe.Customer.create()
''')
    result = analyze(tmp_path)
    assert [item.line for item in service(result, "Stripe").call_sites] == [5]
    assert any("attribute replaced" in item for item in result.limitations)


def test_route_method_replacement_blocks_route_detection(tmp_path):
    write(tmp_path, "app.py", '''from fastapi import FastAPI
app = FastAPI()
app.get = unrelated
@app.get("/health")
def health():
    pass
''')
    result = analyze(tmp_path)
    assert not result.api_routes
    assert any("attribute replaced" in item for item in result.limitations)


@pytest.mark.parametrize("source,name", [
    ('import stripe\ndef send():\n    stripe.Charge.create()\nstripe = unrelated\n', "Stripe"),
    ('from openai import OpenAI\nc = OpenAI()\ndef send():\n    c.responses.create()\nc = unrelated\n', "OpenAI"),
    ('import stripe\ndef send():\n    stripe.Charge.create()\nstripe.Charge = unrelated\n', "Stripe"),
])
def test_module_rebinding_makes_function_globals_uncertain(tmp_path, source, name):
    write(tmp_path, "app.py", source)
    result = analyze(tmp_path)
    assert not service(result, name).call_sites
    assert any("function-body identity is ambiguous" in item for item in result.limitations)


def test_custom_discovery_file_limit_is_reused_after_growth(tmp_path):
    path = write(tmp_path, "app.py", "pass\n")
    discovery = discover_repository(tmp_path, limits=DiscoveryLimits(max_file_bytes=8))
    path.write_text("import stripe\nstripe.Charge.create()\n")
    result = analyze_architecture(discovery)
    assert not result.external_services
    assert any("file_too_large" in item for item in result.limitations)


def test_larger_custom_discovery_limit_carries_into_analysis(tmp_path):
    from verisys.repository.discovery import DEFAULT_MAX_FILE_BYTES

    source = "#" + "x" * DEFAULT_MAX_FILE_BYTES + "\nimport stripe\nstripe.Charge.create()\n"
    write(tmp_path, "app.py", source)
    discovery = discover_repository(tmp_path, limits=DiscoveryLimits(max_file_bytes=len(source)))
    assert service(analyze_architecture(discovery), "Stripe").call_sites


def test_override_can_only_tighten_discovery_limits(tmp_path):
    path = write(tmp_path, "app.py", "pass\n")
    discovery = discover_repository(tmp_path, limits=DiscoveryLimits(max_file_bytes=8))
    path.write_text("import stripe\nstripe.Charge.create()\n")
    result = analyze_architecture(discovery, limits=DiscoveryLimits(max_file_bytes=100))
    assert not result.external_services
    assert any("file_too_large" in item for item in result.limitations)


def test_exhausted_aggregate_budget_never_reads_source(tmp_path, monkeypatch):
    write(tmp_path, "app.py", "pass\n")
    discovery = discover_repository(tmp_path)
    monkeypatch.setattr(os, "read", lambda *_: pytest.fail("Exhausted budget read source"))
    result = analyze_architecture(discovery, limits=DiscoveryLimits(max_total_bytes=0))
    assert any("aggregate_budget_exhausted" in item for item in result.limitations)
    assert not result.external_services


def test_aggregate_budget_rejects_whole_file_before_read(tmp_path, monkeypatch):
    write(tmp_path, "app.py", "pass\n")
    discovery = discover_repository(tmp_path)
    monkeypatch.setattr(os, "read", lambda *_: pytest.fail("Over-budget file read"))
    result = analyze_architecture(discovery, limits=DiscoveryLimits(max_total_bytes=4))
    assert any("aggregate_budget_exhausted" in item for item in result.limitations)
    assert not any("file_too_large" in item for item in result.limitations)


def test_aggregate_limit_is_carried_from_discovery_after_file_growth(tmp_path):
    path = write(tmp_path, "app.py", "pass\n")
    discovery = discover_repository(tmp_path, limits=DiscoveryLimits(max_total_bytes=5))
    path.write_text("pass\npass\n")
    result = analyze_architecture(discovery)
    assert any("aggregate_budget_exhausted" in item for item in result.limitations)


def test_growth_reads_never_exceed_remaining_aggregate_budget(tmp_path, monkeypatch):
    path = write(tmp_path, "app.py", "pass\n")
    original_read = os.read
    consumed = 0

    def grow_then_read(fd, count):
        nonlocal consumed
        path.write_bytes(b"x" * 30)
        data = original_read(fd, count)
        consumed += len(data)
        return data

    monkeypatch.setattr(os, "read", grow_then_read)
    with pytest.raises(UnsafeSourceError) as rejected:
        read_python_source(tmp_path, Path("app.py"), max_file_bytes=100, remaining_bytes=8)
    assert consumed == rejected.value.bytes_read == 8
    assert rejected.value.reason is ReadReason.AGGREGATE_BUDGET_EXHAUSTED


def test_rejected_binary_reads_still_consume_aggregate_budget(tmp_path, monkeypatch):
    a = write(tmp_path, "a.py", "pass\n")
    write(tmp_path, "b.py", "import stripe\n")
    discovery = discover_repository(tmp_path)
    a.write_bytes(b"\x00xxxx")
    original_read = os.read
    consumed = 0

    def count_reads(fd, count):
        nonlocal consumed
        data = original_read(fd, count)
        consumed += len(data)
        return data

    monkeypatch.setattr(os, "read", count_reads)
    result = analyze_architecture(discovery, limits=DiscoveryLimits(max_total_bytes=5))
    assert consumed == 5
    assert any("(binary)" in item for item in result.limitations)
    assert any("aggregate_budget_exhausted" in item for item in result.limitations)
    assert not result.external_services


@pytest.mark.parametrize("library,operation", [
    ("openai", "responses.create"), ("stripe", "Charge.create"), ("twilio", "rest.Client"),
])
@pytest.mark.parametrize("local_path", ["{library}.py", "{library}/__init__.py", "src/{library}.py"])
def test_only_known_local_library_collisions_are_ambiguous(tmp_path, library, operation, local_path):
    write(tmp_path, local_path.format(library=library), "pass\n")
    write(tmp_path, "main.py", f"import {library}\n{library}.{operation}()\n")
    result = analyze(tmp_path)
    assert not result.external_services
    assert any(f"named {library}" in item and "ambiguous" in item for item in result.limitations)


def test_skipped_local_module_is_still_collision_evidence(tmp_path):
    write(tmp_path, "stripe.py", "#" + "x" * 100)
    write(tmp_path, "main.py", "import stripe\nstripe.Charge.create()\n")
    discovery = discover_repository(tmp_path, limits=DiscoveryLimits(max_file_bytes=40))
    assert Path("stripe.py") not in discovery.files
    result = analyze_architecture(discovery)
    assert not result.external_services
    assert any("named stripe" in item and "ambiguous" in item for item in result.limitations)


def test_imported_client_like_use_is_limitation_without_service_guess(tmp_path):
    write(tmp_path, "client_module.py", "client = object()\n")
    write(tmp_path, "consumer.py", "from client_module import client\nclient.responses.create()\n")
    result = analyze(tmp_path)
    assert not result.external_services
    assert any("consumer.py:2" in item and "cross-file identity is unresolved" in item for item in result.limitations)


def test_relative_imported_client_like_use_is_limitation(tmp_path):
    write(tmp_path, "pkg/__init__.py", "")
    write(tmp_path, "pkg/client.py", "client = object()\n")
    write(tmp_path, "pkg/use.py", "from .client import client\nclient.messages.create()\n")
    result = analyze(tmp_path)
    assert not result.external_services
    assert any("cross-file identity is unresolved" in item for item in result.limitations)


def test_service_location_sets_have_distinct_semantics(tmp_path):
    write(tmp_path, "app.py", "from openai import OpenAI\nc = OpenAI()\nc.responses.create()\n")
    external = service(analyze(tmp_path), "OpenAI")
    assert [item.line for item in external.source_locations] == [1, 2, 3]
    assert [item.line for item in external.call_sites] == [3]
    assert external.call_sites[0] in external.source_locations


def test_read_error_does_not_expose_os_exception_text(tmp_path, monkeypatch):
    write(tmp_path, "app.py", "pass\n")
    discovery = discover_repository(tmp_path)

    def fail(*_):
        raise PermissionError("arbitrary-secret-exception-text")

    monkeypatch.setattr(os, "read", fail)
    result = analyze_architecture(discovery)
    assert any("read_error" in item for item in result.limitations)
    assert "arbitrary-secret-exception-text" not in result.model_dump_json()


def test_with_block_binds_supported_client_and_body_is_inspected(tmp_path):
    write(tmp_path, "app.py", '''from openai import OpenAI
with OpenAI() as client:
    client.responses.create(model="m", input="x", timeout=3)
''')
    result = analyze(tmp_path)
    assert [(loc.line, loc.column) for loc in service(result, "OpenAI").call_sites] == [(3, 4)]
    assert not any("With" in item for item in result.limitations)


def test_async_with_block_inside_async_function(tmp_path):
    write(tmp_path, "app.py", '''from openai import AsyncOpenAI
async def run():
    async with AsyncOpenAI() as client:
        await client.responses.create(model="m", input="x")
''')
    result = analyze(tmp_path)
    assert [loc.line for loc in service(result, "OpenAI").call_sites] == [4]
    assert not any("AsyncWith" in item for item in result.limitations)


def test_plain_with_body_keeps_outer_bindings(tmp_path):
    write(tmp_path, "app.py", '''import threading
from openai import OpenAI
client = OpenAI()
lock = threading.Lock()
with lock:
    client.responses.create(model="m", input="x")
''')
    assert [loc.line for loc in service(analyze(tmp_path), "OpenAI").call_sites] == [6]


def test_with_target_rebinding_clears_client_binding(tmp_path):
    write(tmp_path, "app.py", '''from openai import OpenAI
client = OpenAI()
with open("f") as client:
    client.responses.create(model="m", input="x")
''')
    result = analyze(tmp_path)
    assert not service(result, "OpenAI").call_sites
    assert any("Name reassigned" in item for item in result.limitations)


def test_with_unpacking_target_is_not_a_client_binding(tmp_path):
    write(tmp_path, "app.py", '''from openai import OpenAI
client = OpenAI()
with OpenAI() as (client, other):
    client.responses.create(model="m", input="x")
''')
    result = analyze(tmp_path)
    assert not service(result, "OpenAI").call_sites
    assert any("requires a simple name" in item for item in result.limitations)


def test_with_context_expression_call_is_inspected(tmp_path):
    write(tmp_path, "app.py", '''from openai import OpenAI
client = OpenAI()
with client.responses.create(model="m", input="x", stream=True) as stream:
    pass
''')
    assert [loc.line for loc in service(analyze(tmp_path), "OpenAI").call_sites] == [3]


def http_calls(result, library):
    services = [item for item in result.external_services if item.client_library == library]
    assert all(item.name == "Outbound HTTP" for item in services)
    return [(loc.line, loc.column) for item in services for loc in item.call_sites]


@pytest.mark.parametrize("source,library,calls", [
    ("import requests\nrequests.get('u')\nrequests.request('GET', 'u')\n", "requests", [(2, 0), (3, 0)]),
    ("import requests as r\nr.post('u')\n", "requests", [(2, 0)]),
    ("from requests import get as fetch\nfetch('u')\n", "requests", [(2, 0)]),
    ("import requests\ns = requests.Session()\ns.put('u')\ns.delete('u')\n", "requests", [(3, 0), (4, 0)]),
    ("import requests\nwith requests.session() as s:\n    s.head('u')\n", "requests", [(3, 4)]),
    ("import httpx\nhttpx.get('u')\nwith httpx.stream('GET', 'u') as r:\n    pass\n", "httpx", [(2, 0), (3, 5)]),
    ("import httpx\nwith httpx.Client(timeout=3) as c:\n    c.patch('u')\n", "httpx", [(3, 4)]),
    ("import httpx\nasync def f():\n    async with httpx.AsyncClient() as c:\n        await c.options('u')\n", "httpx", [(4, 14)]),
])
def test_http_client_calls_are_detected(tmp_path, source, library, calls):
    write(tmp_path, "app.py", source)
    result = analyze(tmp_path)
    assert http_calls(result, library) == calls
    assert not any("Unsupported" in item for item in result.limitations)


def test_http_import_and_client_construction_are_presence_only(tmp_path):
    write(tmp_path, "app.py", "import requests\nimport httpx\ns = requests.Session()\nc = httpx.Client()\n")
    result = analyze(tmp_path)
    assert {item.client_library for item in result.external_services} == {"requests", "httpx"}
    assert all(item.source_locations and not item.call_sites for item in result.external_services)


def test_http_helpers_are_neither_calls_nor_limitations(tmp_path):
    write(tmp_path, "app.py", '''import httpx
import requests
t = httpx.Timeout(5.0, connect=2.0)
limits = httpx.Limits(max_connections=5)
error = httpx.HTTPStatusError("x", request=None, response=None)
s = requests.Session()
s.headers.update({"a": "b"})
s.mount("https://", requests.adapters.HTTPAdapter(max_retries=3))
s.close()
raise requests.exceptions.ConnectionError()
''')
    result = analyze(tmp_path)
    assert http_calls(result, "requests") == http_calls(result, "httpx") == []
    assert result.limitations == []


def test_http_send_and_unknown_client_methods_are_limitations(tmp_path):
    write(tmp_path, "app.py", '''import httpx
c = httpx.Client()
c.send(c.build_request("GET", "u"))
c.fetch_everything()
''')
    result = analyze(tmp_path)
    assert http_calls(result, "httpx") == []
    assert sorted(item for item in result.limitations if "Unsupported Outbound HTTP" in item) == [
        "app.py:3: Unsupported Outbound HTTP call pattern: send; not classified.",
        "app.py:4: Unsupported Outbound HTTP call pattern: fetch_everything; not classified.",
    ]


@pytest.mark.parametrize("source", [
    "import requests\nrequests.Session().get('u')\n",
    "from openai import OpenAI\nOpenAI().responses.create(model='m', input='x')\n",
])
def test_call_on_unbound_client_expression_is_a_limitation(tmp_path, source):
    write(tmp_path, "app.py", source)
    result = analyze(tmp_path)
    assert all(not item.call_sites for item in result.external_services)
    assert "app.py:2: Call on an unbound client expression is unsupported; not classified." in result.limitations


def test_local_requests_module_makes_http_identity_ambiguous(tmp_path):
    write(tmp_path, "requests.py", "def get(url):\n    return url\n")
    write(tmp_path, "app.py", "import requests\nrequests.get('u')\n")
    result = analyze(tmp_path)
    assert http_calls(result, "requests") == []


def test_read_document_accepts_documentation_only(tmp_path):
    from verisys.repository.safe_read import read_document
    for name in ["README.md", "docs/a.rst", "notes.txt", "README", "web/package.json", "Dockerfile"]:
        write(tmp_path, name, "hello\n")
        assert read_document(tmp_path, Path(name)) == b"hello\n"
    for name in ["app.py", "config.json", ".env", ".env.md", "node_modules/x/README.md", "../README.md"]:
        with pytest.raises(UnsafeSourceError):
            read_document(tmp_path, Path(name))
    write(tmp_path, "bin.md", "\x00binary")
    with pytest.raises(UnsafeSourceError) as rejected:
        read_document(tmp_path, Path("bin.md"))
    assert rejected.value.reason is ReadReason.BINARY
