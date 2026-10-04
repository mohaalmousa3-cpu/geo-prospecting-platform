"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState, type ComponentType } from "react";

import {
  AoiApiError,
  createAoi,
  deleteAoi,
  getAoi,
  getLimits,
  listAois,
  previewAoi,
  uploadAoi,
  type AoiRequest,
} from "@/lib/aoiApi";
import {
  dedupeConsecutive,
  formatArea,
  formatCoord,
  parseNumber,
  rectangleFromCorners,
} from "@/lib/geometry";
import type {
  Aoi,
  AoiDraft,
  AoiLimits,
  AoiPolygonRequest,
  AoiSummary,
  Bbox,
  LonLat,
} from "@/types/contracts";

import type { DrawMode, MapViewProps } from "./mapTypes";

const DefaultMap = dynamic(() => import("./MapView"), {
  ssr: false,
  loading: () => <p>Loading map…</p>,
});

type Tab = "point" | "rectangle" | "polygon" | "upload";
const TABS: { id: Tab; label: string }[] = [
  { id: "point", label: "Point + radius" },
  { id: "rectangle", label: "Rectangle" },
  { id: "polygon", label: "Polygon" },
  { id: "upload", label: "Upload file" },
];

function parsePolygonText(text: string): { points: LonLat[]; bad: number } {
  const points: LonLat[] = [];
  let bad = 0;
  for (const line of text.split("\n")) {
    if (!line.trim()) continue;
    const parts = line.split(/[,;\s]+/).filter(Boolean);
    const lon = parts.length === 2 ? parseNumber(parts[0]) : null;
    const lat = parts.length === 2 ? parseNumber(parts[1]) : null;
    if (lon === null || lat === null) bad += 1;
    else points.push([lon, lat]);
  }
  return { points, bad };
}

function toErr(e: unknown) {
  return e instanceof AoiApiError
    ? { code: e.code, message: e.message }
    : { code: "error", message: (e as Error).message };
}

