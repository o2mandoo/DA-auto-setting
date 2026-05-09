"""Compatibility runtime facade over the local Semantic Registry.

This package keeps the Phase 8/11 runtime imports working without introducing a
new execution engine. It re-exports the structured runtime contract models and
wraps the existing Registry planner/guard logic in a small, validation-only
facade.
"""

from __future__ import annotations

from .ambiguity import AmbiguityGate, evaluate_ambiguity_gate_dict
from .models import *  # noqa: F401,F403
from .query_planner import DomainQueryPlanner, SqlDraftGenerator, generate_sql_draft, plan_domain_query
from .verifiers import PolicyVerifier, SemanticVerifier, verify_policy, verify_semantics

__all__ = [
    "AmbiguityGate",
    "DomainQueryPlanner",
    "PolicyVerifier",
    "SemanticVerifier",
    "SqlDraftGenerator",
    "evaluate_ambiguity_gate_dict",
    "generate_sql_draft",
    "plan_domain_query",
    "verify_policy",
    "verify_semantics",
]
