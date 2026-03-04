import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import MonitorsPage from "@/app/monitors/page";
import {
  cancelMonitorRun,
  createMonitor,
  deleteMonitor,
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
  getDestinations: vi.fn(),
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
const mockedGetMonitorLogs = vi.mocked(getMonitorLogs);
const mockedGetMonitorRuns = vi.mocked(getMonitorRuns);
const mockedGetMonitorRunEvents = vi.mocked(getMonitorRunEvents);
const mockedCancelMonitorRun = vi.mocked(cancelMonitorRun);
const mockedCreateMonitor = vi.mocked(createMonitor);
const mockedUpdateMonitor = vi.mocked(updateMonitor);
const mockedRunMonitor = vi.mocked(runMonitor);
const mockedDeleteMonitor = vi.mocked(deleteMonitor);

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
    ]);
    mockedGetDestinations.mockResolvedValue([
      {
        id: "notion",
        name: "Notion",
        type: "notion",
        description: "Notion destination",
        config: {},
        enabled: true,
      },
    ]);
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
        trigger_type: "test",
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

    expect(await screen.findByRole("heading", { name: "Edit Monitor" })).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("e.g. Daily AI Brief"), {
      target: { value: "Updated monitor" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(mockedUpdateMonitor).toHaveBeenCalledWith(
        "monitor-1",
        expect.objectContaining({
          name: "Updated monitor",
          time_period: "daily",
          report_type: "daily",
          source_ids: ["source-1"],
          destination_ids: ["notion"],
        })
      );
    });
  });

  it("groups sources by category in both create and edit modals", async () => {
    render(<MonitorsPage />);

    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Create Monitor" }));
    const newsCategoryTrigger = await screen.findByRole("button", { name: "Category: news" });
    expect(newsCategoryTrigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "Category: research" })).toBeInTheDocument();
    expect(screen.getByText("DeepMind News")).toBeInTheDocument();

    fireEvent.click(newsCategoryTrigger);
    expect(newsCategoryTrigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("DeepMind News")).not.toBeInTheDocument();

    fireEvent.click(newsCategoryTrigger);
    expect(newsCategoryTrigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("DeepMind News")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    fireEvent.click(screen.getByText("Daily AI Brief"));
    expect(await screen.findByRole("heading", { name: "Edit Monitor" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Category: news" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Category: research" })).toBeInTheDocument();
  });

  it("does not preselect any source when creating monitor", async () => {
    render(<MonitorsPage />);

    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Create Monitor" }));

    fireEvent.change(screen.getByPlaceholderText("e.g. Daily AI Brief"), {
      target: { value: "No Default Source Monitor" },
    });

    const createButton = screen.getByRole("button", { name: "Create" });
    expect(createButton).toBeDisabled();

    fireEvent.click(screen.getByLabelText("OpenAI Blog"));

    expect(createButton).not.toBeDisabled();
  });

  it("sends source max_items override when creating monitor", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Create Monitor" }));
    fireEvent.change(screen.getByPlaceholderText("e.g. Daily AI Brief"), {
      target: { value: "HF Monitor" },
    });

    fireEvent.click(screen.getByLabelText("Hugging Face Daily Papers"));
    fireEvent.change(screen.getByLabelText("Fetch limit for Hugging Face Daily Papers"), {
      target: { value: "12" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Create" }));

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

  it("sends arxiv keywords and max_results override when creating monitor", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Create Monitor" }));
    fireEvent.change(screen.getByPlaceholderText("e.g. Daily AI Brief"), {
      target: { value: "Arxiv Monitor" },
    });

    fireEvent.click(screen.getByLabelText("arXiv"));
    fireEvent.change(screen.getByLabelText("Keywords for arXiv"), {
      target: { value: "reasoning, agent" },
    });
    fireEvent.change(screen.getByLabelText("Max results for arXiv"), {
      target: { value: "40" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Create" }));

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

  it("requires report type when time period is custom", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Create Monitor" }));
    fireEvent.change(screen.getByPlaceholderText("e.g. Daily AI Brief"), {
      target: { value: "Custom Monitor" },
    });
    fireEvent.click(screen.getByLabelText("OpenAI Blog"));

    fireEvent.change(screen.getByLabelText("Frequency"), {
      target: { value: "custom" },
    });

    const createButton = screen.getByRole("button", { name: "Create" });
    expect(createButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Template"), {
      target: { value: "research" },
    });
    expect(createButton).not.toBeDisabled();
  });

  it("supports test run with temporary window override", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Test" }));
    expect(await screen.findByRole("heading", { name: "Test Run: Daily AI Brief" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Custom" }));
    fireEvent.change(screen.getByPlaceholderText("24"), {
      target: { value: "6" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start Test Run" }));

    await waitFor(() => {
      expect(mockedRunMonitor).toHaveBeenCalledWith("monitor-1", { window_hours: 6, trigger_type: "test" });
    });
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Test Console: Daily AI Brief" })).toBeInTheDocument();
    });
  });

  it("supports terminating a running live debug run", async () => {
    render(<MonitorsPage />);
    expect(await screen.findByText("Daily AI Brief")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Test" }));
    expect(await screen.findByRole("heading", { name: "Test Run: Daily AI Brief" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start Test Run" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Test Console: Daily AI Brief" })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: "Terminate" }));

    await waitFor(() => {
      expect(mockedCancelMonitorRun).toHaveBeenCalledWith("monitor-1", "run-1");
    });
  });
});