export function AoiWorkbench({
  MapComponent = DefaultMap,
}: {
  MapComponent?: ComponentType<MapViewProps>;
}) {
  const [tab, setTab] = useState<Tab>("point");
  const [name, setName] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [radius, setRadius] = useState("1000");
  const [rect, setRect] = useState({ west: "", south: "", east: "", north: "" });
  const [polyText, setPolyText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<DrawMode>("none");

  const [limits, setLimits] = useState<AoiLimits | null>(null);
  const [saved, setSaved] = useState<AoiSummary[]>([]);
  const [selected, setSelected] = useState<Aoi | null>(null);
  const [draft, setDraft] = useState<{ key: string; value: AoiDraft } | null>(null);
  const [fitTo, setFitTo] = useState<Bbox | null>(null);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const polygon = useMemo(() => parsePolygonText(polyText), [polyText]);

  // The request implied by the current inputs (null + reason when incomplete).
  const built = useMemo((): { req: AoiRequest | null; problem: string | null } => {
    if (tab === "point") {
      const la = parseNumber(lat),
        lo = parseNumber(lon),
        r = parseNumber(radius);
      if (la === null || lo === null || r === null)
        return { req: null, problem: "Enter latitude, longitude and radius as numbers." };
      return { req: { method: "point_radius", lat: la, lon: lo, radius_m: r }, problem: null };
    }
    if (tab === "rectangle") {
      const v = [rect.west, rect.south, rect.east, rect.north].map(parseNumber);
      if (v.some((x) => x === null))
        return { req: null, problem: "Enter west, south, east and north as numbers." };
      const [west, south, east, north] = v as number[];
      return { req: { method: "rectangle", west, south, east, north }, problem: null };
    }
    if (tab === "polygon") {
      if (polygon.bad) return { req: null, problem: `${polygon.bad} line(s) are not "lon, lat".` };
      if (polygon.points.length < 3)
        return { req: null, problem: "A polygon needs at least 3 points." };
      return {
        req: { method: "polygon", coordinates: polygon.points as AoiPolygonRequest["coordinates"] },
        problem: null,
      };
    }
    return { req: null, problem: file ? null : "Choose a file." };
  }, [tab, lat, lon, radius, rect, polygon, file]);

  const key = useMemo(
    () => JSON.stringify([tab, built.req, file?.name, file?.size, file?.lastModified]),
    [tab, built.req, file],
  );
  const currentDraft = draft && draft.key === key ? draft.value : null;

  const refresh = useCallback(async () => {
    try {
      setSaved((await listAois()).items);
    } catch (e) {
      setError(toErr(e));
    }
  }, []);

  useEffect(() => {
    getLimits()
      .then(setLimits)
      .catch((e) => setError(toErr(e)));
    listAois()
      .then((l) => setSaved(l.items))
      .catch((e) => setError(toErr(e)));
  }, []);

  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      return await fn();
    } catch (e) {
      setError(toErr(e));
      return undefined;
    } finally {
      setBusy(false);
    }
  }

  const validate = () =>
    run(async () => {
      const d =
        tab === "upload" && file ? await uploadAoi(file, name, true) : await previewAoi(built.req!);
      setDraft({ key, value: d });
      setSelected(null);
      setFitTo(d.bbox as Bbox);
      setMode("none");
    });

  const save = () =>
    run(async () => {
      if (!name.trim())
        throw new AoiApiError("name_required", "Give the AOI a name before saving.", 422);
      const aoi =
        tab === "upload" && file
          ? await uploadAoi(file, name, false)
          : await createAoi({ ...built.req!, name: name.trim() });
      setDraft(null);
      setSelected(aoi);
      setFitTo(aoi.bbox as Bbox);
      setInfo(`Saved “${aoi.name}”.`);
      await refresh();
    });

  const select = (id: string) =>
    run(async () => {
      const aoi = await getAoi(id);
      setSelected(aoi);
      setDraft(null);
      setFitTo(aoi.bbox as Bbox);
    });

  const remove = (a: AoiSummary) => {
    if (!window.confirm(`Delete “${a.name}”? This cannot be undone.`)) return;
    void run(async () => {
      await deleteAoi(a.id);
      if (selected?.id === a.id) setSelected(null);
      await refresh();
    });
  };

  // --- map callbacks
  const onCenter = (p: LonLat) => {
    setLon(p[0].toFixed(6));
    setLat(p[1].toFixed(6));
    setMode("none");
  };
  const onRectangle = (a: LonLat, b: LonLat) => {
    const r = rectangleFromCorners(a, b);
    setRect({
      west: r.west.toFixed(6),
      south: r.south.toFixed(6),
      east: r.east.toFixed(6),
      north: r.north.toFixed(6),
    });
    setMode("none");
  };
  const onPolygonPoint = (p: LonLat) =>
    setPolyText(
      (t) => `${t}${t && !t.endsWith("\n") ? "\n" : ""}${p[0].toFixed(6)}, ${p[1].toFixed(6)}\n`,
    );
  const onPolygonFinish = () => {
    setPolyText((t) => {
      const pts = dedupeConsecutive(parsePolygonText(t).points);
      return pts.map((p) => `${p[0].toFixed(6)}, ${p[1].toFixed(6)}`).join("\n") + "\n";
    });
    setMode("none");
  };

  const marker: LonLat | null = (() => {
    if (tab !== "point") return null;
    const la = parseNumber(lat),
      lo = parseNumber(lon);
    return la === null || lo === null ? null : [lo, la];
  })();

  const switchTab = (t: Tab) => {
    setTab(t);
    setMode("none");
    setError(null);
  };
  const drawMode: DrawMode | null =
    tab === "point"
      ? "center"
      : tab === "rectangle"
        ? "rectangle"
        : tab === "polygon"
          ? "polygon"
          : null;

  return (
    <div
      style={{ display: "grid", gridTemplateColumns: "minmax(300px, 400px) 1fr", gap: 16 }}
      className="workbench"
    >
      <section aria-label="AOI input" style={{ display: "grid", gap: 12, alignContent: "start" }}>
        <p style={{ margin: 0, fontSize: 14 }}>
          Define an area of interest.{" "}
          <strong>Only the outline is validated — no analysis is performed.</strong>
          {limits && (
            <>
              {" "}
              Limits (provisional safeguards): up to {limits.max_area_km2} km², radius up to{" "}
              {limits.max_radius_m / 1000} km, |lat| ≤ {limits.max_abs_latitude}°.
            </>
          )}
        </p>

        <div
          role="tablist"
          aria-label="Input method"
          style={{ display: "flex", gap: 4, flexWrap: "wrap" }}
        >
          {TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => switchTab(t.id)}
              style={{ fontWeight: tab === t.id ? 700 : 400 }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "point" && (
          <fieldset style={{ display: "grid", gap: 6 }}>
            <legend>Centre and radius</legend>
            <label>
              Latitude (°)
              <input
                aria-label="Latitude"
                value={lat}
                onChange={(e) => setLat(e.target.value)}
                inputMode="decimal"
              />
            </label>
            <label>
              Longitude (°)
              <input
                aria-label="Longitude"
                value={lon}
                onChange={(e) => setLon(e.target.value)}
                inputMode="decimal"
              />
            </label>
            <label>
              Radius (m)
              <input
                aria-label="Radius (m)"
                value={radius}
                onChange={(e) => setRadius(e.target.value)}
                inputMode="decimal"
              />
            </label>
          </fieldset>
        )}
        {tab === "rectangle" && (
          <fieldset style={{ display: "grid", gap: 6 }}>
            <legend>Bounds (°)</legend>
            {(["west", "south", "east", "north"] as const).map((k) => (
              <label key={k}>
                {k[0].toUpperCase() + k.slice(1)}
                <input
                  aria-label={k[0].toUpperCase() + k.slice(1)}
                  value={rect[k]}
                  inputMode="decimal"
                  onChange={(e) => setRect({ ...rect, [k]: e.target.value })}
                />
              </label>
            ))}
          </fieldset>
        )}
        {tab === "polygon" && (
          <fieldset style={{ display: "grid", gap: 6 }}>
            <legend>Vertices (one “lon, lat” per line)</legend>
            <textarea
              aria-label="Polygon vertices"
              rows={6}
              value={polyText}
              onChange={(e) => setPolyText(e.target.value)}
            />
            <div style={{ display: "flex", gap: 6 }}>
              <button
                type="button"
                onClick={() =>
                  setPolyText((t) => t.trimEnd().split("\n").slice(0, -1).join("\n") + "\n")
                }
              >
                Undo last
              </button>
              <button type="button" onClick={() => setPolyText("")}>
                Clear
              </button>
              <button type="button" onClick={onPolygonFinish}>
                Finish
              </button>
            </div>
          </fieldset>
        )}
        {tab === "upload" && (
          <fieldset style={{ display: "grid", gap: 6 }}>
            <legend>GeoJSON, KML, KMZ or zipped Shapefile</legend>
            <input
              type="file"
              aria-label="AOI file"
              accept=".geojson,.json,.kml,.kmz,.zip"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            {limits && (
              <small>
                Max {limits.max_upload_mb} MB. One polygon per file. Shapefiles need a .prj.
              </small>
            )}
          </fieldset>
        )}

        {drawMode && (
          <button
            type="button"
            aria-pressed={mode === drawMode}
            onClick={() => setMode(mode === drawMode ? "none" : drawMode)}
          >
            {mode === drawMode
              ? "Cancel drawing (Esc)"
              : tab === "point"
                ? "Pick centre on map"
                : tab === "rectangle"
                  ? "Draw rectangle (2 clicks)"
                  : "Draw polygon (click; double-click to finish)"}
          </button>
        )}

        <label>
          Name
          <input
            aria-label="Name"
            value={name}
            maxLength={120}
            onChange={(e) => setName(e.target.value)}
            placeholder="required to save"
          />
        </label>

        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" onClick={validate} disabled={busy || !!built.problem}>
            Validate
          </button>
          <button type="button" onClick={save} disabled={busy || !!built.problem || !currentDraft}>
            Save
          </button>
        </div>
        {built.problem && <small>{built.problem}</small>}

        {error && (
          <p role="alert" data-testid="aoi-error" style={{ color: "#b71c1c", margin: 0 }}>
            <code>{error.code}</code>: {error.message}
          </p>
        )}
        {info && (
          <p role="status" style={{ margin: 0 }}>
            {info}
          </p>
        )}

        {currentDraft && (
          <div data-testid="draft-summary" style={{ border: "1px solid #1565c0", padding: 8 }}>
            <strong>Valid outline (not saved)</strong>
            <div>
              Area {formatArea(currentDraft.area_km2)} · {currentDraft.vertex_count} vertices ·
              working CRS {currentDraft.working_crs}
            </div>
            <div>
              Bounds W {formatCoord(currentDraft.bbox[0])} S {formatCoord(currentDraft.bbox[1])} E{" "}
              {formatCoord(currentDraft.bbox[2])} N {formatCoord(currentDraft.bbox[3])}
            </div>
            {currentDraft.warnings.map((w) => (
              <div key={w}>⚠ {w}</div>
            ))}
          </div>
        )}

        <div>
          <h2 style={{ fontSize: 16 }}>Saved AOIs ({saved.length})</h2>
          {saved.length === 0 && <p>None yet.</p>}
          <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: 4 }}>
            {saved.map((a) => (
              <li key={a.id} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <button
                  type="button"
                  onClick={() => select(a.id)}
                  aria-pressed={selected?.id === a.id}
                  style={{ flex: 1, textAlign: "left" }}
                >
                  {a.name}{" "}
                  <small>
                    ({a.method}, {formatArea(a.area_km2)})
                  </small>
                </button>
                <button type="button" aria-label={`Delete ${a.name}`} onClick={() => remove(a)}>
                  🗑
                </button>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section aria-label="Map" style={{ minHeight: 480, border: "1px solid #ccd" }}>
        <MapComponent
          mode={mode}
          draft={currentDraft?.geometry ?? null}
          saved={selected?.geometry ?? null}
          fitTo={fitTo}
          marker={marker}
          polygonPoints={tab === "polygon" ? polygon.points : []}
          onCenter={onCenter}
          onRectangle={onRectangle}
          onPolygonPoint={onPolygonPoint}
          onPolygonFinish={onPolygonFinish}
          onCancel={() => setMode("none")}
        />
      </section>
    </div>
  );
}
