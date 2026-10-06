"""`GET /connectors`: read-only description of what the server can run (Phase 3a: the offline fixture only).

Static by design: the backend never imports `geo_connectors` (ADR-0011); a test checks this list against the
connector registry. It accepts no input and discloses no host, URL, credential or provider setting; `live` is
reported as not available.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from geo_common.config import Settings
from geo_common.models._generated import ConnectorList

router = APIRouter(prefix="/connectors", tags=["connectors"])


@router.get("", response_model=ConnectorList, summary="Describe connector capability (fixtures only)")
def list_connectors(request: Request) -> ConnectorList:
    s: Settings = request.app.state.settings
    return ConnectorList.model_validate(
        {
            "mode": s.CONNECTOR_MODE,
            "live_available": False,
            "connectors": [
                {
                    "name": "fixture",
                    "kind": "fixture",
                    "enabled": s.CONNECTOR_MODE == "fixture",
                    "synthetic": True,
                    "job_types": ["catalog_search"],
                    "asset_kinds": ["scene_catalog"],
                }
            ],
        }
    )
