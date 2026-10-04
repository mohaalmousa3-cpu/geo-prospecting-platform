import { expect, test, type APIRequestContext, type Dialog } from "@playwright/test";

const API = "http://127.0.0.1:8000/api/v1";
const PREFIX = "e2e-";

async function purge(request: APIRequestContext) {
  const list = (await (await request.get(`${API}/projects`)).json()) as {
    items: { id: string; name: string }[];
  };
  for (const p of list.items.filter((x) => x.name.startsWith(PREFIX)))
    await request.delete(`${API}/projects/${p.id}?delete_aois=true`);
}

test.beforeAll(async ({ request }) => purge(request)); // residue from an earlier failed run
test.afterAll(async ({ request }) => purge(request));

test("browser ↔ backend: project and AOI lifecycle, with explicit cascade confirmation", async ({
  page,
  request,
}) => {
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  page.on("pageerror", (e) => pageErrors.push(e.message));
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
  const dialogs: string[] = [];
  let answer: "accept" | "dismiss" = "accept";
  page.on("dialog", async (d: Dialog) => {
    dialogs.push(d.message());
    await (answer === "accept" ? d.accept() : d.dismiss());
  });

  const projectName = `${PREFIX}${Date.now()}`;
  const projectSelect = page.getByRole("combobox", { name: "Project" });
  const apiProject = async () => {
    const list = (await (await request.get(`${API}/projects`)).json()) as {
      items: { id: string; name: string; aoi_count: number }[];
    };
    return list.items.find((p) => p.name === projectName);
  };
  const createAoi = async (name: string) => {
    await page.getByLabel("Latitude").fill("30");
    await page.getByLabel("Longitude").fill("10");
    await page.getByLabel("Radius (m)").fill("1000");
    await page.getByRole("button", { name: "Validate" }).click();
    await expect(page.getByTestId("draft-summary")).toBeVisible();
    await page.getByLabel("Name", { exact: true }).fill(name);
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(page.getByText(`Saved “${name}”.`)).toBeVisible();
  };

  await test.step("frontend ↔ backend connectivity in a real browser session", async () => {
    await page.goto("/status");
    await expect(page.getByTestId("readiness")).toHaveText("ok"); // cross-origin GET, CORS allow-list
    await page.goto("/");
    await expect(page.getByText(/up to 25 km²/)).toBeVisible(); // limits loaded from the API
    await expect(page.locator(".maplibregl-canvas")).toBeVisible(); // MapLibre + its worker started
    await expect(page.getByTestId("basemap-note")).toContainText("No basemap"); // default is none
  });

  await test.step("create project", async () => {
    await page.getByLabel("New project name").fill(projectName);
    await page.getByRole("button", { name: "Create project" }).click();
    await expect(page.getByText(`Created project “${projectName}”.`)).toBeVisible();
    await expect(projectSelect).toContainText(projectName);
    expect(await apiProject()).toMatchObject({ aoi_count: 0 });
  });

  await test.step("create AOI", async () => {
    await createAoi("e2e circle 1");
    await expect(projectSelect).toContainText(`${projectName} (1 AOI)`);
    const p = await apiProject();
    expect(p?.aoi_count).toBe(1);
    const aois = (await (await request.get(`${API}/aois?project_id=${p!.id}`)).json()) as {
      total: number;
    };
    expect(aois.total).toBe(1);
  });

  await test.step("delete AOI (browser DELETE passes CORS preflight)", async () => {
    await page.getByRole("button", { name: "Delete e2e circle 1" }).click();
    await expect(page.getByText(/Saved AOIs \(0\)/)).toBeVisible();
    await expect(projectSelect).toContainText(`${projectName} (0 AOIs)`);
    expect((await apiProject())?.aoi_count).toBe(0);
  });

  await test.step("delete project: cascade needs explicit confirmation", async () => {
    await createAoi("e2e circle 2");
    const p = (await apiProject())!;
    expect(p.aoi_count).toBe(1);

    answer = "dismiss"; // declining must change nothing
    await page.getByRole("button", { name: "Delete project" }).click();
    await expect.poll(() => dialogs.length).toBeGreaterThan(0);
    expect(dialogs.at(-1)).toContain(`Delete project “${projectName}” AND its 1 AOI(s)`);
    expect((await apiProject())?.aoi_count).toBe(1);

    answer = "accept"; // confirming removes the project and its AOIs
    await page.getByRole("button", { name: "Delete project" }).click();
    await expect(projectSelect).not.toContainText(projectName);
    expect(await apiProject()).toBeUndefined();
    expect((await request.get(`${API}/projects/${p.id}`)).status()).toBe(404);
    const left = (await (await request.get(`${API}/aois?project_id=${p.id}`)).json()) as {
      total: number;
    };
    expect(left.total).toBe(0);
  });

  await test.step("no uncaught page errors or failing requests during the whole flow", async () => {
    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]); // includes "Worker failed to load" and blocked-by-CORS errors
  });
});
