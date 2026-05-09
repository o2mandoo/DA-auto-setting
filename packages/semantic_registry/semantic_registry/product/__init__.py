"""Productization facades for local demos and n8n orchestration.

These modules are deterministic wrappers around Registry/contract behavior. They
never become a SQL execution surface and they do not hide explicit provider or
backend failures behind silent fallback behavior.
"""

from .baseline import (
    BaselineGenerationResult,
    BaselinePromptContext,
    BaselineProviderConfigurationError,
    BaselineRiskNote,
    BaselineSqlCandidate,
    BaselineStore,
    MockBaselineProvider,
    build_physical_schema_snapshot,
    generate_baseline_sql,
)
from .comparison import compare_baseline_vs_system_sql, profile_sql

__all__ = [
    "BaselineGenerationResult",
    "BaselinePromptContext",
    "BaselineProviderConfigurationError",
    "BaselineRiskNote",
    "BaselineSqlCandidate",
    "BaselineStore",
    "MockBaselineProvider",
    "build_physical_schema_snapshot",
    "compare_baseline_vs_system_sql",
    "generate_baseline_sql",
    "profile_sql",
]
