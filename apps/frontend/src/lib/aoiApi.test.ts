import { afterEach, describe, expect, it, vi } from "vitest";

import { AoiApiError, createAoi, deleteAoi, previewAoi, uploadAoi } from "./aoiApi";

afterEach(() => vi.unstubAllGlobals());

const ok = (body: unknown, status = 200) => ({ ok: true, status, json: async () => body });

describe("aoiApi", () => {
  it("posts JSON for preview", async () => {
    const f = vi.fn().mockResolvedValue(ok({ area_km2: 1 }));
    vi.stubGlobal("fetch", f);
    await previewAoi({ method: "point_radius", lat: 1, lon: 2, radius_m: 100 });
    expect(f.mock.calls[0][0]).toMatch(/\/aois\/preview$/);
    expect(JSON.parse(f.mock.calls[0][1].body)).toEqual({
      method: "point_radius",
      lat: 1,
      lon: 2,
      radius_m: 100,
    });
  });

  it("turns API errors into AoiApiError with code and message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({
          error: { code: "area_too_large", message: "AOI area 40 exceeds MAX_AOI_AREA_KM2=25" },
        }),
      }),
    );
    await expect(
      createAoi({ method: "rectangle", west: 0, south: 0, east: 1, north: 1 }),
    ).rejects.toMatchObject({
      code: "area_too_large",
      status: 422,
      message: expect.stringContaining("MAX_AOI_AREA_KM2=25"),
    });
  });

  it("reports unreachable backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    await expect(deleteAoi("x")).rejects.toBeInstanceOf(AoiApiError);
    await expect(deleteAoi("x")).rejects.toMatchObject({ code: "network_error" });
  });

  it("handles 204 on delete", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 204, json: async () => null }),
    );
    await expect(deleteAoi("x")).resolves.toBeUndefined();
  });

  it("uploads as multipart, with preview flag and optional name", async () => {
    const f = vi.fn().mockResolvedValue(ok({ area_km2: 1 }));
    vi.stubGlobal("fetch", f);
    const file = new File(["{}"], "a.geojson");
    await uploadAoi(file, "  My site ", true);
    expect(f.mock.calls[0][0]).toMatch(/\/aois\/upload\?preview=true$/);
    const form = f.mock.calls[0][1].body as FormData;
    expect(form.get("name")).toBe("My site");
    expect((form.get("file") as File).name).toBe("a.geojson");
    await uploadAoi(file, "", false, "proj-1");
    expect(f.mock.calls[1][0]).toMatch(/\/aois\/upload$/);
    const form2 = f.mock.calls[1][1].body as FormData;
    expect(form2.has("name")).toBe(false);
    expect(form2.get("project_id")).toBe("proj-1");
  });
});
