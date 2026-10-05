"""API mapping of deletion outcomes (ADR-0014 §7.6): status codes, error codes and the unchanged success paths."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app import deletion

pytestmark = pytest.mark.integration
MakeAoi = Callable[..., tuple[UUID, UUID]]
AddJob = Callable[..., UUID]


def test_aoi_with_active_job_is_refused_with_409_has_active_jobs(
    client: TestClient, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    _, aoi = make_aoi()
    add_job(aoi, "running")
    for flag in ("false", "true"):
        r = client.delete(f"/api/v1/aois/{aoi}?delete_dependents={flag}")
        assert r.status_code == 409 and r.json()["error"]["code"] == "has_active_jobs"
    assert client.get(f"/api/v1/aois/{aoi}").status_code == 200


def test_aoi_with_finished_jobs_needs_the_explicit_flag(
    client: TestClient, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    _, aoi = make_aoi()
    add_job(aoi, "succeeded")
    r = client.delete(f"/api/v1/aois/{aoi}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "needs_cascade"
    assert client.delete(f"/api/v1/aois/{aoi}?delete_dependents=true").status_code == 204
    assert client.get(f"/api/v1/aois/{aoi}").status_code == 404


def test_missing_aoi_is_404_and_plain_delete_is_unchanged(client: TestClient, make_aoi: MakeAoi) -> None:
    _, aoi = make_aoi()
    assert client.delete(f"/api/v1/aois/{aoi}").status_code == 204
    r = client.delete(f"/api/v1/aois/{aoi}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "aoi_not_found"


def test_project_with_an_active_job_is_refused_even_with_delete_aois(
    client: TestClient, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    p, aoi = make_aoi()
    add_job(aoi, "queued")
    r = client.delete(f"/api/v1/projects/{p}?delete_aois=true")
    assert r.status_code == 409 and r.json()["error"]["code"] == "has_active_jobs"
    assert client.get(f"/api/v1/projects/{p}").json()["aoi_count"] == 1


def test_project_semantics_of_adr_0013_are_unchanged(
    client: TestClient, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    p, aoi = make_aoi()
    add_job(aoi, "failed")
    r = client.delete(f"/api/v1/projects/{p}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "project_not_empty"
    assert client.delete(f"/api/v1/projects/{p}?delete_aois=true").status_code == 204
    assert client.delete(f"/api/v1/projects/{p}").status_code == 404


@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [
        (deletion.RetryLaterError("x"), 503, "retry_later"),
        (deletion.StillReferencedError("job_aoi_project_fk"), 409, "still_referenced"),
        (deletion.IntegrityFailureError("23514", "c"), 500, "integrity_error"),
    ],
)
def test_infrastructure_outcomes_map_to_the_documented_errors(
    client: TestClient,
    make_aoi: MakeAoi,
    monkeypatch: pytest.MonkeyPatch,
    exc: Exception,
    status: int,
    code: str,
) -> None:
    p, aoi = make_aoi()

    def boom(*_a: object, **_k: object) -> None:
        raise exc

    monkeypatch.setattr(deletion, "delete_aoi", boom)
    monkeypatch.setattr(deletion, "delete_project", boom)
    for url in (f"/api/v1/aois/{aoi}", f"/api/v1/projects/{p}"):
        r = client.delete(url)
        assert r.status_code == status and r.json()["error"]["code"] == code
        assert "SQL" not in r.text and "constraint" not in r.json()["error"]["message"].lower()
