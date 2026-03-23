import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { within } from "@testing-library/react";

import ReportDetailPage from "@/app/reports/[id]/page";
import { getArticleById, getDestinations, getReportById, publishReportToDestination } from "@/lib/api";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "report-1" }),
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/lib/api", () => ({
  getReportById: vi.fn(),
  getArticleById: vi.fn(),
  getDestinations: vi.fn(),
  publishReportToDestination: vi.fn(),
}));

const mockedGetReportById = vi.mocked(getReportById);
const mockedGetArticleById = vi.mocked(getArticleById);
const mockedGetDestinations = vi.mocked(getDestinations);
const mockedPublishReportToDestination = vi.mocked(publishReportToDestination);

describe("ReportDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pushMock.mockReset();
    mockedGetDestinations.mockResolvedValue([
      {
        id: "dest-notion-1",
        name: "Notion Workspace",
        type: "notion",
        description: "Sync to Notion",
        config: {},
        enabled: true,
      },
      {
        id: "dest-obsidian-1",
        name: "Obsidian Vault",
        type: "obsidian",
        description: "Sync to Obsidian",
        config: {},
        enabled: true,
      },
      {
        id: "dest-rss-1",
        name: "RSS Feed",
        type: "rss",
        description: "Sync to RSS",
        config: {},
        enabled: false,
      },
    ] as never);
  });

  it("renders document from report.content and outline", async () => {
    const events = Array.from({ length: 15 }).map((_, idx) => ({
      event_id: `event-${idx + 1}`,
      index: idx + 1,
      title: `Event ${idx + 1}`,
      category: "行业动态",
      one_line_tldr: `TLDR ${idx + 1}`,
      detail: `Detail ${idx + 1}`,
      keywords: [],
      entities: [],
      metrics: [],
      source_links: [],
      source_count: 1,
      source_name: "Source",
      published_at: null,
    }));

    mockedGetReportById.mockResolvedValue({
      id: "report-1",
      user_id: null,
      time_period: "daily",
      report_type: "research",
      title: "AI Daily",
      report_date: "2026-03-02",
      tldr: [],
      article_count: 0,
      topics: [],
      events,
      global_tldr: "",
      content: "# AI Daily\n\n## 全局总结与锐评\nA",
      article_ids: [],
      published_to: [],
      published_destination_instance_ids: [],
      publish_trace: [],
      metadata: {},
      monitor_id: "monitor-1",
      monitor_name: "Agent Watch",
      created_at: "2026-03-02T00:00:00Z",
    } as never);
    mockedGetArticleById.mockResolvedValue(null as never);

    render(<ReportDetailPage />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "概览" })).toBeInTheDocument());
    expect(screen.getByRole("navigation", { name: "Report outline" })).toBeInTheDocument();
    expect(screen.getByText("Agent Watch")).toBeInTheDocument();
    expect(mockedGetArticleById).not.toHaveBeenCalled();
  });

  it("renders the research summary in the cover area", async () => {
    mockedGetReportById.mockResolvedValue({
      id: "report-research",
      user_id: null,
      time_period: "custom",
      report_type: "research",
      title: "Anthropic MCP Research",
      report_date: "2026-03-02",
      tldr: ["MCP 正从工具协议变成平台分发层，接下来要看谁能占住生态入口。"],
      article_count: 0,
      topics: [],
      events: [
        {
          event_id: "event-1",
          index: 1,
          title: "Anthropic expands MCP ecosystem",
          category: "开发生态",
          one_line_tldr: "MCP 正在进入平台化竞争阶段。",
          detail: "Detailed research body",
          keywords: [],
          entities: [],
          metrics: [],
          source_links: ["https://example.com/mcp"],
          source_count: 2,
          source_name: "Anthropic",
          published_at: null,
        },
      ],
      global_tldr: "MCP 正从工具协议变成平台分发层，接下来要看谁能占住生态入口。",
      content: "# Anthropic MCP Research\n\n## 执行摘要\n研究正文",
      article_ids: [],
      published_to: [],
      published_destination_instance_ids: [],
      publish_trace: [],
      metadata: {},
      monitor_id: "monitor-1",
      monitor_name: "Agent Watch",
      created_at: "2026-03-02T00:00:00Z",
    } as never);
    mockedGetArticleById.mockResolvedValue(null as never);

    const { container } = render(<ReportDetailPage />);

    await waitFor(() => expect(screen.getByText("Anthropic MCP Research", { selector: "header h1" })).toBeInTheDocument());
    const header = container.querySelector("header");
    expect(header).not.toBeNull();
    expect(
      within(header as HTMLElement).getByText("MCP 正从工具协议变成平台分发层，接下来要看谁能占住生态入口。")
    ).toBeInTheDocument();
  });

  it("renders the paper report title without daily rewriting", async () => {
    mockedGetReportById.mockResolvedValue({
      id: "report-paper",
      user_id: null,
      time_period: "daily",
      report_type: "paper",
      title: "Paper Digest",
      report_date: "2026-03-02",
      tldr: [],
      article_count: 0,
      topics: [],
      events: [],
      global_tldr: "",
      content: "# Paper Digest\n\n## 本期导读\nIntro",
      article_ids: [],
      published_to: [],
      metadata: {},
      monitor_id: "monitor-1",
      monitor_name: "Paper Watch",
      created_at: "2026-03-02T00:00:00Z",
    } as never);
    mockedGetArticleById.mockResolvedValue(null as never);

    render(<ReportDetailPage />);

    await waitFor(() => expect(screen.getByText("2026-03-02 论文推荐", { selector: "header h1" })).toBeInTheDocument());
    expect(screen.getByText("Paper Watch")).toBeInTheDocument();
    expect(screen.queryByText(/^AI 早报/)).not.toBeInTheDocument();
  });

  it("normalizes legacy paper digest titles and summary headings on detail pages", async () => {
    mockedGetReportById.mockResolvedValue({
      id: "report-paper-legacy",
      user_id: null,
      time_period: "daily",
      report_type: "paper",
      title: "GUI 智能体的评测、安全与长程记忆",
      report_date: "2026-03-22",
      tldr: [],
      article_count: 0,
      topics: [],
      events: [],
      global_tldr: "",
      content: "# GUI 智能体的评测、安全与长程记忆\n\n## 今日锐评\n\n本期聚焦 GUI agent 的奖励建模。",
      article_ids: [],
      published_to: [],
      metadata: { paper_mode: "digest" },
      monitor_id: "monitor-1",
      monitor_name: "Paper Watch",
      created_at: "2026-03-22T00:00:00Z",
    } as never);
    mockedGetArticleById.mockResolvedValue(null as never);

    render(<ReportDetailPage />);

    await waitFor(() =>
      expect(screen.getByText("2026-03-22 论文推荐", { selector: "header h1" })).toBeInTheDocument()
    );
    expect(screen.getByRole("heading", { name: "总结" })).toBeInTheDocument();
    expect(screen.queryByText("今日锐评")).not.toBeInTheDocument();
  });

  it("renders a paper badge for paper reports", async () => {
    mockedGetReportById.mockResolvedValue({
      id: "report-paper",
      user_id: null,
      time_period: "daily",
      report_type: "paper",
      title: "Paper Digest",
      report_date: "2026-03-02",
      tldr: [],
      article_count: 0,
      topics: [],
      events: [],
      global_tldr: "",
      content: "# Paper Digest\n\n## 本期导读\nIntro",
      article_ids: [],
      published_to: [],
      metadata: {},
      monitor_id: "monitor-1",
      monitor_name: "Paper Watch",
      created_at: "2026-03-02T00:00:00Z",
    } as never);
    mockedGetArticleById.mockResolvedValue(null as never);

    render(<ReportDetailPage />);

    await waitFor(() => expect(screen.getByText("2026-03-02 论文推荐", { selector: "header h1" })).toBeInTheDocument());
    expect(screen.getByText("论文")).toBeInTheDocument();
  });

  it("does not render a top digest relations banner for paper reports", async () => {
    mockedGetReportById.mockResolvedValue({
      id: "report-paper-digest",
      user_id: null,
      time_period: "daily",
      report_type: "paper",
      title: "Paper Digest",
      report_date: "2026-03-02",
      tldr: [],
      article_count: 0,
      topics: [],
      events: [],
      global_tldr: "",
      content:
        "# Paper Digest\n\n## 本期导读\nIntro\n\n### 1. Nemotron-Cascade 2\n- 为什么重要：值得重点关注\n- 详细笔记：见关联阅读笔记",
      article_ids: [],
      published_to: [],
      metadata: {
        paper_mode: "digest",
        paper_note_links: [
          { report_id: "note-1", title: "Nemotron-Cascade 2" },
        ],
      },
      monitor_id: "monitor-1",
      monitor_name: "Paper Watch",
      created_at: "2026-03-02T00:00:00Z",
    } as never);
    mockedGetArticleById.mockResolvedValue(null as never);

    render(<ReportDetailPage />);

    await waitFor(() => expect(screen.getByText("2026-03-02 论文推荐", { selector: "header h1" })).toBeInTheDocument());
    expect(screen.queryByText("本期包含的详细阅读笔记")).not.toBeInTheDocument();
    expect(screen.getByText("为什么重要：值得重点关注")).toBeInTheDocument();
    expect(screen.queryByText("阅读建议：必读")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "查看详细笔记" })).not.toBeInTheDocument();
  });

  it("renders authored paper digests without duplicate body titles or raw frontmatter", async () => {
    mockedGetReportById.mockResolvedValue({
      id: "report-paper-authored",
      user_id: null,
      time_period: "daily",
      report_type: "paper",
      title: "Paper Digest",
      report_date: "2026-03-02",
      tldr: [],
      article_count: 0,
      topics: [],
      events: [],
      global_tldr: "",
      content: `---
date: 2026-03-02
keywords:
  - gui agent
tags:
  - daily-papers
---

# Paper Digest

## 总结

本期聚焦 GUI agent 的奖励建模。

## Safety

### 1. OS-Themis

- 作者：Alice
- 机构：Example Lab
- 链接：[Abs](https://arxiv.org/abs/2603.19191)
- 来源：arXiv

![OS-Themis](https://example.com/os-themis.png)

- **核心方法**：通过多智能体 critic 建模奖励。`,
      article_ids: [],
      published_to: [],
      metadata: {
        paper_mode: "digest",
      },
      monitor_id: "monitor-1",
      monitor_name: "Paper Watch",
      created_at: "2026-03-02T00:00:00Z",
    } as never);
    mockedGetArticleById.mockResolvedValue(null as never);

    render(<ReportDetailPage />);

    await waitFor(() => expect(screen.getByText("2026-03-02 论文推荐", { selector: "header h1" })).toBeInTheDocument());
    expect(screen.getAllByText("2026-03-02 论文推荐", { selector: "h1" })).toHaveLength(1);
    expect(screen.queryByText("date: 2026-03-02")).not.toBeInTheDocument();
    expect(screen.getByText("本期聚焦 GUI agent 的奖励建模。")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "总结" })).toBeInTheDocument();
    expect(
      screen.getByText((_, element) => element?.textContent === "核心方法：通过多智能体 critic 建模奖励。")
    ).toBeInTheDocument();
    expect(screen.getByAltText("OS-Themis")).toBeInTheDocument();
  });

  it("does not render a top source hint for paper note reports", async () => {
    mockedGetReportById.mockResolvedValue({
      id: "report-paper-note",
      user_id: null,
      time_period: "daily",
      report_type: "paper",
      title: "Paper Note",
      report_date: "2026-03-02",
      tldr: [],
      article_count: 0,
      topics: [],
      events: [],
      global_tldr: "",
      content: "# Paper Note\n\nContent",
      article_ids: [],
      published_to: [],
      metadata: {
        paper_mode: "note",
        parent_report_id: "report-paper-digest",
      },
      monitor_id: "monitor-1",
      monitor_name: "Paper Watch",
      created_at: "2026-03-02T00:00:00Z",
    } as never);
    mockedGetArticleById.mockResolvedValue(null as never);

    render(<ReportDetailPage />);

    await waitFor(() => expect(screen.getByText("Paper Note", { selector: "header h1" })).toBeInTheDocument());
    expect(screen.queryByText(/本笔记来自/)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "论文推荐 digest" })).not.toBeInTheDocument();
  });

  it("falls back to grouped article cards when report.content has no heading structure", async () => {
    mockedGetReportById.mockResolvedValue({
      id: "report-2",
      user_id: null,
      time_period: "daily",
      report_type: "daily",
      title: "AI Daily",
      report_date: "2026-03-02",
      tldr: [],
      article_count: 1,
      topics: [],
      events: [],
      global_tldr: "",
      content: "plain text body without heading markers",
      article_ids: ["article-1"],
      published_to: [],
      published_destination_instance_ids: [],
      publish_trace: [],
      metadata: {},
      monitor_id: "monitor-1",
      monitor_name: "Agent Watch",
      created_at: "2026-03-02T00:00:00Z",
    } as never);
    mockedGetArticleById.mockResolvedValue({
      id: "article-1",
      source_id: "source-1",
      source_name: "Test Source",
      category: "news",
      title: "Fallback article title",
      url: "https://example.com/a",
      summary: "Fallback summary",
      keywords: [],
      ai_score: 0.8,
      status: "completed",
      source_type: "rss",
      report_ids: [],
      published_at: "2026-03-02T00:00:00Z",
      collected_at: "2026-03-02T00:00:00Z",
      created_at: "2026-03-02T00:00:00Z",
    } as never);

    render(<ReportDetailPage />);

    await waitFor(() => expect(screen.getByText("Fallback article title")).toBeInTheDocument());
    expect(mockedGetArticleById).toHaveBeenCalledWith("article-1");
    expect(screen.queryByRole("heading", { name: "Outline" })).not.toBeInTheDocument();
  }, 10000);

  it("does not render a delete action on report detail", async () => {
    mockedGetReportById.mockResolvedValue({
      id: "report-1",
      user_id: null,
      time_period: "daily",
      report_type: "daily",
      title: "AI Daily",
      report_date: "2026-03-02",
      tldr: [],
      article_count: 0,
      topics: [],
      events: [],
      global_tldr: "",
      content: "# AI Daily\n\n## 全局总结与锐评\nA",
      article_ids: [],
      published_to: [],
      published_destination_instance_ids: [],
      publish_trace: [],
      metadata: {},
      monitor_id: "monitor-1",
      monitor_name: "Agent Watch",
      created_at: "2026-03-02T00:00:00Z",
    } as never);

    render(<ReportDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Agent Watch")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "删除报告" })).not.toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("renders manual resync statuses for enabled destinations", async () => {
    mockedGetReportById.mockResolvedValue({
      id: "report-1",
      user_id: null,
      time_period: "daily",
      report_type: "daily",
      title: "AI Daily",
      report_date: "2026-03-02",
      tldr: [],
      article_count: 0,
      topics: [],
      events: [],
      global_tldr: "",
      content: "# AI Daily\n\n## 全局总结与锐评\nA",
      article_ids: [],
      published_to: ["notion"],
      published_destination_instance_ids: ["dest-notion-1"],
      publish_trace: [
        {
          stage: "publish",
          sink: "obsidian",
          provider: "dest-obsidian-1",
          destination_instance_id: "dest-obsidian-1",
          destination_instance_name: "Obsidian Vault",
          status: "failed",
          url: null,
          error: "network error",
          latency_ms: 12,
          trigger: "manual",
        },
      ],
      metadata: {},
      monitor_id: "monitor-1",
      monitor_name: "Agent Watch",
      created_at: "2026-03-02T00:00:00Z",
    } as never);

    render(<ReportDetailPage />);

    await waitFor(() => expect(screen.getByText("同步")).toBeInTheDocument());
    expect(screen.getByText("Notion Workspace")).toBeInTheDocument();
    expect(screen.getByText("已同步")).toBeInTheDocument();
    expect(screen.getByText("Obsidian Vault")).toBeInTheDocument();
    expect(screen.getByText("上次失败")).toBeInTheDocument();
    expect(screen.queryByText("RSS Feed")).not.toBeInTheDocument();
  });

  it("publishes report to a destination and refreshes the status", async () => {
    mockedGetReportById.mockResolvedValue({
      id: "report-1",
      user_id: null,
      time_period: "daily",
      report_type: "daily",
      title: "AI Daily",
      report_date: "2026-03-02",
      tldr: [],
      article_count: 0,
      topics: [],
      events: [],
      global_tldr: "",
      content: "# AI Daily\n\n## 全局总结与锐评\nA",
      article_ids: [],
      published_to: [],
      published_destination_instance_ids: [],
      publish_trace: [],
      metadata: {},
      monitor_id: "monitor-1",
      monitor_name: "Agent Watch",
      created_at: "2026-03-02T00:00:00Z",
    } as never);
    mockedPublishReportToDestination.mockResolvedValue({
      id: "report-1",
      user_id: null,
      time_period: "daily",
      report_type: "daily",
      title: "AI Daily",
      report_date: "2026-03-02",
      tldr: [],
      article_count: 0,
      topics: [],
      events: [],
      global_tldr: "",
      content: "# AI Daily\n\n## 全局总结与锐评\nA",
      article_ids: [],
      published_to: ["obsidian"],
      published_destination_instance_ids: ["dest-obsidian-1"],
      publish_trace: [
        {
          stage: "publish",
          sink: "obsidian",
          provider: "dest-obsidian-1",
          destination_instance_id: "dest-obsidian-1",
          destination_instance_name: "Obsidian Vault",
          status: "success",
          url: "/tmp/obsidian-vault/AI Daily.md",
          error: null,
          latency_ms: 18,
          trigger: "manual",
        },
      ],
      metadata: {},
      monitor_id: "monitor-1",
      monitor_name: "Agent Watch",
      created_at: "2026-03-02T00:00:00Z",
    } as never);

    render(<ReportDetailPage />);

    await waitFor(() => expect(screen.getByRole("button", { name: "同步到 Obsidian Vault" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "同步到 Obsidian Vault" }));
    const dialogTitle = await screen.findByRole("heading", { name: "确认同步" });
    const dialog = dialogTitle.closest("div.rounded-3xl");
    expect(dialog).not.toBeNull();
    expect(within(dialog as HTMLElement).getByText("Obsidian Vault")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "确认同步" }));

    await waitFor(() => {
      expect(mockedPublishReportToDestination).toHaveBeenCalledWith("report-1", ["dest-obsidian-1"]);
    });
    expect(await screen.findByText("已同步")).toBeInTheDocument();
  });

  it("does not publish when the sync confirmation is cancelled", async () => {
    mockedGetReportById.mockResolvedValue({
      id: "report-1",
      user_id: null,
      time_period: "daily",
      report_type: "daily",
      title: "AI Daily",
      report_date: "2026-03-02",
      tldr: [],
      article_count: 0,
      topics: [],
      events: [],
      global_tldr: "",
      content: "# AI Daily\n\n## 全局总结与锐评\nA",
      article_ids: [],
      published_to: [],
      published_destination_instance_ids: [],
      publish_trace: [],
      metadata: {},
      monitor_id: "monitor-1",
      monitor_name: "Agent Watch",
      created_at: "2026-03-02T00:00:00Z",
    } as never);

    render(<ReportDetailPage />);

    await waitFor(() => expect(screen.getByRole("button", { name: "同步到 Obsidian Vault" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "同步到 Obsidian Vault" }));
    expect(await screen.findByRole("heading", { name: "确认同步" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "取消" }));

    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: "确认同步" })).not.toBeInTheDocument();
    });
    expect(mockedPublishReportToDestination).not.toHaveBeenCalled();
  });
});
