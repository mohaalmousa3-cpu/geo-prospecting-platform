import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AoiWorkbench } from "./AoiWorkbench";
import type { MapViewProps } from "./mapTypes";

const LIMITS = {
  max_area_km2: 25,
  min_area_km2: 0.01,
  max_radius_m: 2500,
  max_vertices: 2000,
  max_upload_mb: 10,
  max_stored_aois: 100,
  max_abs_latitude: 85,
  supported_upload_formats: ["geojson", "kml", "kmz", "shapefile"],
};
const GEOM = {
  type: "Polygon",
  coordinates: [
    [
      [1, 1],
      [1.1, 1],
      [1.1, 1.1],
      [1, 1.1],
      [1, 1],
    ],
  ],
};
const DRAFT = {
  method: "point_radius",
  geometry: GEOM,
  bbox: [1, 1, 1.1, 1.1],
  area_km2: 3.1,
  vertex_count: 72,
  working_crs: "EPSG:32631",
  details: {},
  warnings: ["ring was not closed; closed automatically"],
};
const SAVED = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Site A",
  method: "polygon",
  area_km2: 2,
  created_at: "2026-01-01T00:00:00Z",
  bbox: [1, 1, 1.1, 1.1],
};

let lastMapProps: MapViewProps;
function MapStub(props: MapViewProps) {
  // eslint-disable-next-line react-hooks/globals -- test stub records the latest props
  lastMapProps = props;
  return <div data-testid="map-stub" data-mode={props.mode} />;
}

type Route = (url: string, init?: RequestInit) => unknown;
function mockApi(routes: Record<string, Route>) {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = url.replace(/^.*\/api\/v1/, "");
      calls.push({ url: path, init });
      const key = Object.keys(routes).find(
        (k) => path.startsWith(k.split(" ")[1]) && (init?.method ?? "GET") === k.split(" ")[0],
      );
      if (!key)
        return {
          ok: false,
          status: 404,
          json: async () => ({ error: { code: "x", message: `no route ${path}` } }),
        };
      const r = routes[key](path, init) as { status?: number; body: unknown };
      const status = r.status ?? 200;
      return { ok: status < 400, status, json: async () => r.body };
    }),
  );
  return calls;
}
const base = (extra: Record<string, Route> = {}) => ({
  "GET /aois/limits": () => ({ body: LIMITS }),
  "GET /aois?": () => ({ body: { items: [SAVED], total: 1 } }),
  ...extra,
});

