"""Console entrypoint for local Semantic Registry inspection.

The CLI is metadata-only: it loads Semantic Packs, searches cards, and resolves
terms. It never executes SQL and never contacts external services.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from .search import resolve_terms, search_cards
from .store import DEFAULT_PACK_ROOT, PackStore


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="semantic-registry")
    parser.add_argument("--pack-root", default=str(DEFAULT_PACK_ROOT))
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-spaces", help="List local semantic spaces")
    subparsers.add_parser("list-packs", help="List local Semantic Packs")

    search_parser = subparsers.add_parser("search", help="Search local Semantic Pack cards")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--card-type", action="append", dest="card_types")

    resolve_parser = subparsers.add_parser("resolve", help="Resolve business terms")
    resolve_parser.add_argument("terms", nargs="+")
    resolve_parser.add_argument("--space-id")

    args = parser.parse_args(argv)
    pack_root = Path(args.pack_root)
    if args.command == "list-spaces":
        return _print({"spaces": [item.as_dict() for item in PackStore(pack_root).list_spaces()]})
    if args.command == "list-packs":
        return _print({"packs": [item.as_dict() for item in PackStore(pack_root).list_packs()]})
    if args.command == "search":
        results = search_cards(args.query, card_types=args.card_types, limit=args.limit, root=pack_root)
        return _print({"results": [item.as_dict() for item in results], "execution_allowed": False})
    if args.command == "resolve":
        result = resolve_terms(args.terms, space_id=args.space_id, root=pack_root)
        return _print(result.model_dump(mode="json"))
    parser.error(f"unknown command: {args.command}")
    return 2


def _print(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - console path
    raise SystemExit(main())
