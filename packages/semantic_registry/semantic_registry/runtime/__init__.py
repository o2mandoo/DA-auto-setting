"""Compatibility runtime layer over the local Semantic Registry.

The registry package owns the validation-only runtime contract used by MCP,
builder evaluation, and registry-facing tests.  This package provides the
missing Phase 8/9 compatibility surface expected by downstream callers while
staying local-only and execution-free.
"""

from .ambiguity import AmbiguityChoice, AmbiguityGate, AmbiguityWarning, evaluate_ambiguity_gate_dict
from .models import *  # noqa: F401,F403
from .query_planner import DomainQueryPlanner, RuntimeQueryPlan, SqlDraftGenerator, generate_sql_draft, plan_domain_query
from .verifiers import PolicyVerifier, SemanticVerifier, verify_policy, verify_semantics

__all__ = [
    "AmbiguityChoice",
    "AmbiguityGate",
    "AmbiguityWarning",
    "DomainQueryPlanner",
    "PolicyVerifier",
    "RuntimeQueryPlan",
    "SemanticVerifier",
    "SqlDraftGenerator",
    "evaluate_ambiguity_gate_dict",
    "generate_sql_draft",
    "plan_domain_query",
    "verify_policy",
    "verify_semantics",
]
