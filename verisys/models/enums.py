"""Distinct product, applicability, and execution vocabularies."""
from enum import StrEnum


class VerdictStatus(StrEnum):
    VERIFIED = "VERIFIED"
    VIOLATED = "VIOLATED"
    NOT_VERIFIABLE = "NOT_VERIFIABLE"


class Applicability(StrEnum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class VerificationMode(StrEnum):
    STATIC = "STATIC"
    RUNTIME = "RUNTIME"
    PERFORMANCE = "PERFORMANCE"
    INFRASTRUCTURE = "INFRASTRUCTURE"


class ExecutionStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NOT_RUN = "NOT_RUN"


class EvidenceType(StrEnum):
    CODE = "CODE"
    CONFIG = "CONFIG"
    STATIC_ANALYSIS = "STATIC_ANALYSIS"
    RUNTIME = "RUNTIME"
    TEST_RESULT = "TEST_RESULT"
    METRIC = "METRIC"


class TraceEventType(StrEnum):
    DECISION = "DECISION"
    ACTION = "ACTION"
    OBSERVATION = "OBSERVATION"
    EVIDENCE = "EVIDENCE"
    VERDICT = "VERDICT"


class ExecutionSupport(StrEnum):
    SUPPORTED = "SUPPORTED"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    PARTIAL = "PARTIAL"
