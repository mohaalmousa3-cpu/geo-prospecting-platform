"""Request rules for `catalog_search` jobs (Phase 3a: fixtures only; ADR-0014, ADR-0008).

The API validates the *shape and limits* of a request and stores the normalised payload. It never imports
`geo_connectors` (ADR-0011: the backend does not depend on workers); the worker's handler re-checks the
same limits (`FetchContext.validate`), and a parity test asserts that every payload accepted here is also
accepted there.

The public payload deliberately has no dataset, fixture, provider, host or cache option. Which connector
answers is decided by the server's `CONNECTOR_MODE`, never by the request. The AOI is the only target, and the
project is derived from it in the queue layer (ADR-0014 §7.4).

The numeric caps below are provisional operational safeguards (ADR-0008), not scientific thresholds.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.errors import ApiError
from geo_common.config import Settings

MAX_COLLECTIONS = 10  # provisional: bounds the request size independently of the body cap
_COLLECTION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CatalogSearchPayload(BaseModel):
    """Exactly these keys; anything else (including `project_id`, `fixture`, `provider`) is rejected."""

    model_config = ConfigDict(extra="forbid", strict=True)
    start: str
    end: str
    collections: list[str] = Field(min_length=1, max_length=MAX_COLLECTIONS)
    max_items: int | None = Field(default=None, ge=1)


def _fail(message: str) -> ApiError:
    return ApiError(422, "validation_error", f"invalid catalog_search payload: {message}")


def _day(name: str, value: str) -> date:
    if not _ISO_DATE.fullmatch(value):
        raise _fail(f"{name} must be an ISO date (YYYY-MM-DD)")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise _fail(f"{name} is not a valid calendar date") from None


def validate_catalog_payload(raw: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Return the normalised payload to store, or raise `ApiError(422, "validation_error")`.

    Normalisation makes every default explicit (nothing is silently filled in later): collections are sorted
    and de-duplicated, `max_items` is always present. Requests above a limit are rejected, never clamped.
    """
    try:
        p = CatalogSearchPayload.model_validate(raw)
    except ValidationError as exc:
        # field names and generic reasons only: no input value is echoed back
        parts = [f"{'.'.join(str(x) for x in e['loc']) or 'payload'}: {e['msg']}" for e in exc.errors()]
        raise _fail("; ".join(parts)) from exc
    start, end = _day("start", p.start), _day("end", p.end)
    if end < start:
        raise _fail("end must not precede start")
    window = (end - start).days + 1
    if window > settings.MAX_TIME_WINDOW_DAYS:
        raise _fail(
            f"time window of {window} days exceeds MAX_TIME_WINDOW_DAYS ({settings.MAX_TIME_WINDOW_DAYS})"
        )
    if not all(_COLLECTION.fullmatch(c) for c in p.collections):
        raise _fail("collections must match [A-Za-z0-9][A-Za-z0-9._-]{0,63}")
    max_items = settings.MAX_SCENES_PER_JOB if p.max_items is None else p.max_items
    if max_items > settings.MAX_SCENES_PER_JOB:
        raise _fail(f"max_items exceeds MAX_SCENES_PER_JOB ({settings.MAX_SCENES_PER_JOB})")
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "collections": sorted(set(p.collections)),
        "max_items": max_items,
    }


def require_connector_mode(settings: Settings) -> None:
    """The one place the API reads `CONNECTOR_MODE` for jobs. Raises before anything is created.

    * `fixture`  — allowed: the worker serves committed synthetic fixtures offline;
    * `disabled` — `409 connectors_disabled` (the default; no connector opens, nothing is queued);
    * `live`     — `501 connector_live_not_available`: the value is accepted as configuration but there is
      no live code path in Phase 3a; stable until a live slice is separately authorised.
    """
    mode = settings.CONNECTOR_MODE
    if mode == "fixture":
        return
    if mode == "live":
        raise ApiError(
            501,
            "connector_live_not_available",
            "CONNECTOR_MODE=live is not available in Phase 3a (fixtures only); no job was created",
        )
    raise ApiError(
        409,
        "connectors_disabled",
        "connectors are disabled (CONNECTOR_MODE=disabled); no job was created",
    )
