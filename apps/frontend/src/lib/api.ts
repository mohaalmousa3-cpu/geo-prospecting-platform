import type { Job } from "@/types/contracts";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export interface Readiness {
  status: string;
  database?: string;
}

export async function getReadiness(base: string = API_BASE): Promise<Readiness> {
  const res = await fetch(`${base}/health/ready`, { cache: "no-store" });
  const body = (await res.json()) as Readiness;
  return { ...body, status: res.ok ? body.status : "unavailable" };
}

export async function createNoopJob(base: string = API_BASE): Promise<Job> {
  const res = await fetch(`${base}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "noop" }),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as { error?: { message?: string } } | null;
    throw new Error(err?.error?.message ?? `request failed (${res.status})`);
  }
  return (await res.json()) as Job;
}

export async function getJob(id: string, base: string = API_BASE): Promise<Job> {
  const res = await fetch(`${base}/jobs/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`request failed (${res.status})`);
  return (await res.json()) as Job;
}

export const TERMINAL = ["succeeded", "failed", "cancelled", "insufficient_data"] as const;
