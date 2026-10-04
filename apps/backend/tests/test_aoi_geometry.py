from __future__ import annotations

import math

import pytest
from aoi_helpers import GEOD, LIMITS, ring_area_km2, square_with_area

from app.aoi.errors import AoiValidationError
from app.aoi.geometry import (
    CIRCLE_VERTICES,
    RawPolygon,
    build_polygon,
    circle_ring,
    rectangle_ring,
    utm_epsg,
)


def build(ring: list[list[float]], holes: list[list[list[float]]] | None = None):  # type: ignore[no-untyped-def]
    return build_polygon(RawPolygon(ring, holes or []), LIMITS)


def code(fn, *a):  # type: ignore[no-untyped-def]
    with pytest.raises(AoiValidationError) as e:
        fn(*a)
    return e.value.code


# ------------------------------------------------------------------ reference values
def test_circle_vertices_lie_on_the_requested_geodesic_radius() -> None:
    ring = circle_ring(45.0, 7.0, 2000.0, LIMITS)
    assert len(ring) == CIRCLE_VERTICES + 1 and ring[0] == ring[-1]  # closed
    for lon, lat in ring:
        _, _, d = GEOD.inv(7.0, 45.0, lon, lat)
        assert d == pytest.approx(2000.0, abs=0.01)


def test_circle_area_matches_the_72_gon_reference_not_pi_r2() -> None:
    g = build(circle_ring(0.0, 0.0, 1000.0, LIMITS))
    expected = 0.5 * CIRCLE_VERTICES * math.sin(2 * math.pi / CIRCLE_VERTICES) * 1000.0**2 / 1e6
    assert g.area_km2 == pytest.approx(expected, rel=2e-3)
    assert g.area_km2 < math.pi  # polygon is inscribed: strictly below the true circle


def test_small_rectangle_area_matches_wgs84_reference() -> None:
    # 0.01 deg x 0.01 deg at the equator: ~1.1132 km (lon) x ~1.1057 km (lat) = ~1.2309 km2
    g = build(rectangle_ring(10.0, 0.0, 10.01, 0.01))
    assert g.area_km2 == pytest.approx(1.2309, rel=5e-3)


def test_hole_area_is_subtracted() -> None:
    outer = square_with_area(4.0)
    x0, y0 = outer[0]
    side = outer[1][0] - x0
    hole = [
        [x0 + side * 0.25, y0 + side * 0.25], [x0 + side * 0.25, y0 + side * 0.75],
        [x0 + side * 0.75, y0 + side * 0.75], [x0 + side * 0.75, y0 + side * 0.25],
        [x0 + side * 0.25, y0 + side * 0.25],
    ]  # fmt: skip
    g = build(outer, [hole])
    assert g.area_km2 == pytest.approx(ring_area_km2(outer) - ring_area_km2(hole), rel=1e-6)
    assert g.vertex_count == 4 + 4


def test_exterior_ring_is_counter_clockwise() -> None:
    ring = square_with_area(1.0)
    for r in (ring, list(reversed(ring))):
        assert build(r).polygon.exterior.is_ccw


@pytest.mark.parametrize(
    ("lon", "lat", "epsg"),
    [
        (13.4, 52.5, "EPSG:32633"),
        (-58.4, -34.6, "EPSG:32721"),
        (179.9, 10, "EPSG:32660"),
        (-179.9, 10, "EPSG:32601"),
    ],
)
def test_utm_zone(lon: float, lat: float, epsg: str) -> None:
    assert utm_epsg(lon, lat) == epsg


# ------------------------------------------------------------------ ADR-0008 boundaries
def test_area_boundaries_max() -> None:
    assert build(square_with_area(25 * (1 - 1e-6))).area_km2 <= 25
    assert code(build, square_with_area(25 * (1 + 1e-4))) == "area_too_large"


def test_area_boundaries_min() -> None:
    assert build(square_with_area(0.01 * (1 + 1e-4))).area_km2 >= 0.01
    assert code(build, square_with_area(0.01 * (1 - 1e-3))) == "area_too_small"


def test_area_error_states_limit_and_value() -> None:
    with pytest.raises(AoiValidationError) as e:
        build(square_with_area(40.0))
    assert "MAX_AOI_AREA_KM2=25" in e.value.message and "40.00" in e.value.message


def test_radius_boundaries() -> None:
    assert build(circle_ring(0, 0, 2500.0, LIMITS)).area_km2 < 25
    assert code(circle_ring, 0, 0, 2500.01, LIMITS) == "radius_too_large"
    assert code(circle_ring, 0, 0, 0.0, LIMITS) == "invalid_radius"
    assert code(circle_ring, 0, 0, -5.0, LIMITS) == "invalid_radius"
    assert code(circle_ring, 0, 0, float("nan"), LIMITS) == "invalid_coordinate"


