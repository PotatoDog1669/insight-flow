import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import MonitorsPage from "@/app/monitors/page";
import {
  createMonitor,
  getDestinations,
  getMonitorLogs,
  getMonitorRunEvents,
  getMonitorRuns,
  getMonitors,
  getProviders,
  getSources,
  updateMonitor,
} from "@/lib/api";

vi.mock("@/lib/api", () => ({
  getMonitors: vi.fn(),
  getSources: vi.fn(),
  getProviders: vi.fn(),
  getDestinations: vi.fn(),
  getMonitorLogs: vi.fn(),
  getMonitorRuns: vi.fn(),
  getMonitorRunEvents: vi.fn(),
  getMonitorAIRoutingDefaults: vi.fn(),
  cancelMonitorRun: vi.fn(),
  createMonitor: vi.fn(),
  updateMonitor: vi.fn(),
  runMonitor: vi.fn(),
  deleteMonitor: vi.fn(),
}));

const mockedGetMonitors = vi.mocked(getMonitors);
const mockedGetSources = vi.mocked(getSources);
const mockedGetProviders = vi.mocked(getProviders);
const mockedGetDestinations = vi.mocked(getDestinations);
const mockedGetMonitorLogs = vi.mocked(getMonitorLogs);
const mockedGetMonitorRuns = vi.mocked(getMonitorRuns);
const mockedGetMonitorRunEvents = vi.mocked(getMonitorRunEvents);
const mockedCreateMonitor = vi.mocked(createMonitor);
const mockedUpdateMonitor = vi.mocked(updateMonitor);

