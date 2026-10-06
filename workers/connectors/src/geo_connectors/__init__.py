"""Data-access connectors (ADR-0014). Data access only: no interpretation, scoring or analysis.

Phase 3a is fixtures-only: contracts, a registry and an offline fixture connector. There is no reachable
network code and no provider configuration in this package. Phase 3b R8 added an offline egress policy and an
unregistered urllib3 transport proof of concept (`transport_urllib3.py`, the only module allowed to import
`urllib3` and `ssl`); nothing imports it (enforced by `tests/unit/test_architecture.py` and the isolation
tests).
"""

__version__ = "0.1.0"
