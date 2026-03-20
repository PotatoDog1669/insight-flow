import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import MonitorsPage from "@/app/monitors/page";
import {
  cancelMonitorRun,
  createMonitor,
  deleteMonitor,
  getProviders,
  getMonitorAIRoutingDefaults,
  getDestinations,
  getMonitorLogs,
  getMonitorRunEvents,
  getMonitorRuns,
  getMonitors,
  getSources,
  runMonitor,
  updateMonitor,
} from "@/lib/api";

vi.mock("@/lib/api", () => ({
  getMonitors: vi.fn(),
  getSources: vi.fn(),
  getProviders: vi.fn(),
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
const mockedGetProviders = vi.mocked(getProviders);
const mockedGetDestinations = vi.mocked(getDestinations);
const mockedGetMonitorAIRoutingDefaults = vi.mocked(getMonitorAIRoutingDefaults);
const mockedGetMonitorLogs = vi.mocked(getMonitorLogs);
const mockedGetMonitorRuns = vi.mocked(getMonitorRuns);
const mockedGetMonitorRunEvents = vi.mocked(getMonitorRunEvents);
const mockedCancelMonitorRun = vi.mocked(cancelMonitorRun);
const mockedCreateMonitor = vi.mocked(createMonitor);
const mockedUpdateMonitor = vi.mocked(updateMonitor);
const mockedRunMonitor = vi.mocked(runMonitor);
const mockedDeleteMonitor = vi.mocked(deleteMonitor);

const expandAiRoutingSection = async () => {
  const toggle = screen.getByRole("button", { name: "AI 路由配置（高级）" });
  if (toggle.getAttribute("aria-expanded") !== "true") {
    fireEvent.click(toggle);
  }
  await screen.findByLabelText("Filter stage provider");
};

describe("MonitorsPage", () => {
  beforeEach(() => {
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
        enabled: true,
        status: "active",
        last_run: null,
        created_at: "2026-03-02T10:00:00Z",
        updated_at: "2026-03-02T10:00:00Z",
      },
    ]);
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
      {
        id: "source-2",
        name: "Anthropic Research",
        category: "research",
        collect_method: "rss",
        config: {},
        enabled: true,
        status: "healthy",
        last_run: null,
        last_collected: null,
        created_at: "2026-03-02T10:00:00Z",
        updated_at: "2026-03-02T10:00:00Z",
      },
      {
        id: "source-3",
        name: "DeepMind News",
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
      {
        id: "source-4",
        name: "Hugging Face Daily Papers",
        category: "open_source",
        collect_method: "huggingface",
        config: { limit: 30 },
        enabled: true,
        status: "healthy",
        last_run: null,
        last_collected: null,
        created_at: "2026-03-02T10:00:00Z",
        updated_at: "2026-03-02T10:00:00Z",
      },
      {
        id: "source-5",
        name: "arXiv",
        category: "academic",
        collect_method: "rss",
        config: { arxiv_api: true, max_results: 30, keywords: ["reasoning"] },
        enabled: true,
        status: "healthy",
        last_run: null,
        last_collected: null,
        created_at: "2026-03-02T10:00:00Z",
        updated_at: "2026-03-02T10:00:00Z",
      },
      {
        id: "source-6",
        name: "OpenAlex",
        category: "academic",
        collect_method: "openalex",
        config: {
          base_url: "https://api.openalex.org/works",
          max_results: 30,
          keywords: ["reasoning"],
          supports_time_window: true,
          auth_mode: "optional_api_key",
        },
        enabled: true,
        status: "healthy",
        last_run: null,
        last_collected: null,
        created_at: "2026-03-02T10:00:00Z",
        updated_at: "2026-03-02T10:00:00Z",
      },
      {
        id: "source-7",
        name: "Reddit",
        category: "social",
        collect_method: "rss",
        config: { subreddits: ["LocalLLaMA", "OpenAI", "MachineLearning"] },
        enabled: true,
        status: "healthy",
        last_run: null,
        last_collected: null,
        created_at: "2026-03-02T10:00:00Z",
        updated_at: "2026-03-02T10:00:00Z",
      },
    ]);
    mockedGetDestinations.mockResolvedValue([
      {
        id: "dest-notion-1",
        name: "Notion Workspace",
        type: "notion",
        description: "Notion destination",
        config: {},
        enabled: true,
      },
    ]);
    mockedGetProviders.mockResolvedValue([
      {
        id: "llm_codex",
        name: "LLM Codex",
        type: "llm",
        description: "Codex provider",
        enabled: false,
        config: {
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
          base_url: "https://api.openai.com/v1",
          model: "gpt-4o-mini",
          timeout_sec: 120,
          max_retry: 2,
          max_output_tokens: 2048,
          temperature: 0.3,
          api_key: "",
        },
      },
    ]);
    mockedGetMonitorAIRoutingDefaults.mockResolvedValue({
      profile_name: "stable_v1",
      stages: {
        filter: "llm_openai",
        keywords: "llm_openai",
        global_summary: "llm_openai",
        report: "llm_openai",
      },
    });
    mockedGetMonitorLogs.mockResolvedValue([
      {
        id: "task-1",
        run_id: "run-1",
        source_id: "source-1",
        trigger_type: "manual",
        status: "running",
        articles_count: 0,
        stage_trace: [{ stage: "collect", provider: "rss", status: "running" }],
        started_at: "2026-03-02T10:01:00Z",
      },
    ]);
    mockedGetMonitorRuns.mockResolvedValue([
      {
        run_id: "run-1",
        task_id: "task-1",
        trigger_type: "manual",
        status: "running",
        articles_count: 0,
        source_total: 1,
        source_done: 0,
        source_failed: 0,
        created_at: "2026-03-02T10:01:00Z",
        started_at: "2026-03-02T10:01:00Z",
        finished_at: null,
        error_message: null,
      },
    ]);
    mockedGetMonitorRunEvents.mockResolvedValue([
      {
        id: "event-1",
        run_id: "run-1",
        task_id: "task-1",
        source_id: "source-1",
        stage: "collect",
        level: "info",
        event_type: "source_started",
        message: "[OpenAI Blog] collect started",
        payload: {},
        created_at: "2026-03-02T10:01:00Z",
      },
    ]);
    mockedCreateMonitor.mockResolvedValue({
      id: "monitor-2",
      name: "Created",
      time_period: "daily",
      report_type: "daily",
      source_ids: ["source-1"],
      destination_ids: [],
      destination_instance_ids: [],
      window_hours: 24,
      custom_schedule: null,
      source_overrides: {},
      enabled: true,
      status: "active",
      last_run: null,
      created_at: "2026-03-02T10:00:00Z",
      updated_at: "2026-03-02T10:00:00Z",
    });
    mockedUpdateMonitor.mockResolvedValue({
      id: "monitor-1",
      name: "Updated monitor",
      time_period: "daily",
      report_type: "daily",
      source_ids: ["source-1"],
      destination_ids: ["notion"],
      destination_instance_ids: ["dest-notion-1"],
      window_hours: 24,
      custom_schedule: null,
      source_overrides: {},
      enabled: true,
      status: "active",
      last_run: null,
      created_at: "2026-03-02T10:00:00Z",
      updated_at: "2026-03-02T10:00:00Z",
    });
    mockedRunMonitor.mockResolvedValue({
      task_id: "task-1",
      run_id: "run-1",
      status: "running",
      monitor_id: "monitor-1",
    });
    mockedCancelMonitorRun.mockResolvedValue({
      run_id: "run-1",
      monitor_id: "monitor-1",
      status: "cancelling",
    });
    mockedDeleteMonitor.mockResolvedValue();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("opens edit modal from monitor card and saves updates", async () => {
    render(<MonitorsPage />);

    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Daily AI Brief"));

    expect(await screen.findByRole("heading", { name: "编辑任务" })).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "Updated monitor" },
    });

    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
        expect(mockedUpdateMonitor).toHaveBeenCalledWith(
        "monitor-1",
        expect.objectContaining({
          name: "Updated monitor",
          time_period: "daily",
          report_type: "daily",
          source_ids: ["source-1"],
          destination_instance_ids: ["dest-notion-1"],
        })
      );
    });
  });

  it("maps legacy destination ids onto destination instances when editing", async () => {
    mockedGetMonitors.mockResolvedValueOnce([
      {
        id: "monitor-1",
        name: "Daily AI Brief",
        time_period: "daily",
        report_type: "daily",
        source_ids: ["source-1"],
        destination_ids: ["notion"],
        destination_instance_ids: [],
        window_hours: 24,
        custom_schedule: null,
        source_overrides: {},
        enabled: true,
        status: "active",
        last_run: null,
        created_at: "2026-03-02T10:00:00Z",
        updated_at: "2026-03-02T10:00:00Z",
      },
    ]);

    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Daily AI Brief"));
    expect(await screen.findByRole("heading", { name: "编辑任务" })).toBeInTheDocument();

    const notionCheckbox = screen.getByRole("checkbox", { name: /Notion Workspace/i });
    expect(notionCheckbox).toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(mockedUpdateMonitor).toHaveBeenCalledWith(
        "monitor-1",
        expect.objectContaining({
          destination_instance_ids: ["dest-notion-1"],
        }),
      );
    });
  });

  it("groups sources by category in both create and edit modals", async () => {
    render(<MonitorsPage />);

    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    const newsCategoryTrigger = await screen.findByRole("button", { name: "分类: news" });
    expect(newsCategoryTrigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "分类: research" })).toBeInTheDocument();
    expect(screen.getByText("DeepMind News")).toBeInTheDocument();

    fireEvent.click(newsCategoryTrigger);
    expect(newsCategoryTrigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("DeepMind News")).not.toBeInTheDocument();

    fireEvent.click(newsCategoryTrigger);
    expect(newsCategoryTrigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("DeepMind News")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "取消" }));

    fireEvent.click(screen.getByText("Daily AI Brief"));
    expect(await screen.findByRole("heading", { name: "编辑任务" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "分类: news" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "分类: research" })).toBeInTheDocument();
  });

  it("does not preselect any source when creating monitor", async () => {
    render(<MonitorsPage />);

    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));

    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "No Default Source Monitor" },
    });

    const createButton = screen.getByRole("button", { name: "创建" });
    expect(createButton).toBeDisabled();

    fireEvent.click(screen.getByLabelText("OpenAI Blog"));

    expect(createButton).not.toBeDisabled();
  });

  it("submits multiple destination instances when creating a monitor", async () => {
    mockedGetDestinations.mockResolvedValueOnce([
      {
        id: "dest-notion-1",
        name: "Notion Workspace",
        type: "notion",
        description: "Notion destination",
        config: {},
        enabled: true,
      },
      {
        id: "dest-obsidian-1",
        name: "Research Vault",
        type: "obsidian",
        description: "Obsidian destination",
        config: {},
        enabled: true,
      },
    ]);

    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "Multi destination monitor" },
    });
    fireEvent.click(screen.getByLabelText("OpenAI Blog"));
    fireEvent.click(screen.getByRole("checkbox", { name: /Notion Workspace/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Research Vault/ }));

    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => {
      expect(mockedCreateMonitor).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Multi destination monitor",
          destination_instance_ids: ["dest-notion-1", "dest-obsidian-1"],
        })
      );
    });
  }, 30000);

  it("sends source max_items override when creating monitor", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "HF Monitor" },
    });

    fireEvent.click(screen.getByLabelText("Hugging Face Daily Papers"));
    fireEvent.change(screen.getByLabelText("Fetch limit for Hugging Face Daily Papers"), {
      target: { value: "12" },
    });

    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => {
      expect(mockedCreateMonitor).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "HF Monitor",
          report_type: "daily",
          source_overrides: { "source-4": { max_items: 12 } },
        })
      );
    });
  });

  it("sends monitor ai_routing when advanced routing is configured", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "Routing Monitor" },
    });
    fireEvent.click(screen.getByLabelText("OpenAI Blog"));
    await expandAiRoutingSection();

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
              llm_codex: { model: "gpt-5-codex" },
              llm_openai: { model: "gpt-4o-mini" },
            },
          },
        })
      );
    });
  });

  it("shows inherit option with current default provider", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    await expandAiRoutingSection();

    const llmInheritOptions = screen.getAllByRole("option", {
      name: "inherit (current: llm_openai)",
    });
    expect(llmInheritOptions.length).toBeGreaterThan(0);
  });

  it("sends ai_routing null on edit when advanced routing is cleared", async () => {
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
            filter: { primary: "llm_openai" },
          },
        },
        enabled: true,
        status: "active",
        last_run: null,
        created_at: "2026-03-02T10:00:00Z",
        updated_at: "2026-03-02T10:00:00Z",
      },
    ]);

    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Daily AI Brief"));
    expect(await screen.findByRole("heading", { name: "编辑任务" })).toBeInTheDocument();
    await expandAiRoutingSection();

    fireEvent.change(screen.getByLabelText("Filter stage provider"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(mockedUpdateMonitor).toHaveBeenCalledWith(
        "monitor-1",
        expect.objectContaining({
          ai_routing: null,
        })
      );
    });
  });

  it("exposes only supported provider options", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    await expandAiRoutingSection();

    const optionTexts = screen.getAllByRole("option").map((option) => option.textContent?.trim() ?? "");
    expect(optionTexts).toContain("llm_codex");
    expect(optionTexts).toContain("llm_openai");
    expect(optionTexts).toContain("rule");
    expect(optionTexts).not.toContain("legacy_agent");
  });

  it("sends arxiv keywords and max_results override when creating monitor", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "Arxiv Monitor" },
    });

    fireEvent.click(screen.getByLabelText("arXiv"));
    fireEvent.change(screen.getByLabelText("Keywords for arXiv"), {
      target: { value: "reasoning, agent" },
    });
    fireEvent.change(screen.getByLabelText("Max results for arXiv"), {
      target: { value: "40" },
    });

    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => {
      expect(mockedCreateMonitor).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Arxiv Monitor",
          report_type: "daily",
          source_overrides: {
            "source-5": { keywords: ["reasoning", "agent"], max_results: 40 },
          },
        })
      );
    });
  });

  it("sends academic api keywords and max_results override when creating monitor", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "OpenAlex Monitor" },
    });

    fireEvent.click(screen.getByLabelText("OpenAlex"));
    fireEvent.change(screen.getByLabelText("Keywords for OpenAlex"), {
      target: { value: "reasoning, agent" },
    });
    fireEvent.change(screen.getByLabelText("Max results for OpenAlex"), {
      target: { value: "40" },
    });

    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => {
      expect(mockedCreateMonitor).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "OpenAlex Monitor",
          report_type: "daily",
          source_overrides: {
            "source-6": { keywords: ["reasoning", "agent"], max_results: 40 },
          },
        })
      );
    });
  });

  it("sends selected reddit subreddits override when creating monitor", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "Reddit Monitor" },
    });

    fireEvent.click(screen.getByLabelText("Reddit"));
    expect(screen.getByText("版块列表")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("OpenAI"));

    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => {
      expect(mockedCreateMonitor).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Reddit Monitor",
          source_overrides: {
            "source-7": { subreddits: ["LocalLLaMA", "MachineLearning"] },
          },
        })
      );
    });
  });

  it("shows human-friendly time window presets in the create form", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));

    const timeWindowSelect = screen.getByLabelText("时间窗口") as HTMLSelectElement;
    expect(timeWindowSelect).toHaveValue("24");
    expect(Array.from(timeWindowSelect.options).map((option) => option.text)).toEqual(["1 天", "3 天", "7 天", "自定义"]);
    expect(screen.queryByLabelText("时间窗口（小时）")).not.toBeInTheDocument();
  });

  it("submits preset and custom time windows as window_hours", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "Preset Window Monitor" },
    });
    fireEvent.click(screen.getByLabelText("OpenAI Blog"));
    fireEvent.change(screen.getByLabelText("时间窗口"), {
      target: { value: "72" },
    });

    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => {
      expect(mockedCreateMonitor).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Preset Window Monitor",
          window_hours: 72,
        })
      );
    });

    mockedCreateMonitor.mockClear();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "Custom Window Monitor" },
    });
    fireEvent.click(screen.getByLabelText("OpenAI Blog"));
    fireEvent.change(screen.getByLabelText("时间窗口"), {
      target: { value: "custom" },
    });
    fireEvent.change(screen.getByLabelText("自定义时间窗口数值"), {
      target: { value: "2" },
    });
    fireEvent.change(screen.getByLabelText("自定义时间窗口单位"), {
      target: { value: "days" },
    });

    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => {
      expect(mockedCreateMonitor).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Custom Window Monitor",
          window_hours: 48,
        })
      );
    });
  });

  it("allows overriding the recommended report template for a daily monitor", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "Flexible Template Monitor" },
    });
    fireEvent.click(screen.getByLabelText("OpenAI Blog"));

    const reportTypeSelect = screen.getByLabelText("报告模板");
    expect(reportTypeSelect).not.toBeDisabled();
    fireEvent.change(reportTypeSelect, {
      target: { value: "research" },
    });

    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => {
      expect(mockedCreateMonitor).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Flexible Template Monitor",
          time_period: "daily",
          report_type: "research",
        })
      );
    });
  });

  it("keeps the recommended template in sync until the user overrides it", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));

    const reportTypeSelect = screen.getByLabelText("报告模板") as HTMLSelectElement;
    expect(reportTypeSelect.value).toBe("daily");

    fireEvent.change(screen.getByLabelText("更新频率"), {
      target: { value: "weekly" },
    });
    expect(reportTypeSelect.value).toBe("weekly");

    fireEvent.change(reportTypeSelect, {
      target: { value: "research" },
    });
    fireEvent.change(screen.getByLabelText("更新频率"), {
      target: { value: "daily" },
    });
    expect(reportTypeSelect.value).toBe("research");
  });

  it("shows structured schedule controls instead of raw cron input", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    fireEvent.change(screen.getByLabelText("更新频率"), {
      target: { value: "weekly" },
    });

    expect(screen.getByLabelText("执行星期")).toBeInTheDocument();
    expect(screen.getByLabelText("执行时间")).toBeInTheDocument();
    expect(screen.queryByText("自定义时间表 (Cron)")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("更新频率"), {
      target: { value: "custom" },
    });
    expect(screen.getByLabelText("执行时间")).toBeInTheDocument();
    expect(screen.getByLabelText("更新间隔（天）")).toBeInTheDocument();
    expect(screen.queryByLabelText("周一")).not.toBeInTheDocument();
    expect(screen.queryByText("使用高级 Cron")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("高级 Cron 表达式")).not.toBeInTheDocument();
    expect(screen.queryByText("自定义时间表 (Cron)")).not.toBeInTheDocument();
  });

  it("submits structured weekly cron and custom interval schedules", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "Weekly Schedule Monitor" },
    });
    fireEvent.click(screen.getByLabelText("OpenAI Blog"));
    fireEvent.change(screen.getByLabelText("更新频率"), {
      target: { value: "weekly" },
    });
    fireEvent.change(screen.getByLabelText("执行星期"), {
      target: { value: "3" },
    });
    fireEvent.change(screen.getByLabelText("执行时间"), {
      target: { value: "08:15" },
    });

    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => {
      expect(mockedCreateMonitor).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Weekly Schedule Monitor",
          time_period: "weekly",
          custom_schedule: "15 8 * * 3",
        })
      );
    });

    mockedCreateMonitor.mockClear();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "Custom Schedule Monitor" },
    });
    fireEvent.click(screen.getByLabelText("OpenAI Blog"));
    fireEvent.change(screen.getByLabelText("更新频率"), {
      target: { value: "custom" },
    });
    fireEvent.change(screen.getByLabelText("更新间隔（天）"), {
      target: { value: "2" },
    });
    fireEvent.change(screen.getByLabelText("执行时间"), {
      target: { value: "10:30" },
    });

    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => {
      expect(mockedCreateMonitor).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Custom Schedule Monitor",
          time_period: "custom",
          custom_schedule: "interval:2@10:30",
        })
      );
    });
  });

  it("offers paper as a custom report template", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    fireEvent.change(screen.getByPlaceholderText("例如：每日 AI 简报"), {
      target: { value: "Paper Monitor" },
    });
    fireEvent.click(screen.getByLabelText("OpenAI Blog"));

    fireEvent.change(screen.getByLabelText("更新频率"), {
      target: { value: "custom" },
    });

    expect(screen.getByRole("option", { name: "论文" })).toBeInTheDocument();
  });

  it("does not show deprecated test action", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Test" })).not.toBeInTheDocument();
  });

  it("allows terminating a running run from logs history", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "日志" }));
    expect(await screen.findByRole("heading", { name: "Run History: Daily AI Brief" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Terminate Run" }));

    await waitFor(() => {
      expect(mockedCancelMonitorRun).toHaveBeenCalledWith("monitor-1", "run-1");
    });
  });

  it("shows pending state when manual run is starting", async () => {
    let resolveRun: ((value: { task_id: string; run_id: string; status: "running"; monitor_id: string }) => void) | null = null;
    mockedRunMonitor.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRun = resolve;
        })
    );

    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    const runButton = screen.getByRole("button", { name: "运行" });
    fireEvent.click(runButton);

    expect(mockedRunMonitor).toHaveBeenCalledWith("monitor-1");
    expect(runButton).toBeDisabled();

    resolveRun?.({
      task_id: "task-1",
      run_id: "run-1",
      status: "running",
      monitor_id: "monitor-1",
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "运行" })).toBeEnabled();
    });
  });

  it("shows visible success hint after manual run starts", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "运行" }));

    expect(await screen.findByText(/Run started\./)).toBeInTheDocument();
    expect(screen.getByText(/run-1/)).toBeInTheDocument();
  });

  it("shows run feedback without auto-opening logs and keeps actions usable during refresh", async () => {
    let resolveRefresh: ((value: Parameters<typeof mockedGetMonitors.mockResolvedValue>[0]) => void) | null = null;
    mockedGetMonitors
      .mockResolvedValueOnce([
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
          enabled: true,
          status: "active",
          last_run: null,
          created_at: "2026-03-02T10:00:00Z",
          updated_at: "2026-03-02T10:00:00Z",
        },
      ])
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveRefresh = resolve;
          })
      );

    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "运行" }));

    expect(await screen.findByText(/Run started\./)).toBeInTheDocument();
    expect(screen.getByText(/Open Logs to follow progress\./)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "运行" })).toBeEnabled();
    });
    expect(screen.queryByRole("heading", { name: /Run History:/ })).not.toBeInTheDocument();
    expect(mockedGetMonitorLogs).not.toHaveBeenCalled();

    await act(async () => {
      resolveRefresh?.([
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
          enabled: true,
          status: "active",
          last_run: null,
          created_at: "2026-03-02T10:00:00Z",
          updated_at: "2026-03-02T10:00:00Z",
        },
      ]);
    });
  });

  it("uses a wider logs modal layout", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "日志" }));

    const modal = await screen.findByTestId("monitor-logs-modal");
    expect(modal).toHaveClass("w-[96vw]");
    expect(modal).toHaveClass("max-w-[1800px]");
    expect(modal).toHaveClass("h-[90vh]");
  });

  it("shows visible error when opening logs fails", async () => {
    mockedGetMonitorLogs.mockRejectedValueOnce(new Error("Logs fetch failed"));

    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "日志" }));

    expect(await screen.findByText("Logs fetch failed")).toBeInTheDocument();
  });
});
