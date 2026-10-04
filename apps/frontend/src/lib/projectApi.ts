import { API_BASE } from "@/lib/api";
import { AoiApiError } from "@/lib/aoiApi";
import type { Project, ProjectCreateRequest, ProjectList } from "@/types/contracts";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { cache: "no-store", ...init });
  } catch {
    throw new AoiApiError("network_error", "Cannot reach the backend.", 0);
  }
  if (res.status === 204) return undefined as T;
  const body = (await res.json().catch(() => null)) as {
    error?: { code?: string; message?: string };
  } | null;
  if (!res.ok) {
    throw new AoiApiError(
      body?.error?.code ?? `http_${res.status}`,
      body?.error?.message ?? `Request failed (${res.status}).`,
      res.status,
    );
  }
  return body as T;
}

export const listProjects = () => request<ProjectList>("/projects");

export const createProject = (req: ProjectCreateRequest) =>
  request<Project>("/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });

/** `deleteAois` must be true to delete a project that still contains AOIs. */
export const deleteProject = (id: string, deleteAois = false) =>
  request<void>(`/projects/${id}${deleteAois ? "?delete_aois=true" : ""}`, { method: "DELETE" });
