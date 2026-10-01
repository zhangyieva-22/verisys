"""Independent evaluation discovery; no HTTP or verifier execution integration."""
from .contracts import (DiscoveryError, DiscoveryInput, DiscoveryLimits, DiscoveryResult,
                        EligibleOption, LLMSelections, StructuredGenerationClient, StructuredGenerationResult)
from .discovery import discover_evaluations
from .normalize import normalize_architecture
from .providers import OpenAIClient, OpenAIConfig

__all__ = ["discover_evaluations", "normalize_architecture", "DiscoveryError", "DiscoveryInput",
           "DiscoveryLimits", "DiscoveryResult", "EligibleOption", "LLMSelections", "StructuredGenerationClient",
           "StructuredGenerationResult", "OpenAIClient", "OpenAIConfig"]
