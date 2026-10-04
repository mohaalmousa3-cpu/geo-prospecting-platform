"use client";

import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map, MapMouseEvent, StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";

import { wrapLon } from "@/lib/geometry";
import type { LonLat } from "@/types/contracts";

import type { MapViewProps } from "./mapTypes";

let workerConfigured = false;
const TILE_URL = process.env.NEXT_PUBLIC_BASEMAP_TILE_URL ?? "";
const ATTRIBUTION = process.env.NEXT_PUBLIC_BASEMAP_ATTRIBUTION ?? "";

export function buildStyle(tileUrl: string, attribution: string): StyleSpecification {
  const layers: StyleSpecification["layers"] = [
    { id: "bg", type: "background", paint: { "background-color": "#e8edf1" } },
  ];
  const sources: StyleSpecification["sources"] = {};
  if (tileUrl) {
    sources.basemap = { type: "raster", tiles: [tileUrl], tileSize: 256, attribution, maxzoom: 19 };
    layers.push({ id: "basemap", type: "raster", source: "basemap" });
  }
  return { version: 8, sources, layers };
}

const EMPTY = { type: "FeatureCollection", features: [] } as const;

function setData(map: Map, id: string, data: unknown) {
  (map.getSource(id) as GeoJSONSource | undefined)?.setData(data as never);
}

