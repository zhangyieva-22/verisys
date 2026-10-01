"""Available execution capability; lookup never executes a verifier."""
from types import MappingProxyType
from .run import verify_timeout_coverage
from .timeout import POLICY_ID

VERIFIERS = MappingProxyType({POLICY_ID: verify_timeout_coverage})


def get_verifier(evaluation_id):
    return VERIFIERS.get(evaluation_id)
