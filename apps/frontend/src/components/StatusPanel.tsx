"use client";

import { useCallback, useEffect, useState } from "react";

import { TERMINAL, createNoopJob, getJob, getReadiness, type Readiness } from "@/lib/api";
import type { Job } from "@/types/contracts";

export function StatusPanel() {
  const [ready, setReady] = useState<Readiness | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getReadiness()
      .then(setReady)
      .catch(() => setReady({ status: "unavailable" }));
  }, []);

  useEffect(() => {
    if (!job || (TERMINAL as readonly string[]).includes(job.status)) return;
    const timer = setInterval(() => {
      getJob(job.id)
        .then(setJob)
        .catch((e: Error) => setError(e.message));
    }, 1000);
    return () => clearInterval(timer);
  }, [job]);

  const submit = useCallback(async () => {
    setError(null);
    try {
      setJob(await createNoopJob());
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  return (
    <section>
      <h2>Backend status</h2>
      <p data-testid="readiness">{ready ? `${ready.status}` : "checking…"}</p>
      <h2>Test job</h2>
      <p>Submits a no-op job to verify the queue and worker. It produces no scientific result.</p>
      <button type="button" onClick={submit}>
        Submit noop job
      </button>
      {job && (
        <p data-testid="job-status">
          Job {job.id}: {job.status}
        </p>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
