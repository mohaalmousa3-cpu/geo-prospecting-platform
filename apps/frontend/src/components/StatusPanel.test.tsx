import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Disclaimer } from "./Disclaimer";
import { StatusPanel } from "./StatusPanel";

const job = (status: string) => ({
  id: "11111111-1111-1111-1111-111111111111",
  type: "noop",
  status,
  priority: 0,
  attempts: 0,
  max_attempts: 2,
  cancel_requested: false,
  created_at: "2026-01-01T00:00:00Z",
});

afterEach(() => vi.restoreAllMocks());

describe("StatusPanel", () => {
  it("shows backend readiness", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok", database: "ok" }) }),
    );
    render(<StatusPanel />);
    await waitFor(() => expect(screen.getByTestId("readiness")).toHaveTextContent("ok"));
  });

  it("shows unavailable when the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    render(<StatusPanel />);
    await waitFor(() => expect(screen.getByTestId("readiness")).toHaveTextContent("unavailable"));
  });

  it("submits a noop job and displays its status", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: "ok" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => job("queued") });
    vi.stubGlobal("fetch", fetchMock);
    render(<StatusPanel />);
    await userEvent.click(screen.getByRole("button", { name: /submit noop job/i }));
    await waitFor(() => expect(screen.getByTestId("job-status")).toHaveTextContent("queued"));
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "POST" });
  });

  it("surfaces queue-full errors", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: "ok" }) })
      .mockResolvedValueOnce({
        ok: false,
        status: 429,
        json: async () => ({ error: { message: "queue is full (MAX_QUEUED_JOBS=10)" } }),
      });
    vi.stubGlobal("fetch", fetchMock);
    render(<StatusPanel />);
    await userEvent.click(screen.getByRole("button", { name: /submit noop job/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("MAX_QUEUED_JOBS"));
  });
});

describe("Disclaimer", () => {
  it("states results are not confirmation", () => {
    render(<Disclaimer />);
    expect(screen.getByRole("note")).toHaveTextContent(/not confirmation of mineralisation/i);
  });
});
