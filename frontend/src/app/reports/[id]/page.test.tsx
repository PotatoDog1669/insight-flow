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
  it("renders document from report.content and outline", async () => {
    mockedGetReportById.mockResolvedValue({
      id: "report-1",
      user_id: null,
      time_period: "daily",
      depth: "deep",
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
      metadata: {},
      report_type: "deep",
      created_at: "2026-03-02T00:00:00Z",
    } as never);
    mockedGetArticleById.mockResolvedValue(null as never);

    render(<ReportDetailPage />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "全局总结与锐评" })).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Outline" })).toBeInTheDocument();
    expect(mockedGetArticleById).not.toHaveBeenCalled();
  });
});
