"""Deterministic Semantic Pack query-understanding helpers.

This layer is intentionally metadata-only: it reads already loaded Semantic Packs
and never calls an LLM, DB, VDB, or SQL execution path.  Its job is to make the
retrieval decision explainable before any backend search runs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Iterable

from semantic_contracts import SemanticPack

_GENERIC_KOREAN_DOMAIN_TOKENS = {"고객", "매출", "금액", "날짜", "지역", "상품", "건수", "수량"}
_CUSTOMER_PHRASE_RE = re.compile(r"([0-9A-Za-z가-힣_./-]+\s*고객)")


@dataclass(frozen=True)
class SemanticMatch:
    card_id: str
    card_type: str
    label: str
    matched_text: str
    match_kind: str
    confidence: float = 1.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticQueryUnderstanding:
    original_query: str
    normalized_query: str
    matched_terms: list[SemanticMatch] = field(default_factory=list)
    matched_metrics: list[SemanticMatch] = field(default_factory=list)
    aliases_used: list[dict[str, str]] = field(default_factory=list)
    verified_query_matches: list[SemanticMatch] = field(default_factory=list)
    reverse_question_candidates: list[SemanticMatch] = field(default_factory=list)
    ambiguity_candidates: list[SemanticMatch] = field(default_factory=list)
    unknown_terms: list[str] = field(default_factory=list)
    recommended_card_types: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    expanded_query: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "original_query": self.original_query,
            "normalized_query": self.normalized_query,
            "matched_terms": [item.as_dict() for item in self.matched_terms],
            "matched_metrics": [item.as_dict() for item in self.matched_metrics],
            "aliases_used": list(self.aliases_used),
            "verified_query_matches": [item.as_dict() for item in self.verified_query_matches],
            "reverse_question_candidates": [item.as_dict() for item in self.reverse_question_candidates],
            "ambiguity_candidates": [item.as_dict() for item in self.ambiguity_candidates],
            "unknown_terms": list(self.unknown_terms),
            "recommended_card_types": list(self.recommended_card_types),
            "warnings": list(self.warnings),
            "expanded_query": self.expanded_query,
        }


def analyze_semantic_query(packs: Iterable[SemanticPack], query: str) -> SemanticQueryUnderstanding:
    """Return structured, deterministic query-understanding evidence."""

    pack_list = tuple(packs)
    normalized_query = normalize_query(query)
    matched_terms = _match_terms(pack_list, normalized_query)
    matched_metrics = _dedupe_matches([
        *_match_metrics(pack_list, normalized_query),
        *_match_metrics_related_to_terms(pack_list, matched_terms),
    ])
    verified_query_matches = _match_verified_queries(pack_list, normalized_query, matched_terms, matched_metrics)
    reverse_questions = _match_reverse_questions(pack_list, normalized_query, matched_terms, matched_metrics)
    ambiguities = _match_ambiguity_rules(pack_list, normalized_query, matched_terms, matched_metrics)
    aliases_used = _aliases_used(matched_terms, matched_metrics)
    unknown_terms = _unknown_domain_terms(normalized_query, matched_terms)
    recommended = _recommended_card_types(
        matched_terms=matched_terms,
        matched_metrics=matched_metrics,
        verified_query_matches=verified_query_matches,
        reverse_questions=reverse_questions,
        ambiguities=ambiguities,
        unknown_terms=unknown_terms,
    )
    warnings: list[str] = []
    if unknown_terms:
        warnings.append("unknown_or_low_confidence_domain_term")
    if not (matched_terms or matched_metrics or verified_query_matches or reverse_questions or ambiguities):
        warnings.append("no_semantic_pack_match")
    expanded_query = _expanded_query(query, matched_terms, matched_metrics, verified_query_matches, reverse_questions, ambiguities)
    return SemanticQueryUnderstanding(
        original_query=query,
        normalized_query=normalized_query,
        matched_terms=matched_terms,
        matched_metrics=matched_metrics,
        aliases_used=aliases_used,
        verified_query_matches=verified_query_matches,
        reverse_question_candidates=reverse_questions,
        ambiguity_candidates=ambiguities,
        unknown_terms=unknown_terms,
        recommended_card_types=recommended,
        warnings=_unique(warnings),
        expanded_query=expanded_query,
    )


def normalize_query(value: str) -> str:
    return " ".join(str(value).casefold().replace("_", " ").replace(".", " ").replace("-", " ").split())


def _match_terms(packs: Iterable[SemanticPack], normalized_query: str) -> list[SemanticMatch]:
    matches: list[SemanticMatch] = []
    for pack in packs:
        for term in pack.business_terms:
            candidates = [(term.term, "term"), (term.id, "id"), *[(alias, "alias") for alias in term.aliases]]
            match = _best_candidate_match(normalized_query, candidates)
            if match is None:
                continue
            matched_text, kind = match
            matches.append(SemanticMatch(term.id, "business_term", term.term, matched_text, kind, _confidence(kind)))
    return _dedupe_matches(matches)


def _match_metrics(packs: Iterable[SemanticPack], normalized_query: str) -> list[SemanticMatch]:
    matches: list[SemanticMatch] = []
    for pack in packs:
        for metric in pack.metrics:
            candidates = [(metric.label, "label"), (metric.name, "name"), (metric.id, "id")]
            if metric.description:
                candidates.append((metric.description, "description"))
            match = _best_candidate_match(normalized_query, candidates)
            if match is None:
                continue
            matched_text, kind = match
            matches.append(SemanticMatch(metric.id, "metric", metric.label, matched_text, kind, _confidence(kind)))
    return _dedupe_matches(matches)


def _match_metrics_related_to_terms(packs: Iterable[SemanticPack], matched_terms: list[SemanticMatch]) -> list[SemanticMatch]:
    """Surface metrics that a matched business term explicitly points to."""

    matched_term_ids = {item.card_id for item in matched_terms}
    if not matched_term_ids:
        return []
    related_metric_ids: set[str] = set()
    for pack in packs:
        for term in pack.business_terms:
            if term.id in matched_term_ids:
                related_metric_ids.update(term.related_metrics)
    if not related_metric_ids:
        return []
    matches: list[SemanticMatch] = []
    for pack in packs:
        for metric in pack.metrics:
            if metric.id not in related_metric_ids:
                continue
            matches.append(SemanticMatch(
                metric.id,
                "metric",
                metric.label,
                metric.id,
                "related_term",
                _confidence("related_term"),
            ))
    return _dedupe_matches(matches)


def _match_verified_queries(
    packs: Iterable[SemanticPack],
    normalized_query: str,
    matched_terms: list[SemanticMatch],
    matched_metrics: list[SemanticMatch],
) -> list[SemanticMatch]:
    term_ids = {item.card_id for item in matched_terms}
    metric_ids = {item.card_id for item in matched_metrics}
    matches: list[SemanticMatch] = []
    for pack in packs:
        for verified in pack.verified_queries:
            question_norm = normalize_query(verified.question)
            direct = question_norm and (question_norm in normalized_query or normalized_query in question_norm)
            related = bool(term_ids.intersection(verified.related_terms) or metric_ids.intersection(verified.related_metrics))
            if direct or (related and term_ids and metric_ids):
                matches.append(SemanticMatch(
                    verified.id,
                    "verified_query",
                    verified.question,
                    verified.question if direct else ",".join(sorted(term_ids | metric_ids)),
                    "question_pattern" if direct else "related_cards",
                    1.0 if direct else 0.82,
                ))
    return _dedupe_matches(matches)


def _match_reverse_questions(
    packs: Iterable[SemanticPack],
    normalized_query: str,
    matched_terms: list[SemanticMatch],
    matched_metrics: list[SemanticMatch],
) -> list[SemanticMatch]:
    target_ids = {item.card_id for item in [*matched_terms, *matched_metrics]}
    matches: list[SemanticMatch] = []
    for pack in packs:
        for question in pack.reverse_questions:
            question_norm = normalize_query(" ".join([question.question, question.reason, question.target]))
            direct = _has_meaningful_overlap(normalized_query, question_norm)
            if question.target in target_ids or direct:
                matches.append(SemanticMatch(
                    question.id,
                    "reverse_question",
                    question.question,
                    question.target if question.target in target_ids else question.question,
                    "target" if question.target in target_ids else "question_pattern",
                    0.9 if question.target in target_ids else 0.7,
                ))
    return _dedupe_matches(matches)


def _match_ambiguity_rules(
    packs: Iterable[SemanticPack],
    normalized_query: str,
    matched_terms: list[SemanticMatch],
    matched_metrics: list[SemanticMatch],
) -> list[SemanticMatch]:
    target_ids = {item.card_id for item in [*matched_terms, *matched_metrics]}
    matches: list[SemanticMatch] = []
    for pack in packs:
        for term in pack.business_terms:
            for rule in term.ambiguity_rules:
                rule_norm = normalize_query(" ".join(str(part or "") for part in (rule.target, rule.condition, rule.question, rule.required_when)))
                direct = _has_meaningful_overlap(normalized_query, rule_norm)
                if rule.target in target_ids or term.id in target_ids or direct:
                    matches.append(SemanticMatch(
                        rule.id,
                        "ambiguity_rule",
                        rule.question,
                        rule.target if rule.target in target_ids else rule.question,
                        "target" if rule.target in target_ids else "question_pattern",
                        0.86 if rule.target in target_ids else 0.68,
                    ))
    return _dedupe_matches(matches)


def _best_candidate_match(normalized_query: str, candidates: Iterable[tuple[str | None, str]]) -> tuple[str, str] | None:
    ordered: list[tuple[str, str, str]] = []
    for text, kind in candidates:
        if not text:
            continue
        normalized = normalize_query(text)
        if not normalized:
            continue
        ordered.append((normalized, str(text), kind))
    # Prefer longest exact phrase/alias match. This prevents generic tokens such
    # as "고객" from becoming confident semantic matches by themselves.
    for normalized, original, kind in sorted(ordered, key=lambda item: len(item[0]), reverse=True):
        if normalized in normalized_query:
            return original, kind
    return None


def _aliases_used(matched_terms: list[SemanticMatch], matched_metrics: list[SemanticMatch]) -> list[dict[str, str]]:
    aliases: list[dict[str, str]] = []
    for item in [*matched_terms, *matched_metrics]:
        if item.match_kind == "alias":
            aliases.append({"card_id": item.card_id, "alias": item.matched_text})
    return aliases


def _unknown_domain_terms(normalized_query: str, matched_terms: list[SemanticMatch]) -> list[str]:
    known_labels = {normalize_query(item.label) for item in matched_terms}
    known_aliases = {normalize_query(item.matched_text) for item in matched_terms}
    unknown: list[str] = []
    for match in _CUSTOMER_PHRASE_RE.finditer(normalized_query):
        phrase = normalize_query(match.group(1))
        if phrase in known_labels or phrase in known_aliases:
            continue
        if any(phrase in known or known in phrase for known in known_labels | known_aliases):
            continue
        unknown.append(phrase)
    return _unique(unknown)


def _recommended_card_types(
    *,
    matched_terms: list[SemanticMatch],
    matched_metrics: list[SemanticMatch],
    verified_query_matches: list[SemanticMatch],
    reverse_questions: list[SemanticMatch],
    ambiguities: list[SemanticMatch],
    unknown_terms: list[str],
) -> list[str]:
    types: list[str] = []
    if verified_query_matches:
        types.append("verified_query")
    if matched_terms:
        types.append("business_term")
    if matched_metrics:
        types.append("metric")
    if reverse_questions:
        types.append("reverse_question")
    if ambiguities:
        types.append("ambiguity_rule")
    if unknown_terms:
        types.append("reverse_question")
        types.append("business_term")
    return _unique(types or ["business_term", "metric", "verified_query", "reverse_question"])


def _expanded_query(query: str, *groups: list[SemanticMatch]) -> str:
    parts = [query]
    for group in groups:
        for item in group:
            parts.extend([item.card_id, item.label, item.matched_text])
    return " ".join(_unique(part for part in parts if part))


def _has_meaningful_overlap(left: str, right: str) -> bool:
    left_terms = {term for term in left.split() if term and term not in _GENERIC_KOREAN_DOMAIN_TOKENS}
    right_terms = {term for term in right.split() if term and term not in _GENERIC_KOREAN_DOMAIN_TOKENS}
    return bool(left_terms & right_terms)


def _confidence(kind: str) -> float:
    return {
        "term": 1.0,
        "label": 1.0,
        "name": 0.95,
        "alias": 0.92,
        "id": 0.82,
        "related_term": 0.74,
        "description": 0.62,
    }.get(kind, 0.7)


def _dedupe_matches(matches: Iterable[SemanticMatch]) -> list[SemanticMatch]:
    by_id: dict[str, SemanticMatch] = {}
    for item in matches:
        existing = by_id.get(item.card_id)
        if existing is None or item.confidence > existing.confidence:
            by_id[item.card_id] = item
    return sorted(by_id.values(), key=lambda item: (-item.confidence, item.card_type, item.card_id))


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


__all__ = ["SemanticMatch", "SemanticQueryUnderstanding", "analyze_semantic_query", "normalize_query"]
