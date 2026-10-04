// MapLibre v6 spawns an ES-module worker. Turbopack/webpack rewrite the default worker URL and
// break it ("Worker failed to load"), so we serve the worker files as static assets instead and
// point MapLibre at them with setWorkerUrl(). Output is generated (git-ignored) into public/maplibre.
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "node_modules", "maplibre-gl", "dist");
const dest = join(root, "public", "maplibre");
mkdirSync(dest, { recursive: true });
for (const f of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"])
  copyFileSync(join(src, f), join(dest, f));
console.log("copied MapLibre worker files to public/maplibre");
