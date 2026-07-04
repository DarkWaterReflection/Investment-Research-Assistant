import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, getStatus, startResearch } from "./api";

function mockFetch(status: number, body: unknown) {
  const response = new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
  const spy = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("startResearch", () => {
  it("posts the company and returns the created job", async () => {
    const spy = mockFetch(202, {
      job_id: "abc",
      status: "queued",
      status_url: "/status/abc",
      report_url: "/report/abc",
    });

    const created = await startResearch({ company: "Acme Robotics", ticker: "ACME" });

    expect(created.job_id).toBe("abc");
    const [url, init] = spy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/research");
    expect(JSON.parse(init.body as string)).toEqual({ company: "Acme Robotics", ticker: "ACME" });
  });

  it("omits empty optional fields from the payload", async () => {
    const spy = mockFetch(202, { job_id: "x", status: "queued", status_url: "", report_url: "" });

    await startResearch({ company: "Acme Robotics" });

    const [, init] = spy.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ company: "Acme Robotics" });
  });

  it("surfaces the API's error detail", async () => {
    mockFetch(503, { detail: "LLM provider not configured" });

    await expect(startResearch({ company: "Acme" })).rejects.toThrowError(
      "LLM provider not configured",
    );
  });
});

describe("getStatus", () => {
  it("raises a typed error with the HTTP status", async () => {
    mockFetch(404, { detail: "Unknown job id 'nope'." });

    const failure = getStatus("nope");

    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({ status: 404 });
  });
});