export default function MapView(props: MapViewProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Map | null>(null);
  const propsRef = useRef(props);
  useEffect(() => {
    propsRef.current = props;
  });
  const cornerA = useRef<LonLat | null>(null);
  const hover = useRef<LonLat | null>(null);

  // --- create the map once
  useEffect(() => {
    if (!container.current) return;
    if (!workerConfigured) {
      maplibregl.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
      workerConfigured = true;
    }
    const map = new maplibregl.Map({
      container: container.current,
      style: buildStyle(TILE_URL, ATTRIBUTION),
      center: [10, 30],
      zoom: 2,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

    map.on("load", () => {
      for (const id of ["draft", "saved", "sketch", "marker"]) {
        map.addSource(id, { type: "geojson", data: EMPTY as never });
      }
      map.addLayer({
        id: "saved-fill",
        type: "fill",
        source: "saved",
        paint: { "fill-color": "#2e7d32", "fill-opacity": 0.2 },
      });
      map.addLayer({
        id: "saved-line",
        type: "line",
        source: "saved",
        paint: { "line-color": "#2e7d32", "line-width": 2 },
      });
      map.addLayer({
        id: "draft-fill",
        type: "fill",
        source: "draft",
        paint: { "fill-color": "#1565c0", "fill-opacity": 0.25 },
      });
      map.addLayer({
        id: "draft-line",
        type: "line",
        source: "draft",
        paint: { "line-color": "#1565c0", "line-width": 2 },
      });
      map.addLayer({
        id: "sketch-fill",
        type: "fill",
        source: "sketch",
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: { "fill-color": "#ef6c00", "fill-opacity": 0.12 },
      });
      map.addLayer({
        id: "sketch-line",
        type: "line",
        source: "sketch",
        paint: { "line-color": "#ef6c00", "line-width": 2, "line-dasharray": [2, 1] },
      });
      map.addLayer({
        id: "sketch-pts",
        type: "circle",
        source: "sketch",
        filter: ["==", ["geometry-type"], "Point"],
        paint: {
          "circle-radius": 4,
          "circle-color": "#ef6c00",
          "circle-stroke-color": "#fff",
          "circle-stroke-width": 1,
        },
      });
      map.addLayer({
        id: "marker-pt",
        type: "circle",
        source: "marker",
        paint: {
          "circle-radius": 6,
          "circle-color": "#1565c0",
          "circle-stroke-color": "#fff",
          "circle-stroke-width": 2,
        },
      });
      redrawAll();
    });

    const lonlat = (e: MapMouseEvent): LonLat => [wrapLon(e.lngLat.lng), e.lngLat.lat];

    map.on("click", (e: MapMouseEvent) => {
      const p = propsRef.current;
      const pt = lonlat(e);
      if (p.mode === "center") p.onCenter(pt);
      else if (p.mode === "rectangle") {
        if (!cornerA.current) {
          cornerA.current = pt;
        } else {
          const a = cornerA.current;
          cornerA.current = null;
          hover.current = null;
          p.onRectangle(a, pt);
        }
        redrawSketch();
      } else if (p.mode === "polygon") p.onPolygonPoint(pt);
    });
    map.on("dblclick", (e: MapMouseEvent) => {
      if (propsRef.current.mode === "polygon") {
        e.preventDefault();
        propsRef.current.onPolygonFinish();
      }
    });
    map.on("mousemove", (e: MapMouseEvent) => {
      const p = propsRef.current;
      if (p.mode === "rectangle" && cornerA.current) {
        hover.current = lonlat(e);
        redrawSketch();
      }
    });
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") {
        cornerA.current = null;
        hover.current = null;
        propsRef.current.onCancel();
        redrawSketch();
      }
    };
    window.addEventListener("keydown", onKey);

    function sketchData() {
      const p = propsRef.current;
      const features: unknown[] = [];
      if (p.mode === "rectangle" && cornerA.current) {
        const a = cornerA.current;
        const b = hover.current ?? a;
        features.push({
          type: "Feature",
          properties: {},
          geometry: { type: "Polygon", coordinates: [[a, [b[0], a[1]], b, [a[0], b[1]], a]] },
        });
        features.push({
          type: "Feature",
          properties: {},
          geometry: { type: "Point", coordinates: a },
        });
      }
      if (p.mode === "polygon" && p.polygonPoints.length) {
        const pts = p.polygonPoints;
        if (pts.length >= 2)
          features.push({
            type: "Feature",
            properties: {},
            geometry: { type: "LineString", coordinates: pts },
          });
        for (const q of pts)
          features.push({
            type: "Feature",
            properties: {},
            geometry: { type: "Point", coordinates: q },
          });
      }
      return { type: "FeatureCollection", features };
    }
    function redrawSketch() {
      if (map.isStyleLoaded() || map.getSource("sketch")) setData(map, "sketch", sketchData());
    }
    function redrawAll() {
      const p = propsRef.current;
      const poly = (g: unknown) => (g ? { type: "Feature", properties: {}, geometry: g } : EMPTY);
      setData(map, "draft", poly(p.draft));
      setData(map, "saved", poly(p.saved));
      setData(
        map,
        "marker",
        p.marker
          ? { type: "Feature", properties: {}, geometry: { type: "Point", coordinates: p.marker } }
          : EMPTY,
      );
      redrawSketch();
    }
    (map as unknown as { __redraw: () => void }).__redraw = redrawAll;

    return () => {
      window.removeEventListener("keydown", onKey);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // --- keep sources in sync with props
  useEffect(() => {
    const map = mapRef.current as (Map & { __redraw?: () => void }) | null;
    if (!map || !map.getSource("draft")) return;
    cornerA.current = props.mode === "rectangle" ? cornerA.current : null;
    map.__redraw?.();
    map.getCanvas().style.cursor = props.mode === "none" ? "" : "crosshair";
    if (props.mode === "polygon") map.doubleClickZoom.disable();
    else map.doubleClickZoom.enable();
  }, [props.draft, props.saved, props.marker, props.polygonPoints, props.mode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !props.fitTo) return;
    const [w, s, e, n] = props.fitTo;
    map.fitBounds(
      [
        [w, s],
        [e, n],
      ],
      { padding: 60, maxZoom: 16, duration: 400 },
    );
  }, [props.fitTo]);

  return (
    <div
      ref={container}
      role="application"
      aria-label="Map. Use the forms beside the map to enter coordinates without drawing."
      data-testid="map"
      style={{ width: "100%", height: "100%", minHeight: 420 }}
    />
  );
}
