import {
  deleteMonitor,
  deleteReport,
  getMonitors,
  publishReportToDestination,
  sendMonitorAgentMessage,
  streamMonitorAgentMessage,
} from "@/lib/api";

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
      "http://127.0.0.1:8000/api/v1/monitors/monitor-1",
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

  it("uses the backend port directly for localhost browser sessions when no API base is configured", async () => {
    const originalLocation = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      value: new URL("http://localhost:3018/providers"),
    });
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(getMonitors()).resolves.toEqual([]);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/monitors",
      expect.objectContaining({
        headers: { "Content-Type": "application/json" },
      })
    );

    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation,
    });
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
      "http://127.0.0.1:8000/api/v1/reports/report-1",
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

  it("posts monitor agent messages to the monitor agent endpoint", async () => {
    const responseBody = {
      mode: "clarify",
      conversation_id: "conv-1",
      message: "请再具体一点",
      missing_or_conflicting_fields: ["topic_scope"],
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(responseBody), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendMonitorAgentMessage({ message: "track ai agents" })).resolves.toEqual(responseBody);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/monitors/agent",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message: "track ai agents" }),
      })
    );
  });

  it("streams monitor agent progress events and final responses from the streaming endpoint", async () => {
    const encoder = new TextEncoder();
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        new ReadableStream({
          start(controller) {
            controller.enqueue(
              encoder.encode(
                [
                  JSON.stringify({ type: "status", key: "understand", label: "理解需求", status: "running" }),
                  JSON.stringify({ type: "message_delta", delta: "我先按当前理解" }),
                  JSON.stringify({
                    type: "final",
                    response: {
                      mode: "clarify",
                      conversation_id: "conv-1",
                      message: "请再具体一点",
                      missing_or_conflicting_fields: ["topic_scope"],
                    },
                  }),
                ].join("\n") + "\n"
              )
            );
            controller.close();
          },
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/x-ndjson" },
        }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const onStatus = vi.fn();
    const onMessageDelta = vi.fn();
    const onFinal = vi.fn();

    await expect(
      streamMonitorAgentMessage(
        { message: "track ai agents" },
        {
          onStatus,
          onMessageDelta,
          onFinal,
        }
      )
    ).resolves.toEqual({
      mode: "clarify",
      conversation_id: "conv-1",
      message: "请再具体一点",
      missing_or_conflicting_fields: ["topic_scope"],
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/monitors/agent/stream",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message: "track ai agents" }),
      })
    );
    expect(onStatus).toHaveBeenCalledWith({
      type: "status",
      key: "understand",
      label: "理解需求",
      status: "running",
    });
    expect(onMessageDelta).toHaveBeenCalledWith({
      type: "message_delta",
      delta: "我先按当前理解",
    });
    expect(onFinal).toHaveBeenCalled();
  });
});
