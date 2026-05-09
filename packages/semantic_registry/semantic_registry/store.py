"""Local file-backed Semantic Pack store."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from semantic_contracts import SemanticPack, load_pack_yaml, validate_semantic_pack

DEFAULT_PACK_ROOT = Path("semantic_packs")


@dataclass(frozen=True)
class PackSummary:
    """Metadata for a Semantic Pack discovered on disk."""

    pack_id: str
    version: str
    title: str
    status: str
    path: Path
    spaces: list[str]

    @property
    def id(self) -> str:
        return self.pack_id

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.pack_id,
            "pack_id": self.pack_id,
            "version": self.version,
            "title": self.title,
            "status": self.status,
            "path": str(self.path),
            "spaces": list(self.spaces),
        }


@dataclass(frozen=True)
class SpaceSummary:
    """Pack-level semantic-space summary for list-semantic-spaces callers."""

    space_id: str
    title: str
    version: str
    status: str
    spaces: list[str]
    pack_id: str
    path: Path

    @property
    def id(self) -> str:
        return self.space_id

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.space_id,
            "space_id": self.space_id,
            "pack_id": self.pack_id,
            "version": self.version,
            "title": self.title,
            "status": self.status,
            "path": str(self.path),
            "spaces": list(self.spaces),
        }


@dataclass(frozen=True)
class _PackFile:
    pack_id: str
    path: Path


class PackStore:
    """Load and list Semantic Packs from a local ``semantic_packs`` directory.

    Phase 1 storage is intentionally local-file only: no external database, no
    VDB, and no SQL execution. YAML files are discovered
    recursively under ``pack_root`` and are validated through
    ``semantic_contracts`` before being returned.
    """

    def __init__(self, pack_root: str | Path = DEFAULT_PACK_ROOT) -> None:
        self.pack_root = Path(pack_root)

    def load_pack(self, pack_id: str) -> SemanticPack:
        """Load and validate one Semantic Pack by id."""

        pack_file = self._find_pack_file(pack_id)
        if pack_file is None:
            raise KeyError(pack_id)
        return self._load_valid_pack(pack_file.path)

    def load_packs(self) -> list[SemanticPack]:
        """Load every valid Semantic Pack under ``pack_root``."""

        return [pack for pack, _path in self._iter_valid_packs()]

    def list_packs(self) -> list[PackSummary]:
        """Return metadata for every valid Semantic Pack under ``pack_root``."""

        return [self._summarize_pack(pack, path) for pack, path in self._iter_valid_packs()]

    def list_spaces(self) -> list[SpaceSummary]:
        """Return semantic-space summaries backed by local pack metadata."""

        return [
            SpaceSummary(
                space_id=summary.pack_id,
                title=summary.title,
                version=summary.version,
                status=summary.status,
                spaces=summary.spaces,
                pack_id=summary.pack_id,
                path=summary.path,
            )
            for summary in self.list_packs()
        ]

    def inspect_all(self) -> dict[str, object]:
        """Return deterministic local pack/card counts for smoke verification."""

        packs = self.load_packs()
        return {
            "root": str(self.pack_root),
            "pack_count": len(packs),
            "pack_ids": [pack.id for pack in packs],
            "card_counts": {
                "tables": sum(len(pack.tables) for pack in packs),
                "columns": sum(len(pack.columns) for pack in packs),
                "value_dictionaries": sum(len(pack.value_dictionaries) for pack in packs),
                "metrics": sum(len(pack.metrics) for pack in packs),
                "business_terms": sum(len(pack.business_terms) for pack in packs),
                "join_recipes": sum(len(pack.join_recipes) for pack in packs),
                "policies": sum(len(pack.policies) for pack in packs),
                "verified_queries": sum(len(pack.verified_queries) for pack in packs),
                "reverse_questions": sum(len(pack.reverse_questions) for pack in packs),
            },
            "execution_allowed": False,
        }

    def _iter_valid_packs(self) -> Iterable[tuple[SemanticPack, Path]]:
        for pack_file in self._discover_pack_files():
            try:
                yield self._load_valid_pack(pack_file.path), pack_file.path
            except ValueError:
                # Listing APIs should ignore unrelated malformed YAML, while
                # load_pack(pack_id) still raises ValueError for a selected bad pack.
                continue

    def _discover_pack_files(self) -> list[_PackFile]:
        if not self.pack_root.exists():
            return []
        discovered: list[_PackFile] = []
        for path in sorted(self.pack_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".yaml", ".yml"}:
                continue
            pack_id = self._read_pack_id(path)
            if pack_id:
                discovered.append(_PackFile(pack_id=pack_id, path=path))
        return discovered

    def _find_pack_file(self, pack_id: str) -> _PackFile | None:
        for pack_file in self._discover_pack_files():
            if pack_file.pack_id == pack_id:
                return pack_file
        return None

    def _load_valid_pack(self, path: Path) -> SemanticPack:
        try:
            pack = load_pack_yaml(path)
        except Exception as exc:  # noqa: BLE001 - normalize parser/contract errors for callers.
            raise ValueError(f"Failed to load Semantic Pack {path}: {exc}") from exc

        result = validate_semantic_pack(pack)
        if not result.valid:
            details = "; ".join(error.message for error in result.errors)
            raise ValueError(f"Invalid Semantic Pack {path}: {details}")
        return pack

    def _summarize_pack(self, pack: SemanticPack, path: Path) -> PackSummary:
        return PackSummary(
            pack_id=pack.id,
            version=pack.version,
            title=pack.title,
            status=str(pack.status),
            path=path,
            spaces=[space.id for space in pack.spaces],
        )

    def _read_pack_id(self, path: Path) -> str | None:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - selected malformed files fail in load_pack().
            return None
        if not isinstance(payload, dict):
            return None
        semantic_pack = payload.get("semantic_pack", payload)
        if not isinstance(semantic_pack, dict):
            return None
        pack_id = semantic_pack.get("id")
        return pack_id if isinstance(pack_id, str) and pack_id else None


def load_pack(pack_id: str, pack_root: str | Path = DEFAULT_PACK_ROOT) -> SemanticPack:
    return PackStore(pack_root).load_pack(pack_id)


def load_packs(pack_root: str | Path = DEFAULT_PACK_ROOT) -> list[SemanticPack]:
    return PackStore(pack_root).load_packs()


def list_packs(pack_root: str | Path = DEFAULT_PACK_ROOT) -> list[PackSummary]:
    return PackStore(pack_root).list_packs()


def list_spaces(pack_root: str | Path = DEFAULT_PACK_ROOT) -> list[SpaceSummary]:
    return PackStore(pack_root).list_spaces()


def inspect_all(pack_root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, object]:
    return PackStore(pack_root).inspect_all()
