import { deleteMonitor, deleteReport, getMonitors, publishReportToDestination } from "@/lib/api";

describe("api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("treats 204 delete responses as success without parsing JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(null, {
        status: 204,
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteMonitor("monitor-1")).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/monitors/monitor-1",
      expect.objectContaining({
        method: "DELETE",
      })
    );
  });

  it("parses JSON responses when the body is present", async () => {
    const monitors = [{ id: "monitor-1", name: "Daily AI Brief" }];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(monitors), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
    );

    await expect(getMonitors()).resolves.toEqual(monitors);
  });

  it("treats report delete 204 responses as success without parsing JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(null, {
        status: 204,
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteReport("report-1")).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/reports/report-1",
      expect.objectContaining({
        method: "DELETE",
      })
    );
  });

  it("surfaces backend detail messages on failed publish requests", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: {
              message: "Obsidian vault is not writable",
              report: { id: "report-1" },
            },
          }),
          {
            status: 502,
            headers: { "Content-Type": "application/json" },
          }
        )
      )
    );

    await expect(publishReportToDestination("report-1", ["dest-1"])).rejects.toMatchObject({
      message: "Obsidian vault is not writable",
    });
  });

  it("falls back to status-based APIError when failed response body is not json", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<html>bad gateway</html>", {
          status: 502,
          headers: { "Content-Type": "text/html" },
        })
      )
    );

    await expect(publishReportToDestination("report-1", ["dest-1"])).rejects.toMatchObject({
      message: "API Error: 502",
      status: 502,
    });
  });
});
