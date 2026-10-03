"""Opt-in, model-inferred repository understanding; never verification Evidence."""
from .contracts import InferredRequirement, InferredRisk, UnderstandingResult
from .selection import SelectionLimits, select_excerpts
from .understand import understand_repository, validate_claims
from .diagram import DiagramEnrichment, enrich_diagram, validate_diagram

__all__ = ["DiagramEnrichment", "enrich_diagram", "validate_diagram", "InferredRequirement", "InferredRisk", "SelectionLimits", "UnderstandingResult",
           "select_excerpts", "understand_repository", "validate_claims"]
