"""PII-safe column profiling for the Phase 4 file-builder MVP.

The profiler deliberately records statistics and patterns, not raw sensitive
values. It has no database, SQL execution, MCP, VDB, or LLM boundary.
"""

from .columns import (
    ColumnProfile,
    PIIDetection,
    SafeProfilerConfig,
    profile_column,
    profile_dataset,
    profile_rows,
)

__all__ = [
    "ColumnProfile",
    "PIIDetection",
    "SafeProfilerConfig",
    "profile_column",
    "profile_dataset",
    "profile_rows",
]
