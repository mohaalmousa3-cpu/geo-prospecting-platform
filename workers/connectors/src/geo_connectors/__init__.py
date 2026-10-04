"""Data-access connectors (ADR-0014). Data access only: no interpretation, scoring or analysis.

Phase 3a is fixtures-only: contracts, a registry and an offline fixture connector. There is no HTTP client,
no socket use and no provider configuration in this package (enforced by `tests/unit/test_architecture.py`).
"""

__version__ = "0.1.0"
