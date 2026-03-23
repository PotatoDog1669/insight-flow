import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

import DiscoverPage from "@/app/page";
import { createMonitor, getDestinations, getReports, getSources, streamMonitorAgentMessage } from "@/lib/api";

const pushMock = vi.fn();

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
  } & React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("@/components/ReportCard", () => ({
  ReportCard: ({
    report,
    onDelete,
  }: {
    report: { title: string; monitor_name?: string; tldr?: string[] };
    onDelete?: () => void;
  }) => {
    return (
      <div>
        <span>{report.title}</span>
        {report.monitor_name ? <span>{report.monitor_name}</span> : null}
        {report.tldr && report.tldr.length > 0 ? <span>{report.tldr[0]}</span> : null}
        {onDelete ? (
          <button type="button" onClick={onDelete}>
            删除报告
          </button>
        ) : null}
      </div>
    );
  },
}));

vi.mock("@/lib/api", () => ({
  createMonitor: vi.fn(),
  getDestinations: vi.fn(),
  getReports: vi.fn(),
  getSources: vi.fn(),
  streamMonitorAgentMessage: vi.fn(),
}));

const mockedCreateMonitor = vi.mocked(createMonitor);
const mockedGetDestinations = vi.mocked(getDestinations);
const mockedGetReports = vi.mocked(getReports);
const mockedGetSources = vi.mocked(getSources);
const mockedStreamMonitorAgentMessage = vi.mocked(streamMonitorAgentMessage);

function createStreamMock(response: {
  mode: "clarify" | "draft";
  conversation_id: string;
  message?: string | null;
  missing_or_conflicting_fields?: string[];
  inferred_fields?: string[];
  draft?: unknown;
  monitor_payload?: unknown;
}) {
  return async (_body: unknown, handlers?: Record<string, (event: unknown) => void>) => {
    handlers?.onStatus?.({
      type: "status",
      key: "understand",
      label: "理解需求",
      status: "running",
    });
    handlers?.onStatus?.({
      type: "status",
      key: "sources",
      label: "匹配来源",
      status: "completed",
    });
    if (response.message) {
      handlers?.onMessageDelta?.({
        type: "message_delta",
        delta: response.message,
      });
    }
    handlers?.onFinal?.({
      type: "final",
      response,
    });
    return response;
  };
}