describe("MonitorsPage AI provider flow", () => {
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
        destination_instance_ids: ["dest-notion-1"],
        window_hours: 24,
        custom_schedule: null,
        source_overrides: {},
        ai_routing: {
          stages: {
            filter: { primary: "llm_openai" },
            keywords: { primary: "llm_openai" },
            global_summary: { primary: "llm_openai" },
            report: { primary: "llm_openai" },
          },
          providers: {},
        },
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
        id: "dest-notion-1",
        name: "Notion",
        type: "notion",
        description: "Notion destination",
        config: {},
        enabled: true,
      },
    ] as never);
    mockedGetProviders.mockResolvedValue([
      {
        id: "llm_codex",
        name: "LLM Codex",
        type: "llm",
        description: "Codex provider",
        enabled: false,
        config: {
          auth_mode: "api_key",
          base_url: "https://api.openai.com/v1",
          model: "gpt-5-codex",
          timeout_sec: 120,
          max_retry: 2,
          max_output_tokens: 2048,
          temperature: 0.3,
          api_key: "",
        },
      },
      {
        id: "llm_openai",
        name: "LLM OpenAI",
        type: "llm",
        description: "OpenAI provider",
        enabled: true,
        config: {
          auth_mode: "api_key",
          base_url: "https://api.openai.com/v1",
          model: "gpt-4o-mini",
          timeout_sec: 120,
          max_retry: 2,
          max_output_tokens: 2048,
          temperature: 0.3,
          api_key: "",
        },
      },
    ] as never);
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
      destination_instance_ids: ["dest-notion-1"],
      window_hours: 24,
      custom_schedule: null,
      source_overrides: {},
      ai_routing: {
        stages: {
          filter: { primary: "llm_codex" },
          keywords: { primary: "llm_codex" },
          global_summary: { primary: "llm_codex" },
          report: { primary: "llm_codex" },
        },
        providers: {},
      },
      enabled: true,
      status: "active",
      last_run: null,
      created_at: "2026-03-02T10:00:00Z",
      updated_at: "2026-03-02T10:00:00Z",
    } as never);
    mockedUpdateMonitor.mockResolvedValue({
      id: "monitor-1",
      name: "Daily AI Brief",
      time_period: "daily",
      report_type: "daily",
      source_ids: ["source-1"],
      destination_ids: ["notion"],
      destination_instance_ids: ["dest-notion-1"],
      window_hours: 24,
      custom_schedule: null,
      source_overrides: {},
      ai_routing: {
        stages: {
          filter: { primary: "llm_openai" },
          keywords: { primary: "llm_openai" },
          global_summary: { primary: "llm_openai" },
          report: { primary: "llm_openai" },
        },
        providers: {},
      },
      enabled: true,
      status: "active",
      last_run: null,
      created_at: "2026-03-02T10:00:00Z",
      updated_at: "2026-03-02T10:00:00Z",
    } as never);
  });

  it("shows a single AI provider selector with supported options only", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));

    const providerSelect = screen.getByLabelText("AI 提供商");
    const optionTexts = Array.from(providerSelect.querySelectorAll("option")).map((option) => option.textContent?.trim() ?? "");

    expect(screen.getByText("监控任务全链路统一使用一个 AI 提供商，不再分别配置过滤、关键词、摘要和报告阶段。")).toBeInTheDocument();
    expect(optionTexts).toEqual(["llm_codex", "llm_openai"]);
    expect(screen.queryByLabelText("Filter stage provider")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Global summary stage provider")).not.toBeInTheDocument();
  });

  it("warns when the selected provider is disabled but still allows saving", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "Routing Warning Monitor" },
    });
    fireEvent.click(screen.getByLabelText("OpenAI Blog"));
    fireEvent.change(screen.getByLabelText("AI 提供商"), {
      target: { value: "llm_codex" },
    });

    expect(screen.getByText("当前选择的 provider 尚未启用，任务可以保存，但运行时可能失败。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "创建" })).toBeEnabled();
  });

  it("loads the simplified ai provider from existing routing when editing", async () => {
    mockedGetMonitors.mockResolvedValueOnce([
      {
        id: "monitor-1",
        name: "Daily AI Brief",
        time_period: "daily",
        report_type: "daily",
        source_ids: ["source-1"],
        destination_ids: ["notion"],
        destination_instance_ids: ["dest-notion-1"],
        window_hours: 24,
        custom_schedule: null,
        source_overrides: {},
        ai_routing: {
          stages: {
            filter: { primary: "llm_codex" },
          },
          providers: {},
        },
        enabled: true,
        status: "active",
        last_run: null,
        created_at: "2026-03-02T10:00:00Z",
        updated_at: "2026-03-02T10:00:00Z",
      },
    ] as never);

    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Daily AI Brief"));
    expect(await screen.findByRole("heading", { name: "编辑任务" })).toBeInTheDocument();

    expect(screen.getByLabelText("AI 提供商")).toHaveValue("llm_codex");
    expect(screen.getByText("当前选择的 provider 尚未启用，任务可以保存，但运行时可能失败。")).toBeInTheDocument();
  });

  it("submits the selected provider across all AI routing stages on create", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "Routing Monitor" },
    });
    fireEvent.click(screen.getByLabelText("OpenAI Blog"));
    fireEvent.change(screen.getByLabelText("AI 提供商"), {
      target: { value: "llm_codex" },
    });
    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => {
      expect(mockedCreateMonitor).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Routing Monitor",
          ai_routing: {
            stages: {
              filter: { primary: "llm_codex" },
              keywords: { primary: "llm_codex" },
              global_summary: { primary: "llm_codex" },
              report: { primary: "llm_codex" },
            },
          },
        })
      );
    });
  });

  it("submits the updated provider across all AI routing stages on edit", async () => {
    mockedGetMonitors.mockResolvedValueOnce([
      {
        id: "monitor-1",
        name: "Daily AI Brief",
        time_period: "daily",
        report_type: "daily",
        source_ids: ["source-1"],
        destination_ids: ["notion"],
        destination_instance_ids: ["dest-notion-1"],
        window_hours: 24,
        custom_schedule: null,
        source_overrides: {},
        ai_routing: {
          stages: {
            filter: { primary: "llm_codex" },
          },
          providers: {},
        },
        enabled: true,
        status: "active",
        last_run: null,
        created_at: "2026-03-02T10:00:00Z",
        updated_at: "2026-03-02T10:00:00Z",
      },
    ] as never);

    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Daily AI Brief"));
    expect(await screen.findByRole("heading", { name: "编辑任务" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("AI 提供商"), {
      target: { value: "llm_openai" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(mockedUpdateMonitor).toHaveBeenCalledWith(
        "monitor-1",
        expect.objectContaining({
          ai_routing: {
            stages: {
              filter: { primary: "llm_openai" },
              keywords: { primary: "llm_openai" },
              global_summary: { primary: "llm_openai" },
              report: { primary: "llm_openai" },
            },
          },
        })
      );
    });
  });
});