beforeEach(() => vi.spyOn(window, "confirm").mockReturnValue(true));
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("AoiWorkbench", () => {
  it("shows limits as provisional and states that no analysis is done", async () => {
    mockApi(base());
    render(<AoiWorkbench MapComponent={MapStub} />);
    expect(await screen.findByText(/up to 25 km²/)).toBeInTheDocument();
    expect(screen.getByText(/provisional safeguards/i)).toBeInTheDocument();
    expect(screen.getByText(/no analysis is performed/i)).toBeInTheDocument();
  });

  it("lists saved AOIs", async () => {
    mockApi(base());
    render(<AoiWorkbench MapComponent={MapStub} />);
    expect(await screen.findByRole("button", { name: /^Site A \(/ })).toBeInTheDocument();
    expect(screen.getByText(/Saved AOIs \(1\)/)).toBeInTheDocument();
  });

  it("blocks validation until point+radius inputs are numbers", async () => {
    mockApi(base());
    render(<AoiWorkbench MapComponent={MapStub} />);
    expect(screen.getByRole("button", { name: "Validate" })).toBeDisabled();
    expect(screen.getByText(/Enter latitude, longitude and radius/)).toBeInTheDocument();
  });

  it("validates a point+radius AOI, shows the summary and passes the draft to the map", async () => {
    const calls = mockApi(base({ "POST /aois/preview": () => ({ body: DRAFT }) }));
    render(<AoiWorkbench MapComponent={MapStub} />);
    await userEvent.type(screen.getByLabelText("Latitude"), "12.5");
    await userEvent.type(screen.getByLabelText("Longitude"), "40,1");
    await userEvent.click(screen.getByRole("button", { name: "Validate" }));
    const summary = await screen.findByTestId("draft-summary");
    expect(within(summary).getByText(/3\.10 km²/)).toBeInTheDocument();
    expect(within(summary).getByText(/closed automatically/)).toBeInTheDocument();
    const body = JSON.parse(calls.find((c) => c.url === "/aois/preview")!.init!.body as string);
    expect(body).toEqual({ method: "point_radius", lat: 12.5, lon: 40.1, radius_m: 1000 });
    expect(lastMapProps.draft).toEqual(GEOM);
    expect(lastMapProps.fitTo).toEqual(DRAFT.bbox);
  });

  it("shows the server's error code and message when validation fails", async () => {
    mockApi(
      base({
        "POST /aois/preview": () => ({
          status: 422,
          body: {
            error: { code: "radius_too_large", message: "radius 9000 m exceeds MAX_RADIUS_KM=2.5" },
          },
        }),
      }),
    );
    render(<AoiWorkbench MapComponent={MapStub} />);
    await userEvent.type(screen.getByLabelText("Latitude"), "1");
    await userEvent.type(screen.getByLabelText("Longitude"), "1");
    await userEvent.clear(screen.getByLabelText("Radius (m)"));
    await userEvent.type(screen.getByLabelText("Radius (m)"), "9000");
    await userEvent.click(screen.getByRole("button", { name: "Validate" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("radius_too_large");
    expect(alert).toHaveTextContent("MAX_RADIUS_KM=2.5");
    expect(screen.queryByTestId("draft-summary")).toBeNull();
  });

  it("requires a name to save, saves, and refreshes the list", async () => {
    let created = false;
    const calls = mockApi({
      "GET /aois/limits": () => ({ body: LIMITS }),
      "GET /aois?": () => ({
        body: {
          items: created ? [SAVED, { ...SAVED, id: "2", name: "New" }] : [SAVED],
          total: created ? 2 : 1,
        },
      }),
      "POST /aois/preview": () => ({ body: DRAFT }),
      "POST /aois": () => {
        created = true;
        return {
          status: 201,
          body: { ...DRAFT, id: "2", name: "New", created_at: "2026-01-02T00:00:00Z" },
        };
      },
    });
    render(<AoiWorkbench MapComponent={MapStub} />);
    await userEvent.type(screen.getByLabelText("Latitude"), "1");
    await userEvent.type(screen.getByLabelText("Longitude"), "1");
    await userEvent.click(screen.getByRole("button", { name: "Validate" }));
    await screen.findByTestId("draft-summary");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("name_required");
    await userEvent.type(screen.getByLabelText("Name"), "New");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText(/Saved “New”/)).toBeInTheDocument();
    expect(await screen.findByText(/Saved AOIs \(2\)/)).toBeInTheDocument();
    const post = calls.find((c) => c.url === "/aois" && c.init?.method === "POST")!;
    expect(JSON.parse(post.init!.body as string)).toMatchObject({
      method: "point_radius",
      name: "New",
    });
  });

  it("invalidates the validated draft when an input changes (Save disabled)", async () => {
    mockApi(base({ "POST /aois/preview": () => ({ body: DRAFT }) }));
    render(<AoiWorkbench MapComponent={MapStub} />);
    await userEvent.type(screen.getByLabelText("Latitude"), "1");
    await userEvent.type(screen.getByLabelText("Longitude"), "1");
    await userEvent.click(screen.getByRole("button", { name: "Validate" }));
    await screen.findByTestId("draft-summary");
    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
    await userEvent.type(screen.getByLabelText("Latitude"), "9");
    expect(screen.queryByTestId("draft-summary")).toBeNull();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(lastMapProps.draft).toBeNull();
  });

  it("fills the form from map interactions and builds a polygon from clicks", async () => {
    mockApi(base());
    render(<AoiWorkbench MapComponent={MapStub} />);
    await userEvent.click(screen.getByRole("button", { name: /Pick centre on map/ }));
    expect(screen.getByTestId("map-stub")).toHaveAttribute("data-mode", "center");
    await waitFor(() => lastMapProps.onCenter([40.123456, 12.5]));
    await waitFor(() => expect(screen.getByLabelText("Latitude")).toHaveValue("12.500000"));
    expect(screen.getByLabelText("Longitude")).toHaveValue("40.123456");

    await userEvent.click(screen.getByRole("tab", { name: "Rectangle" }));
    lastMapProps.onRectangle([10.2, 0.3], [10.0, 0.1]);
    await waitFor(() => expect(screen.getByLabelText("West")).toHaveValue("10.000000"));
    expect(screen.getByLabelText("North")).toHaveValue("0.300000");

    await userEvent.click(screen.getByRole("tab", { name: "Polygon" }));
    lastMapProps.onPolygonPoint([1, 1]);
    await waitFor(() => expect(lastMapProps.polygonPoints).toHaveLength(1));
    lastMapProps.onPolygonPoint([1.1, 1]);
    lastMapProps.onPolygonPoint([1.1, 1.1]);
    await waitFor(() => expect(lastMapProps.polygonPoints).toHaveLength(3));
    expect(screen.getByRole("button", { name: "Validate" })).toBeEnabled();
  });

  it("flags malformed polygon lines instead of sending them", async () => {
    mockApi(base());
    render(<AoiWorkbench MapComponent={MapStub} />);
    await userEvent.click(screen.getByRole("tab", { name: "Polygon" }));
    await userEvent.type(
      screen.getByLabelText("Polygon vertices"),
      "1,1{enter}oops{enter}2,2{enter}3,3",
    );
    expect(screen.getByText(/1 line\(s\) are not/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Validate" })).toBeDisabled();
  });

  it("uploads a file for validation", async () => {
    const calls = mockApi(base({ "POST /aois/upload": () => ({ body: DRAFT }) }));
    render(<AoiWorkbench MapComponent={MapStub} />);
    await userEvent.click(screen.getByRole("tab", { name: "Upload file" }));
    expect(screen.getByRole("button", { name: "Validate" })).toBeDisabled();
    await userEvent.upload(screen.getByLabelText("AOI file"), new File(["{}"], "site.geojson"));
    await userEvent.click(screen.getByRole("button", { name: "Validate" }));
    await screen.findByTestId("draft-summary");
    expect(calls.some((c) => c.url === "/aois/upload?preview=true")).toBe(true);
  });

  it("selects a saved AOI onto the map and deletes after confirmation", async () => {
    let deleted = false;
    const calls = mockApi({
      "GET /aois/limits": () => ({ body: LIMITS }),
      "GET /aois?": () => ({ body: { items: deleted ? [] : [SAVED], total: deleted ? 0 : 1 } }),
      [`GET /aois/${SAVED.id}`]: () => ({ body: { ...DRAFT, ...SAVED } }),
      [`DELETE /aois/${SAVED.id}`]: () => {
        deleted = true;
        return { status: 204, body: null };
      },
    });
    render(<AoiWorkbench MapComponent={MapStub} />);
    await userEvent.click(await screen.findByRole("button", { name: /^Site A \(/ }));
    await waitFor(() => expect(lastMapProps.saved).toEqual(GEOM));
    await userEvent.click(screen.getByRole("button", { name: "Delete Site A" }));
    await waitFor(() => expect(screen.getByText(/Saved AOIs \(0\)/)).toBeInTheDocument());
    expect(window.confirm).toHaveBeenCalled();
    expect(calls.some((c) => c.init?.method === "DELETE")).toBe(true);
    expect(lastMapProps.saved).toBeNull();
  });

  it("does not delete when the confirmation is declined", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const calls = mockApi(base());
    render(<AoiWorkbench MapComponent={MapStub} />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete Site A" }));
    expect(calls.some((c) => c.init?.method === "DELETE")).toBe(false);
  });

  it("contains no analysis or result wording in the UI", async () => {
    mockApi(base());
    const { container } = render(<AoiWorkbench MapComponent={MapStub} />);
    await screen.findByText(/Saved AOIs/);
    expect(container.textContent).not.toMatch(
      /prospectiv|anomal|confidence|score|target|gold|void|cave|depth/i,
    );
  });
});
