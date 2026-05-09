"""Runtime model compatibility aliases.

The concrete models live in :mod:`semantic_contracts.runtime_contracts`; this
module simply re-exports them under the Registry runtime namespace expected by
the tests and MCP/demo entry points.
"""

from __future__ import annotations

from semantic_contracts.runtime_contracts import *  # noqa: F401,F403

