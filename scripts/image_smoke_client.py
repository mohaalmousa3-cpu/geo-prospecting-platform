"""Runs INSIDE the backend container against its own API (stdlib only; nothing is published on the host).

The stack runs with CONNECTOR_MODE=fixture for the API and for the worker (docker-compose.smoke.yml). The
worker image processes the jobs. Offline: the fixtures are committed synthetic files.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"
RECT = {"method": "rectangle", "name": "smoke", "west": 10.02, "south": 40.02, "east": 10.05, "north": 40.05}
BODY = {"start": "2026-01-01", "end": "2026-12-31", "collections": ["synthetic-optical"]}


def call(method: str, path: str, body: object = None) -> tuple[int, bytes, dict[str, str]]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method)  # noqa: S310 - fixed loopback URL
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def jcall(method: str, path: str, body: object = None) -> tuple[int, dict]:
    status, raw, _ = call(method, path, body)
    return status, (json.loads(raw) if raw else {})


def wait_terminal(job_id: str, timeout: float = 120.0) -> dict:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        _, job = jcall("GET", f"/jobs/{job_id}")
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(1)
    raise SystemExit(f"job {job_id} did not finish within {timeout:g}s (is the worker running?)")


def main() -> None:
    assert jcall("GET", "/health/ready")[0] == 200
    s, project = jcall("POST", "/projects", {"name": "image smoke"})
    assert s == 201, project
    s, aoi = jcall("POST", "/aois", {**RECT, "project_id": project["id"]})
    assert s == 201, aoi

    # refusals that must hold in the running stack
    assert (
        jcall(
            "POST",
            "/jobs",
            {"type": "catalog_search", "aoi_id": aoi["id"], "payload": BODY, "project_id": project["id"]},
        )[0]
        == 422
    )
    assert (
        jcall(
            "POST",
            "/jobs",
            {"type": "catalog_search", "aoi_id": "00000000-0000-0000-0000-000000000000", "payload": BODY},
        )[0]
        == 404
    )

    # non-empty: the worker image runs the registered handler and publishes the fixture asset
    s, job = jcall("POST", "/jobs", {"type": "catalog_search", "aoi_id": aoi["id"], "payload": BODY})
    assert s == 201 and job["project_id"] == project["id"], job
    done = wait_terminal(job["id"])
    assert done["status"] == "succeeded", done
    s, listing = jcall("GET", f"/assets?job_id={job['id']}")
    assert s == 200 and listing["total"] == 1, listing
    asset = listing["items"][0]
    s, raw, headers = call(
        "GET", f"/assets/{asset['id']}/content"
    )  # the file was written by the worker container
    assert s == 200 and hashlib.sha256(raw).hexdigest() == asset["sha256"], (s, asset)
    doc = json.loads(raw)
    assert doc["records"] and doc["source"]["synthetic"] is True and doc["source"]["kind"] == "fixture"
    s, one = jcall("GET", f"/assets/{asset['id']}")
    assert one["provenance"]["job_id"] == job["id"] and one["provenance"]["request_hash"].startswith("v1:")

    # zero results: insufficient_data, no asset
    s, empty = jcall(
        "POST",
        "/jobs",
        {
            "type": "catalog_search",
            "aoi_id": aoi["id"],
            "payload": {**BODY, "start": "2020-01-01", "end": "2020-01-31"},
        },
    )
    assert s == 201, empty
    done0 = wait_terminal(empty["id"])
    assert done0["status"] == "insufficient_data" and "no catalogue items matched" in done0["error"], done0
    assert jcall("GET", f"/assets?job_id={empty['id']}")[1]["total"] == 0
    assert jcall("GET", "/assets")[1]["total"] == 1  # exactly the one asset of the non-empty job

    print(
        json.dumps(
            {
                "ok": True,
                "records": len(doc["records"]),
                "asset": asset["id"],
                "zero_result_status": done0["status"],
            }
        )
    )


if __name__ == "__main__":
    main()