def _n_gon(n: int, r_deg: float = 0.005) -> list[list[float]]:
    pts = [
        [10 + r_deg * math.cos(2 * math.pi * i / n), r_deg * math.sin(2 * math.pi * i / n)] for i in range(n)
    ]
    return [*pts, pts[0]]


def test_vertex_boundaries() -> None:
    assert build(_n_gon(2000)).vertex_count == 2000
    assert code(build, _n_gon(2001)) == "too_many_vertices"


def test_vertex_count_includes_holes() -> None:
    outer = _n_gon(1500, 0.01)
    hole = _n_gon(501, 0.001)
    assert code(build, outer, [hole]) == "too_many_vertices"


# ------------------------------------------------------------------ coordinate hygiene
@pytest.mark.parametrize(
    ("ring", "expected"),
    [
        ([[181, 0], [182, 0], [182, 1], [181, 0]], "coordinate_out_of_range"),
        ([[0, 91], [1, 91], [1, 90], [0, 91]], "coordinate_out_of_range"),
        ([[10, 85.0001], [10.01, 85.0001], [10.01, 85.0002], [10, 85.0001]], "latitude_unsupported"),
        ([[10, -86], [10.01, -86], [10.01, -85.99], [10, -86]], "latitude_unsupported"),
        ([[10, 0], [10.1, float("nan")], [10.1, 0.1], [10, 0]], "invalid_coordinate"),
        ([[10, 0], [10.1, float("inf")], [10.1, 0.1], [10, 0]], "invalid_coordinate"),
        ([[10, 0], [True, 0.1], [10.1, 0.1], [10, 0]], "invalid_coordinate"),
        ([[10, 0], [10.1]], "invalid_coordinate"),
        ([[10, 0], [10, 0], [10, 0], [10, 0]], "too_few_vertices"),
        ([[10, 0], [10.1, 0], [10, 0]], "too_few_vertices"),
        ([[10, 0], [10.1, 0.1], [10.1, 0], [10, 0.1], [10, 0]], "invalid_geometry"),  # bow-tie
        (
            [[179.99, 0], [-179.99, 0], [-179.99, 0.01], [179.99, 0.01], [179.99, 0]],
            "antimeridian_unsupported",
        ),
    ],
)
def test_invalid_rings_are_rejected_with_a_specific_code(ring: list[list[float]], expected: str) -> None:
    assert code(build, ring) == expected


def test_latitude_85_exactly_is_allowed() -> None:
    assert build([[10, 85], [10.2, 85], [10.2, 84.9], [10, 84.9], [10, 85]]).area_km2 > 0


def test_circle_across_antimeridian_and_near_pole_rejected() -> None:
    c = circle_ring(0.0, 179.99, 2000.0, LIMITS)
    assert code(build, c) == "antimeridian_unsupported"
    assert code(circle_ring, 85.5, 0, 2000.0, LIMITS) == "latitude_unsupported"  # centre itself
    # centre allowed (<= 85) but the circle's northern vertices exceed 85: rejected when built
    assert code(build, circle_ring(84.99, 0, 2000.0, LIMITS)) == "latitude_unsupported"


def test_open_ring_is_closed_with_warning_and_duplicates_removed() -> None:
    sq = square_with_area(1.0)[:-1]  # open
    sq.insert(1, sq[1])  # duplicate point
    g = build(sq)
    assert g.polygon.exterior.is_closed and g.vertex_count == 4
    assert any("closed automatically" in w for w in g.warnings)
    assert any("duplicate" in w for w in g.warnings)


def test_no_silent_repair_of_invalid_geometry() -> None:
    bowtie = [[10, 0], [10.05, 0.05], [10.05, 0], [10, 0.05], [10, 0]]
    with pytest.raises(AoiValidationError) as e:
        build(bowtie)
    assert "Self-intersection" in e.value.message


def test_z_values_are_dropped() -> None:
    ring3d = [[x, y, 123.0] for x, y in square_with_area(1.0)]
    g = build(ring3d)
    assert all(len(c) == 2 for c in g.polygon.exterior.coords)


@pytest.mark.parametrize("args", [(10, 0, 10, 1), (11, 0, 10, 1), (10, 1, 11, 0), (float("nan"), 0, 1, 1)])
def test_invalid_rectangles(args: tuple[float, ...]) -> None:
    assert code(rectangle_ring, *args) in ("invalid_rectangle", "invalid_coordinate")
