"""Deterministic architecture understanding from discovered source."""

from .analyzer import analyze_architecture

from .graph import project_architecture_graph

__all__ = ["analyze_architecture", "project_architecture_graph"]
