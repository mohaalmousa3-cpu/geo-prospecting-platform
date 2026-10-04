import { API_BASE } from "@/lib/api";
import type {
  Aoi,
  AoiDraft,
  AoiLimits,
  AoiList,
  AoiPointRadiusRequest,
  AoiPolygonRequest,
  AoiRectangleRequest,
} from "@/types/contracts";

export type AoiRequest = AoiPointRadiusRequest | AoiRectangleRequest | AoiPolygonRequest;

/** Error returned by the API (`{error:{code,message}}`), or a network failure (`network_error`). */
export class AoiApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "AoiApiError";
  }
}

async function request<T>(path: string, init?: RequestInit, base: string = API_BASE): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${base}${path}`, { cache: "no-store", ...init });
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

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const getLimits = () => request<AoiLimits>("/aois/limits");
export const previewAoi = (req: AoiRequest) => request<AoiDraft>("/aois/preview", json(req));
export const createAoi = (req: AoiRequest) => request<Aoi>("/aois", json(req));
export const listAois = (limit = 50, offset = 0) =>
  request<AoiList>(`/aois?limit=${limit}&offset=${offset}`);
export const getAoi = (id: string) => request<Aoi>(`/aois/${id}`);
export const deleteAoi = (id: string) => request<void>(`/aois/${id}`, { method: "DELETE" });

export function uploadAoi(file: File, name: string, preview: true): Promise<AoiDraft>;
export function uploadAoi(file: File, name: string, preview: false): Promise<Aoi>;
export function uploadAoi(file: File, name: string, preview: boolean): Promise<Aoi | AoiDraft> {
  const form = new FormData();
  form.append("file", file);
  if (name.trim()) form.append("name", name.trim());
  return request<Aoi | AoiDraft>(`/aois/upload${preview ? "?preview=true" : ""}`, {
    method: "POST",
    body: form,
  });
}
