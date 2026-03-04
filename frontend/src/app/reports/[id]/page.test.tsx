import { render, screen, waitFor } from "@testing-library/react";

import ReportDetailPage from "@/app/reports/[id]/page";
import { getArticleById, getReportById } from "@/lib/api";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "report-1" }),
}));

vi.mock("@/lib/api", () => ({
  getReportById: vi.fn(),
  getArticleById: vi.fn(),
}));

const mockedGetReportById = vi.mocked(getReportById);
const mockedGetArticleById = vi.mocked(getArticleById);

describe("ReportDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
      metadata: {},
      created_at: "2026-03-02T00:00:00Z",
    } as never);
    mockedGetArticleById.mockResolvedValue(null as never);

    render(<ReportDetailPage />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "全局总结与锐评" })).toBeInTheDocument());
    expect(screen.getByRole("navigation", { name: "Report outline" })).toBeInTheDocument();
    expect(mockedGetArticleById).not.toHaveBeenCalled();
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
      metadata: {},
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
  });
});
