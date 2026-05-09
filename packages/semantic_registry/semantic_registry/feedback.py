"""Local JSONL feedback storage for Semantic Registry Phase 1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any, Mapping
from uuid import uuid4


EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\-\s().]{7,}\d)(?!\d)")
TEXT_FIELDS = {"text", "comment", "message", "question", "answer", "feedback", "prompt", "raw_value"}


@dataclass(frozen=True)
class FeedbackReceipt:
    feedback_id: str
    path: str
    stored: bool = True

    def as_dict(self) -> dict[str, object]:
        return {"feedback_id": self.feedback_id, "path": self.path, "stored": self.stored}


class FeedbackStore:
    """Append-only local JSONL feedback store.

    Records are local files under ``.runtime/feedback`` by default. The store
    rejects obvious raw PII in free-text fields and never calls external services.
    """

    def __init__(self, root: str | Path = Path(".runtime") / "feedback"):
        self.root = Path(root)

    def save_feedback(self, record: Mapping[str, Any], space_id: str | None = None) -> FeedbackReceipt:
        if not isinstance(record, Mapping):
            raise TypeError("feedback record must be a mapping")
        payload = dict(record)
        target_space = str(space_id or payload.get("space_id") or "default")
        _validate_space_id(target_space)
        _reject_pii(payload)
        payload.setdefault("feedback_id", f"fb_{uuid4().hex}")
        payload.setdefault("created_at", datetime.now(UTC).isoformat())
        payload.setdefault("space_id", target_space)
        path = self.root / f"{target_space}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        return FeedbackReceipt(feedback_id=str(payload["feedback_id"]), path=str(path))

    def record_feedback(self, record: Mapping[str, Any], space_id: str | None = None) -> FeedbackReceipt:
        return self.save_feedback(record, space_id=space_id)

    def read_feedback(self, space_id: str) -> list[dict[str, Any]]:
        _validate_space_id(space_id)
        path = self.root / f"{space_id}.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _validate_space_id(space_id: str) -> None:
    if not space_id or any(part in space_id for part in ("/", "\\", "..")):
        raise ValueError("space_id must be a safe file stem")


def _reject_pii(value: Any, key: str | None = None) -> None:
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            _reject_pii(child_value, key=str(child_key))
        return
    if isinstance(value, list):
        for item in value:
            _reject_pii(item, key=key)
        return
    if isinstance(value, str) and (key or "").casefold() in TEXT_FIELDS:
        if EMAIL_RE.search(value) or PHONE_RE.search(value):
            raise ValueError("feedback text fields must not contain raw PII")


def save_feedback(
    record: Mapping[str, Any],
    root: str | Path = Path(".runtime") / "feedback",
    space_id: str | None = None,
) -> FeedbackReceipt:
    """Convenience API for appending one local feedback JSONL record."""

    return FeedbackStore(root).save_feedback(record, space_id=space_id)
