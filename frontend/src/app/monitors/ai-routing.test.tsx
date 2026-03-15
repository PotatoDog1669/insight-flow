import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import MonitorsPage from "@/app/monitors/page";
import {
  createMonitor,
  getDestinations,
  getMonitorAIRoutingDefaults,
  getMonitorLogs,
  getMonitorRunEvents,
  getMonitorRuns,
  getMonitors,
  getSources,
} from "@/lib/api";

vi.mock("@/lib/api", () => ({
  getMonitors: vi.fn(),
  getSources: vi.fn(),
  getDestinations: vi.fn(),
  getMonitorAIRoutingDefaults: vi.fn(),
  getMonitorLogs: vi.fn(),
  getMonitorRuns: vi.fn(),
  getMonitorRunEvents: vi.fn(),
  cancelMonitorRun: vi.fn(),
  createMonitor: vi.fn(),
  updateMonitor: vi.fn(),
  runMonitor: vi.fn(),
  deleteMonitor: vi.fn(),
}));

const mockedGetMonitors = vi.mocked(getMonitors);
const mockedGetSources = vi.mocked(getSources);
const mockedGetDestinations = vi.mocked(getDestinations);
const mockedGetMonitorAIRoutingDefaults = vi.mocked(getMonitorAIRoutingDefaults);
const mockedGetMonitorLogs = vi.mocked(getMonitorLogs);
const mockedGetMonitorRuns = vi.mocked(getMonitorRuns);
const mockedGetMonitorRunEvents = vi.mocked(getMonitorRunEvents);
const mockedCreateMonitor = vi.mocked(createMonitor);

describe("MonitorsPage AI routing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetMonitors.mockResolvedValue([
      {
        id: "monitor-1",
        name: "Daily AI Brief",
        time_period: "daily",
        report_type: "daily",
        source_ids: ["source-1"],
        destination_ids: ["notion"],
        window_hours: 24,
        custom_schedule: null,
        enabled: true,
        status: "active",
        last_run: null,
        created_at: "2026-03-02T10:00:00Z",
        updated_at: "2026-03-02T10:00:00Z",
      },
    ] as never);
    mockedGetSources.mockResolvedValue([
      {
        id: "source-1",
        name: "OpenAI Blog",
        category: "news",
        collect_method: "rss",
        config: {},
        enabled: true,
        status: "healthy",
        last_run: null,
        last_collected: null,
        created_at: "2026-03-02T10:00:00Z",
        updated_at: "2026-03-02T10:00:00Z",
      },
    ] as never);
    mockedGetDestinations.mockResolvedValue([
      {
        id: "notion",
        name: "Notion",
        type: "notion",
        description: "Notion destination",
        config: {},
        enabled: true,
      },
    ] as never);
    mockedGetMonitorAIRoutingDefaults.mockResolvedValue({
      profile_name: "stable_v1",
      stages: {
        filter: "llm_openai",
        keywords: "llm_openai",
        global_summary: "llm_openai",
        report: "llm_openai",
      },
    } as never);
    mockedGetMonitorLogs.mockResolvedValue([] as never);
    mockedGetMonitorRuns.mockResolvedValue([] as never);
    mockedGetMonitorRunEvents.mockResolvedValue([] as never);
    mockedCreateMonitor.mockResolvedValue({
      id: "monitor-2",
      name: "Routing Monitor",
      time_period: "daily",
      report_type: "daily",
      source_ids: ["source-1"],
      destination_ids: [],
      window_hours: 24,
      custom_schedule: null,
      source_overrides: {},
      ai_routing: {
        stages: {
          filter: { primary: "llm_openai" },
          keywords: { primary: "llm_openai" },
          global_summary: { primary: "llm_codex" },
          report: { primary: "llm_codex" },
        },
        providers: {
          llm_openai: { model: "gpt-4o-mini" },
          llm_codex: { model: "gpt-5-codex" },
        },
      },
      enabled: true,
      status: "active",
      last_run: null,
      created_at: "2026-03-02T10:00:00Z",
      updated_at: "2026-03-02T10:00:00Z",
    } as never);
  });

  it("shows llm_codex in routing selects and inherit defaults", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    expect(await screen.findByRole("heading", { name: "创建任务" })).toBeInTheDocument();

    const optionTexts = screen.getAllByRole("option").map((option) => option.textContent?.trim() ?? "");
    expect(optionTexts).toContain("llm_codex");
    expect(optionTexts).toContain("llm_openai");
    expect(optionTexts).toContain("inherit (current: llm_openai)");
  });

  it("submits llm_codex for global summary and report stages", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "Routing Monitor" },
    });
    fireEvent.click(screen.getByLabelText("OpenAI Blog"));

    fireEvent.change(screen.getByLabelText("Filter stage provider"), {
      target: { value: "llm_openai" },
    });
    fireEvent.change(screen.getByLabelText("Keywords stage provider"), {
      target: { value: "llm_openai" },
    });
    fireEvent.change(screen.getByLabelText("Global summary stage provider"), {
      target: { value: "llm_codex" },
    });
    fireEvent.change(screen.getByLabelText("Report stage provider"), {
      target: { value: "llm_codex" },
    });
    fireEvent.change(screen.getByLabelText("Model for llm_openai"), {
      target: { value: "gpt-4o-mini" },
    });
    fireEvent.change(screen.getByLabelText("Model for llm_codex"), {
      target: { value: "gpt-5-codex" },
    });

    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => {
      expect(mockedCreateMonitor).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Routing Monitor",
          ai_routing: {
            stages: {
              filter: { primary: "llm_openai" },
              keywords: { primary: "llm_openai" },
              global_summary: { primary: "llm_codex" },
              report: { primary: "llm_codex" },
            },
            providers: {
              llm_openai: { model: "gpt-4o-mini" },
              llm_codex: { model: "gpt-5-codex" },
            },
          },
        })
      );
    });
  });
});
