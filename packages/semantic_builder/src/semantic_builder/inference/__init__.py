"""Phase 5 semantic inference pipeline and PII-safe hypothesis models.

The default provider is deterministic and local-only. Optional local LLM adapters
must be explicitly enabled by callers; this package does not perform external
network calls, VDB indexing, SQL execution, or approve generated meanings by
default.
"""

from .models import (
    BusinessTermHypothesis,
    ColumnHypothesis,
    ConfidenceLevel,
    EvidenceReference,
    MetricHypothesis,
    SemanticHypothesis,
    TableHypothesis,
    Uncertainty,
)
from .pipeline import (
    DeterministicMockInferenceProvider,
    LocalProviderConfig,
    LocalSemanticInferenceProvider,
    SemanticInferenceProvider,
    generate_semantic_inference,
    load_inference_provider_config,
    load_profile_jsonl,
    write_jsonl,
)

__all__ = [
    "BusinessTermHypothesis",
    "ColumnHypothesis",
    "ConfidenceLevel",
    "DeterministicMockInferenceProvider",
    "EvidenceReference",
    "LocalProviderConfig",
    "LocalSemanticInferenceProvider",
    "MetricHypothesis",
    "SemanticHypothesis",
    "SemanticInferenceProvider",
    "TableHypothesis",
    "Uncertainty",
    "generate_semantic_inference",
    "load_inference_provider_config",
    "load_profile_jsonl",
    "write_jsonl",
]
