"""Function-level MCP resource payload builders.

These helpers return JSON-like dictionaries and do not depend on a live MCP
transport, SQL engine, UI runtime, vector database, or external data source.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from semantic_registry import PackStore
from semantic_registry.store import DEFAULT_PACK_ROOT

SEMANTIC_PACK_RESOURCE_URI = "semantic://packs"
SEMANTIC_PACK_BY_ID_URI_PREFIX = "semantic://packs/"
SEMANTIC_PACK_TERMS_URI_SUFFIX = "/terms"
SEMANTIC_PACK_METRICS_URI_SUFFIX = "/metrics"
SEMANTIC_PACK_POLICIES_URI_SUFFIX = "/policies"
SEMANTIC_PACK_VERIFIED_QUERIES_URI_SUFFIX = "/verified-queries"


@dataclass(frozen=True)
class PackResourceItem:
    """Stable metadata envelope returned from ``semantic://packs``."""

    space_id: str
    title: str
    version: str
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "space_id": self.space_id,
            "title": self.title,
            "version": self.version,
            "status": self.status,
        }


def _dump_model(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    if isinstance(item, dict):
        return item
    raise TypeError(f"Unsupported resource item: {type(item)!r}")


def list_packs_resource(root: str | Path = DEFAULT_PACK_ROOT) -> list[PackResourceItem]:
    """Return stable metadata envelopes for available packs."""

    return [
        PackResourceItem(
            space_id=space.space_id,
            title=space.title,
            version=space.version,
            status=space.status,
        )
        for space in PackStore(root).list_spaces()
    ]


def build_packs_resource(root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    """Build payload for ``semantic://packs``."""

    items = list_packs_resource(root)
    return {"uri": SEMANTIC_PACK_RESOURCE_URI, "count": len(items), "spaces": [item.as_dict() for item in items]}


def build_pack_resource(pack_id: str, root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    """Build payload for ``semantic://packs/{pack_id}``."""

    pack = PackStore(root).load_pack(pack_id)
    payload = pack.model_dump(mode="json")
    payload.setdefault("uri", f"{SEMANTIC_PACK_BY_ID_URI_PREFIX}{pack_id}")
    return payload


def build_pack_terms_resource(pack_id: str, root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    """Build payload for ``semantic://packs/{pack_id}/terms``."""

    pack = PackStore(root).load_pack(pack_id)
    return {
        "pack_id": pack.id,
        "version": pack.version,
        "resource_uri": f"{SEMANTIC_PACK_BY_ID_URI_PREFIX}{pack.id}{SEMANTIC_PACK_TERMS_URI_SUFFIX}",
        "terms": [_dump_model(term) for term in pack.business_terms],
    }


def build_pack_metrics_resource(pack_id: str, root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    """Build payload for ``semantic://packs/{pack_id}/metrics``."""

    pack = PackStore(root).load_pack(pack_id)
    return {
        "pack_id": pack.id,
        "version": pack.version,
        "resource_uri": f"{SEMANTIC_PACK_BY_ID_URI_PREFIX}{pack.id}{SEMANTIC_PACK_METRICS_URI_SUFFIX}",
        "metrics": [_dump_model(metric) for metric in pack.metrics],
    }


def get_pack_terms(pack_id: str, root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    return build_pack_terms_resource(pack_id, root)


def get_pack_metrics(pack_id: str, root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    return build_pack_metrics_resource(pack_id, root)


def get_pack_policies(pack_id: str, root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    """Return policy cards for ``semantic://packs/{pack_id}/policies``."""

    pack = PackStore(root).load_pack(pack_id)
    return {
        "pack_id": pack.id,
        "version": pack.version,
        "resource_uri": f"{SEMANTIC_PACK_BY_ID_URI_PREFIX}{pack.id}{SEMANTIC_PACK_POLICIES_URI_SUFFIX}",
        "policies": [_dump_model(policy) for policy in pack.policies],
    }


def get_pack_verified_queries(pack_id: str, root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    """Return verified query cards for ``semantic://packs/{pack_id}/verified-queries``."""

    pack = PackStore(root).load_pack(pack_id)
    return {
        "pack_id": pack.id,
        "version": pack.version,
        "resource_uri": f"{SEMANTIC_PACK_BY_ID_URI_PREFIX}{pack.id}{SEMANTIC_PACK_VERIFIED_QUERIES_URI_SUFFIX}",
        "verified_queries": [_dump_model(query) for query in pack.verified_queries],
    }


# Registration-friendly aliases used by server tests and MCP decorators.
def get_pack_resource(pack_id: str, root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    return build_pack_resource(pack_id, root)


def get_pack_terms_resource(pack_id: str, root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    return build_pack_terms_resource(pack_id, root)


def get_pack_metrics_resource(pack_id: str, root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    return build_pack_metrics_resource(pack_id, root)


def get_pack_policies_resource(pack_id: str, root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    return get_pack_policies(pack_id, root)


def get_pack_verified_queries_resource(pack_id: str, root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    return get_pack_verified_queries(pack_id, root)


def semantic_pack_resources(root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, dict[str, Any]]:
    """Return a resource map keyed by canonical MCP resource URI."""

    return {SEMANTIC_PACK_RESOURCE_URI: build_packs_resource(root)}


def semantic_pack_resource_uris(root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, dict[str, Any]]:
    """Return per-pack resource URI map."""

    return {
        f"{SEMANTIC_PACK_BY_ID_URI_PREFIX}{space.space_id}": build_pack_resource(space.space_id, root)
        for space in PackStore(root).list_spaces()
    }


def semantic_pack_terms_resource_uris(root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, dict[str, Any]]:
    """Return per-pack terms resource URI map."""

    return {
        f"{SEMANTIC_PACK_BY_ID_URI_PREFIX}{space.space_id}{SEMANTIC_PACK_TERMS_URI_SUFFIX}": build_pack_terms_resource(space.space_id, root)
        for space in PackStore(root).list_spaces()
    }


def semantic_pack_metrics_resource_uris(root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, dict[str, Any]]:
    """Return per-pack metrics resource URI map."""

    return {
        f"{SEMANTIC_PACK_BY_ID_URI_PREFIX}{space.space_id}{SEMANTIC_PACK_METRICS_URI_SUFFIX}": build_pack_metrics_resource(space.space_id, root)
        for space in PackStore(root).list_spaces()
    }