describe("DiscoverPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pushMock.mockReset();
    mockedCreateMonitor.mockResolvedValue({
      id: "monitor-1",
      name: "Agent Monitor",
      time_period: "daily",
      report_type: "daily",
      source_ids: ["source-1"],
      destination_ids: [],
      destination_instance_ids: [],
      window_hours: 24,
      custom_schedule: "0 9 * * *",
      enabled: true,
      status: "active",
      last_run: null,
      created_at: "2026-03-23T00:00:00Z",
      updated_at: "2026-03-23T00:00:00Z",
    } as never);
    mockedGetDestinations.mockResolvedValue([
      {
        id: "dest-notion-1",
        name: "Notion DB",
        type: "notion",
        description: "Daily sync target",
        config: {},
        enabled: true,
      },
    ] as never);
    mockedGetSources.mockResolvedValue([
      {
        id: "source-1",
        name: "Seed Source",
        category: "news",
        collect_method: "rss",
        config: {},
        enabled: true,
        status: "healthy",
        last_run: null,
        last_collected: null,
        created_at: "2026-03-23T00:00:00Z",
        updated_at: "2026-03-23T00:00:00Z",
      },
      {
        id: "source-2",
        name: "X Watch",
        category: "social",
        collect_method: "twitter_snaplytics",
        config: { usernames: ["OpenAI", "AnthropicAI", "LangChainAI"] },
        enabled: true,
        status: "healthy",
        last_run: null,
        last_collected: null,
        created_at: "2026-03-23T00:00:00Z",
        updated_at: "2026-03-23T00:00:00Z",
      },
      {
        id: "source-3",
        name: "Reddit",
        category: "social",
        collect_method: "rss",
        config: { subreddits: ["LocalLLaMA", "OpenAI", "singularity"] },
        enabled: true,
        status: "healthy",
        last_run: null,
        last_collected: null,
        created_at: "2026-03-23T00:00:00Z",
        updated_at: "2026-03-23T00:00:00Z",
      },
      {
        id: "source-4",
        name: "Research Feed",
        category: "academic",
        collect_method: "rss",
        config: { keywords: ["agent", "reasoning"], arxiv_api: true, max_results: 25 },
        enabled: true,
        status: "healthy",
        last_run: null,
        last_collected: null,
        created_at: "2026-03-23T00:00:00Z",
        updated_at: "2026-03-23T00:00:00Z",
      },
    ] as never);
    mockedGetReports.mockResolvedValue([] as never);
    mockedStreamMonitorAgentMessage.mockImplementation(
      createStreamMock({
        mode: "clarify",
        conversation_id: "conv-1",
        message: "请再具体一点",
        missing_or_conflicting_fields: ["topic_scope"],
      } as never)
    );
  });

  it("loads reports without forcing report_type filter", async () => {
    render(<DiscoverPage />);

    await waitFor(() => {
      expect(mockedGetReports).toHaveBeenCalledWith({ limit: 10, page: 1 });
    });

    expect(screen.getByText("今日暂无新报告。")).toBeInTheDocument();
  });

  it("renders a minimal landing hero without the previous headline copy or start button", async () => {
    render(<DiscoverPage />);

    await waitFor(() => {
      expect(mockedGetReports).toHaveBeenCalledWith({ limit: 10, page: 1 });
    });

    expect(screen.queryByText("Insight Flow")).not.toBeInTheDocument();
    expect(screen.queryByText("需要我为你持续关注什么？")).not.toBeInTheDocument();
    expect(screen.queryByText("Insight Flow Monitor Agent")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start inquiry" })).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("Scout for what matters next")).toBeInTheDocument();
  });

  it("shows timeout error when reports request hangs", async () => {
    vi.useFakeTimers();
    try {
      mockedGetReports.mockImplementation(() => new Promise(() => {}) as never);
      render(<DiscoverPage />);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(15000);
      });

      expect(screen.getByText("加载报告失败：Request timeout after 15s")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("passes monitor name through to report cards", async () => {
    mockedGetReports.mockResolvedValue([
      {
        id: "report-1",
        user_id: null,
        time_period: "daily",
        report_type: "daily",
        title: "Agent Brief",
        report_date: "2026-03-02",
        tldr: [],
        article_count: 1,
        topics: [],
        events: [],
        global_tldr: "",
        content: "",
        article_ids: [],
        published_to: [],
        metadata: {},
        monitor_id: "monitor-1",
        monitor_name: "Agent Watch",
        created_at: "2026-03-02T00:00:00Z",
      },
    ] as never);

    render(<DiscoverPage />);

    await waitFor(() => {
      expect(screen.getByText("Agent Watch")).toBeInTheDocument();
    });
  });

  it("shows only the latest three reports in the landing feed", async () => {
    mockedGetReports.mockResolvedValue(
      Array.from({ length: 4 }, (_, index) => ({
        id: `report-${index + 1}`,
        user_id: null,
        time_period: "daily",
        report_type: "daily",
        title: `Agent Brief ${index + 1}`,
        report_date: `2026-03-0${index + 1}`,
        tldr: [],
        article_count: 1,
        topics: [],
        events: [],
        global_tldr: "",
        content: "",
        article_ids: [],
        published_to: [],
        metadata: {},
        monitor_id: `monitor-${index + 1}`,
        monitor_name: `Agent Watch ${index + 1}`,
        created_at: "2026-03-02T00:00:00Z",
      })) as never
    );

    render(<DiscoverPage />);

    await waitFor(() => {
      expect(screen.getByText("Agent Watch 1")).toBeInTheDocument();
    });

    expect(screen.getByText("Agent Watch 2")).toBeInTheDocument();
    expect(screen.getByText("Agent Watch 3")).toBeInTheDocument();
    expect(screen.queryByText("Agent Watch 4")).not.toBeInTheDocument();
  });

  it("renders paper reports in the discover feed", async () => {
    mockedGetReports.mockResolvedValue([
      {
        id: "report-paper",
        user_id: null,
        time_period: "daily",
        report_type: "paper",
        title: "Paper Brief",
        report_date: "2026-03-02",
        tldr: ["本期重点不只是新论文数量，而是后训练强化学习与 GUI 奖励建模两条线开始进入更可复用的工程阶段。"],
        article_count: 1,
        topics: [],
        events: [],
        global_tldr: "",
        content: "",
        article_ids: [],
        published_to: [],
        metadata: {},
        monitor_id: "monitor-1",
        monitor_name: "Paper Watch",
        created_at: "2026-03-02T00:00:00Z",
      },
    ] as never);

    render(<DiscoverPage />);

    await waitFor(() => {
      expect(screen.getByText("2026-03-02 论文推荐")).toBeInTheDocument();
      expect(
        screen.getByText("本期重点不只是新论文数量，而是后训练强化学习与 GUI 奖励建模两条线开始进入更可复用的工程阶段。")
      ).toBeInTheDocument();
    });
  });

  it("does not render paper note reports in the discover feed", async () => {
    mockedGetReports.mockResolvedValue([
      {
        id: "report-paper-digest",
        user_id: null,
        time_period: "daily",
        report_type: "paper",
        title: "Paper Digest",
        report_date: "2026-03-02",
        tldr: [],
        article_count: 1,
        topics: [],
        events: [],
        global_tldr: "",
        content: "",
        article_ids: [],
        published_to: [],
        metadata: { paper_mode: "digest" },
        monitor_id: "monitor-1",
        monitor_name: "Paper Watch",
        created_at: "2026-03-02T00:00:00Z",
      },
      {
        id: "report-paper-note",
        user_id: null,
        time_period: "daily",
        report_type: "paper",
        title: "Paper Note Report",
        report_date: "2026-03-02",
        tldr: [],
        article_count: 1,
        topics: [],
        events: [],
        global_tldr: "",
        content: "",
        article_ids: [],
        published_to: [],
        metadata: { paper_mode: "note" },
        monitor_id: "monitor-1",
        monitor_name: "Paper Watch",
        created_at: "2026-03-02T00:00:00Z",
      },
    ] as never);

    render(<DiscoverPage />);

    await waitFor(() => {
      expect(screen.getByText("2026-03-02 论文推荐")).toBeInTheDocument();
      expect(screen.queryByText("Paper Note Report")).not.toBeInTheDocument();
    });
  });

  it("does not render delete actions on discover cards", async () => {
    mockedGetReports.mockResolvedValue([
      {
        id: "report-1",
        user_id: null,
        time_period: "daily",
        report_type: "daily",
        title: "Agent Brief",
        report_date: "2026-03-02",
        tldr: [],
        article_count: 1,
        topics: [],
        events: [],
        global_tldr: "",
        content: "",
        article_ids: [],
        published_to: [],
        metadata: {},
        monitor_id: "monitor-1",
        monitor_name: "Agent Watch",
        created_at: "2026-03-02T00:00:00Z",
      },
    ] as never);

    render(<DiscoverPage />);

    await waitFor(() => {
      expect(screen.getByText("AI 早报 2026-03-02")).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: "删除报告" })).not.toBeInTheDocument();
  });

  it("starts an inline inquiry thread and renders the clarify response as a chat turn", async () => {
    render(<DiscoverPage />);

    fireEvent.change(screen.getByPlaceholderText("Scout for what matters next"), {
      target: { value: "track ai agents" },
    });
    fireEvent.keyDown(screen.getByPlaceholderText("Scout for what matters next"), {
      key: "Enter",
      code: "Enter",
      shiftKey: false,
    });

    await waitFor(() => {
      expect(mockedStreamMonitorAgentMessage).toHaveBeenCalledWith({
        message: "track ai agents",
      }, expect.any(Object));
    });

    expect(screen.queryByRole("dialog", { name: "Agent Inquiry" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Agent conversation" })).toBeInTheDocument();
    expect(screen.queryByText("理解需求")).not.toBeInTheDocument();
    const userBubble = screen.getByText("track ai agents");
    expect(userBubble).toBeInTheDocument();
    expect(userBubble).toHaveClass("bg-white/95");
    expect(screen.getByText("请再具体一点")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Continue refining this monitor…")).toBeInTheDocument();
  });

  it("keeps shift enter for multi-line draft input instead of sending immediately", async () => {
    render(<DiscoverPage />);

    const input = screen.getByPlaceholderText("Scout for what matters next");
    fireEvent.change(input, {
      target: { value: "track ai agents" },
    });
    fireEvent.keyDown(input, {
      key: "Enter",
      code: "Enter",
      shiftKey: true,
    });

    await waitFor(() => {
      expect(mockedGetReports).toHaveBeenCalled();
    });

    expect(mockedStreamMonitorAgentMessage).not.toHaveBeenCalled();
  });

  it("renders a draft card inside the inline thread when the monitor agent returns draft mode", async () => {
    mockedStreamMonitorAgentMessage.mockImplementationOnce(createStreamMock({
      mode: "draft",
      conversation_id: "conv-1",
      message: "我先按当前理解给你一版可编辑的 monitor 草案。",
      inferred_fields: ["ai_provider", "schedule"],
      draft: {
        name: "Agent Monitor",
        summary: "围绕 agent 主题生成的草案",
        editable: true,
        sections: [
          {
            kind: "source_list",
            title: "推荐来源",
            items: [
              {
                key: "source:source-1",
                type: "source",
                label: "Seed Source",
                status: "ready",
                source_id: "source-1",
              },
            ],
          },
          {
            kind: "schedule",
            title: "调度建议",
            items: [
              {
                key: "schedule:daily",
                type: "schedule",
                label: "每天 09:00",
                status: "ready",
                time_period: "daily",
                custom_schedule: "0 9 * * *",
              },
            ],
          },
        ],
      },
      monitor_payload: {
        name: "Agent Monitor",
        time_period: "daily",
        report_type: "daily",
        source_ids: ["source-1"],
        ai_provider: "llm_openai",
        source_overrides: {},
        destination_instance_ids: [],
        window_hours: 24,
        custom_schedule: "0 9 * * *",
        enabled: true,
      },
    } as never));

    render(<DiscoverPage />);

    fireEvent.change(screen.getByPlaceholderText("Scout for what matters next"), {
      target: { value: "关注 agent 前沿内容" },
    });
    fireEvent.keyDown(screen.getByPlaceholderText("Scout for what matters next"), {
      key: "Enter",
      code: "Enter",
    });

    await waitFor(() => {
      expect(screen.getByRole("region", { name: "Agent conversation" })).toBeInTheDocument();
    });

    expect(screen.getByTestId("monitor-draft-card")).toHaveClass("max-w-[46rem]");
    expect(screen.getByText("监控草案")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Agent Monitor")).toBeInTheDocument();
    expect(screen.getByText("信息源")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "分类: news" })).toBeInTheDocument();
    expect(screen.getByLabelText("报告类型")).toHaveValue("daily");
    expect(screen.getByTestId("draft-type-frequency-row")).toHaveClass("md:grid-cols-2");
    expect(screen.queryByLabelText("时间窗口")).not.toBeInTheDocument();
    expect(screen.queryByText("Runs daily at 09:00 by default.")).not.toBeInTheDocument();
    expect(screen.getByText("输出位置")).toBeInTheDocument();
    expect(screen.getByLabelText("Notion DB")).not.toBeChecked();
    expect(screen.getByLabelText("Seed Source")).toBeChecked();
    expect(screen.getByRole("button", { name: "保存任务" })).toBeInTheDocument();
  });

  it("allows editing X usernames and Reddit subreddits in the draft card before saving", async () => {
    mockedStreamMonitorAgentMessage.mockImplementationOnce(createStreamMock({
      mode: "draft",
      conversation_id: "conv-1",
      message: "我先按当前理解给你一版可编辑的 monitor 草案。",
      inferred_fields: ["ai_provider", "schedule"],
      draft: {
        name: "Agent Social Monitor",
        summary: "围绕 agent 社交源生成的草案",
        editable: true,
        sections: [
          {
            kind: "source_list",
            title: "推荐来源",
            items: [
              {
                key: "source:source-2",
                type: "source",
                label: "X Watch",
                status: "ready",
                source_id: "source-2",
              },
              {
                key: "source:source-3",
                type: "source",
                label: "Reddit",
                status: "ready",
                source_id: "source-3",
              },
            ],
          },
        ],
      },
      monitor_payload: {
        name: "Agent Social Monitor",
        time_period: "daily",
        report_type: "daily",
        source_ids: ["source-2", "source-3"],
        ai_provider: "llm_openai",
        source_overrides: {
          "source-2": { usernames: ["OpenAI", "AnthropicAI"] },
          "source-3": { subreddits: ["LocalLLaMA", "OpenAI"] },
        },
        destination_instance_ids: [],
        window_hours: 24,
        custom_schedule: "0 9 * * *",
        enabled: true,
      },
    } as never));

    render(<DiscoverPage />);

    fireEvent.change(screen.getByPlaceholderText("Scout for what matters next"), {
      target: { value: "关注 agent 前沿内容" },
    });
    fireEvent.keyDown(screen.getByPlaceholderText("Scout for what matters next"), {
      key: "Enter",
      code: "Enter",
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue("Agent Social Monitor")).toBeInTheDocument();
    });

    expect(screen.getByText("账号列表")).toBeInTheDocument();
    expect(screen.getByText("版块列表")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("X 账号 AnthropicAI"));
    fireEvent.click(screen.getByLabelText("Reddit 版块 OpenAI"));
    fireEvent.click(screen.getByRole("button", { name: "保存任务" }));

    await waitFor(() => {
      expect(mockedCreateMonitor).toHaveBeenCalledWith(
        expect.objectContaining({
          source_ids: ["source-2", "source-3"],
          source_overrides: {
            "source-2": { usernames: ["OpenAI"] },
            "source-3": { subreddits: ["LocalLLaMA"] },
          },
        })
      );
    });
  });

  it("allows editing academic keywords and max results in the draft card before saving", async () => {
    mockedStreamMonitorAgentMessage.mockImplementationOnce(createStreamMock({
      mode: "draft",
      conversation_id: "conv-1",
      message: "我先按当前理解给你一版可编辑的 monitor 草案。",
      inferred_fields: ["sources", "keywords", "schedule"],
      draft: {
        name: "Academic Agent Monitor",
        summary: "围绕 agent 学术进展生成的草案",
        editable: true,
        sections: [
          {
            kind: "source_list",
            title: "推荐来源",
            items: [
              {
                key: "source:source-4",
                type: "source",
                label: "Research Feed",
                status: "ready",
                source_id: "source-4",
              },
            ],
          },
        ],
      },
      monitor_payload: {
        name: "Academic Agent Monitor",
        time_period: "daily",
        report_type: "daily",
        source_ids: ["source-4"],
        ai_provider: "llm_openai",
        source_overrides: {
          "source-4": {
            keywords: ["multimodal agents", "reasoning"],
            max_results: 40,
          },
        },
        destination_instance_ids: [],
        window_hours: 24,
        custom_schedule: "0 9 * * *",
        enabled: true,
      },
    } as never));

    render(<DiscoverPage />);

    fireEvent.change(screen.getByPlaceholderText("Scout for what matters next"), {
      target: { value: "追踪多模态 agent 论文进展" },
    });
    fireEvent.keyDown(screen.getByPlaceholderText("Scout for what matters next"), {
      key: "Enter",
      code: "Enter",
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue("Academic Agent Monitor")).toBeInTheDocument();
    });

    expect(screen.getByLabelText("学术关键词 Research Feed")).toHaveValue("multimodal agents, reasoning");
    expect(screen.getByLabelText("最大结果数 Research Feed")).toHaveValue(40);

    fireEvent.change(screen.getByLabelText("学术关键词 Research Feed"), {
      target: { value: "multimodal agents, gui agents" },
    });
    fireEvent.change(screen.getByLabelText("最大结果数 Research Feed"), {
      target: { value: "30" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存任务" }));

    await waitFor(() => {
      expect(mockedCreateMonitor).toHaveBeenCalledWith(
        expect.objectContaining({
          source_ids: ["source-4"],
          source_overrides: {
            "source-4": {
              keywords: ["multimodal agents", "gui agents"],
              max_results: 30,
            },
          },
        })
      );
    });
  });

  it("saves the edited monitor draft from the inline thread and redirects to monitors", async () => {
    mockedStreamMonitorAgentMessage.mockImplementationOnce(createStreamMock({
      mode: "draft",
      conversation_id: "conv-1",
      message: "我先按当前理解给你一版可编辑的 monitor 草案。",
      inferred_fields: ["ai_provider", "schedule"],
      draft: {
        name: "Agent Monitor",
        summary: "围绕 agent 主题生成的草案",
        editable: true,
        sections: [
          {
            kind: "source_list",
            title: "推荐来源",
            items: [
              {
                key: "source:source-1",
                type: "source",
                label: "Seed Source",
                status: "ready",
                source_id: "source-1",
              },
            ],
          },
        ],
      },
      monitor_payload: {
        name: "Agent Monitor",
        time_period: "daily",
        report_type: "daily",
        source_ids: ["source-1"],
        ai_provider: "llm_openai",
        source_overrides: {},
        destination_instance_ids: [],
        window_hours: 24,
        custom_schedule: "0 9 * * *",
        enabled: true,
      },
    } as never));

    render(<DiscoverPage />);

    fireEvent.change(screen.getByPlaceholderText("Scout for what matters next"), {
      target: { value: "关注 agent 前沿内容" },
    });
    fireEvent.keyDown(screen.getByPlaceholderText("Scout for what matters next"), {
      key: "Enter",
      code: "Enter",
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue("Agent Monitor")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("监控名称"), {
      target: { value: "Agent Frontier Monitor" },
    });
    fireEvent.change(screen.getByLabelText("报告类型"), {
      target: { value: "research" },
    });
    fireEvent.click(screen.getByLabelText("Notion DB"));
    fireEvent.click(screen.getByRole("button", { name: "保存任务" }));

    await waitFor(() => {
      expect(mockedCreateMonitor).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Agent Frontier Monitor",
          report_type: "research",
          window_hours: 24,
          source_ids: ["source-1"],
          destination_instance_ids: ["dest-notion-1"],
          ai_provider: "llm_openai",
        })
      );
    });

    expect(pushMock).toHaveBeenCalledWith("/monitors");
  });

  it("derives a 7 day time window when saving a weekly draft", async () => {
    mockedStreamMonitorAgentMessage.mockImplementationOnce(createStreamMock({
      mode: "draft",
      conversation_id: "conv-1",
      message: "我先按当前理解给你一版可编辑的 monitor 草案。",
      inferred_fields: ["ai_provider", "schedule"],
      draft: {
        name: "Weekly Agent Monitor",
        summary: "围绕 agent 主题生成的周报草案",
        editable: true,
        sections: [],
      },
      monitor_payload: {
        name: "Weekly Agent Monitor",
        time_period: "weekly",
        report_type: "weekly",
        source_ids: ["source-1"],
        ai_provider: "llm_openai",
        source_overrides: {},
        destination_instance_ids: [],
        window_hours: 24,
        custom_schedule: "0 9 * * 1",
        enabled: true,
      },
    } as never));

    render(<DiscoverPage />);

    fireEvent.change(screen.getByPlaceholderText("Scout for what matters next"), {
      target: { value: "每周关注 agent 前沿内容" },
    });
    fireEvent.keyDown(screen.getByPlaceholderText("Scout for what matters next"), {
      key: "Enter",
      code: "Enter",
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue("Weekly Agent Monitor")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "保存任务" }));

    await waitFor(() => {
      expect(mockedCreateMonitor).toHaveBeenCalledWith(
        expect.objectContaining({
          report_type: "weekly",
          window_hours: 168,
        })
      );
    });
  });

  it("sends follow-up replies on enter in the inline composer", async () => {
    mockedStreamMonitorAgentMessage
      .mockImplementationOnce(createStreamMock({
        mode: "clarify",
        conversation_id: "conv-1",
        message: "请再具体一点",
        missing_or_conflicting_fields: ["topic_scope"],
      } as never))
      .mockImplementationOnce(createStreamMock({
        mode: "clarify",
        conversation_id: "conv-1",
        message: "好的，我会更聚焦 agent 框架和产品动态。",
        missing_or_conflicting_fields: [],
      } as never));

    render(<DiscoverPage />);

    const landingInput = screen.getByPlaceholderText("Scout for what matters next");
    fireEvent.change(landingInput, {
      target: { value: "关注 agent" },
    });
    fireEvent.keyDown(landingInput, {
      key: "Enter",
      code: "Enter",
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Continue refining this monitor…")).toBeInTheDocument();
    });

    const replyInput = screen.getByPlaceholderText("Continue refining this monitor…");
    fireEvent.change(replyInput, {
      target: { value: "重点是框架和产品更新" },
    });
    fireEvent.keyDown(replyInput, {
      key: "Enter",
      code: "Enter",
    });

    await waitFor(() => {
      expect(mockedStreamMonitorAgentMessage).toHaveBeenLastCalledWith({
        message: "重点是框架和产品更新",
        conversation_id: "conv-1",
      }, expect.any(Object));
    });
  });

  it("uses a fixed bottom composer without a send button in conversation mode", async () => {
    render(<DiscoverPage />);

    const landingInput = screen.getByPlaceholderText("Scout for what matters next");
    fireEvent.change(landingInput, {
      target: { value: "关注 agent" },
    });
    fireEvent.keyDown(landingInput, {
      key: "Enter",
      code: "Enter",
    });

    const replyInput = await screen.findByPlaceholderText("Continue refining this monitor…");

    expect(screen.queryByRole("button", { name: "Send reply" })).not.toBeInTheDocument();
    expect(replyInput.closest(".fixed")).not.toBeNull();
  });

  it("does not render the old monitor inquiry heading in conversation mode", async () => {
    render(<DiscoverPage />);

    const landingInput = screen.getByPlaceholderText("Scout for what matters next");
    fireEvent.change(landingInput, {
      target: { value: "关注 agent" },
    });
    fireEvent.keyDown(landingInput, {
      key: "Enter",
      code: "Enter",
    });

    await screen.findByPlaceholderText("Continue refining this monitor…");

    expect(screen.queryByText("Monitor inquiry")).not.toBeInTheDocument();
  });

  it("shows a loader instead of progress labels while the agent is still streaming", async () => {
    let resolveStream: ((value: {
      mode: "clarify";
      conversation_id: string;
      message: string;
      missing_or_conflicting_fields: string[];
    }) => void) | null = null;

    mockedStreamMonitorAgentMessage.mockImplementationOnce(
      (_body, handlers) =>
        new Promise((resolve) => {
          handlers?.onStatus?.({
            type: "status",
            key: "understand",
            label: "理解需求",
            status: "running",
          });
          resolveStream = resolve;
        }) as never
    );

    render(<DiscoverPage />);

    const landingInput = screen.getByPlaceholderText("Scout for what matters next");
    fireEvent.change(landingInput, {
      target: { value: "关注 agent" },
    });
    fireEvent.keyDown(landingInput, {
      key: "Enter",
      code: "Enter",
    });

    await waitFor(() => {
      expect(screen.getByTestId("agent-loader")).toBeInTheDocument();
    });
    expect(screen.queryByText("理解需求")).not.toBeInTheDocument();
    expect(screen.queryByText("正在生成 monitor 草案…")).not.toBeInTheDocument();

    resolveStream?.({
      mode: "clarify",
      conversation_id: "conv-1",
      message: "请再具体一点",
      missing_or_conflicting_fields: ["topic_scope"],
    });

    await waitFor(() => {
      expect(screen.queryByTestId("agent-loader")).not.toBeInTheDocument();
    });
  });

  it("shows a draft card loader after streamed text arrives but before the draft card is ready", async () => {
    let resolveStream: ((value: {
      mode: "draft";
      conversation_id: string;
      message: string;
      inferred_fields: string[];
      draft: {
        name: string;
        summary: string;
        editable: true;
        sections: [];
      };
      monitor_payload: {
        name: string;
        time_period: "daily";
        report_type: "daily";
        source_ids: string[];
        ai_provider: "llm_openai";
        source_overrides: Record<string, never>;
        destination_instance_ids: string[];
        window_hours: number;
        custom_schedule: string;
        enabled: true;
      };
    }) => void) | null = null;

    mockedStreamMonitorAgentMessage.mockImplementationOnce(
      (_body, handlers) =>
        new Promise((resolve) => {
          handlers?.onStatus?.({
            type: "status",
            key: "draft",
            label: "生成草案",
            status: "running",
          });
          handlers?.onMessageDelta?.({
            type: "message_delta",
            delta: "我先按当前理解给你一版可编辑的 monitor 草案。",
          });
          resolveStream = resolve;
        }) as never
    );

    render(<DiscoverPage />);

    const landingInput = screen.getByPlaceholderText("Scout for what matters next");
    fireEvent.change(landingInput, {
      target: { value: "关注 agent 前沿内容" },
    });
    fireEvent.keyDown(landingInput, {
      key: "Enter",
      code: "Enter",
    });

    await waitFor(() => {
      expect(screen.getByText("我先按当前理解给你一版可编辑的 monitor 草案。")).toBeInTheDocument();
      expect(screen.getByTestId("draft-card-loader")).toBeInTheDocument();
    });

    resolveStream?.({
      mode: "draft",
      conversation_id: "conv-1",
      message: "我先按当前理解给你一版可编辑的 monitor 草案。",
      inferred_fields: ["ai_provider", "schedule"],
      draft: {
        name: "Agent Monitor",
        summary: "围绕 agent 主题生成的草案",
        editable: true,
        sections: [],
      },
      monitor_payload: {
        name: "Agent Monitor",
        time_period: "daily",
        report_type: "daily",
        source_ids: ["source-1"],
        ai_provider: "llm_openai",
        source_overrides: {},
        destination_instance_ids: [],
        window_hours: 24,
        custom_schedule: "0 9 * * *",
        enabled: true,
      },
    });

    await waitFor(() => {
      expect(screen.queryByTestId("draft-card-loader")).not.toBeInTheDocument();
      expect(screen.getByTestId("monitor-draft-card")).toBeInTheDocument();
    });
  });
});
