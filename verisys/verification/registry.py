"""Available execution capability; lookup never executes a verifier."""
from types import MappingProxyType
from . import http_timeout, timeout
from .run import verify_http_timeout_coverage, verify_timeout_coverage

VERIFIERS = MappingProxyType({
    timeout.POLICY_ID: verify_timeout_coverage,
    http_timeout.POLICY_ID: verify_http_timeout_coverage,
})


def get_verifier(evaluation_id):
    return VERIFIERS.get(evaluation_id)
