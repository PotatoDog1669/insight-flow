import { act, render, screen, waitFor } from "@testing-library/react";

import DiscoverPage from "@/app/page";
import { getReports } from "@/lib/api";

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

vi.mock("@/components/ReportCard", () => ({
  ReportCard: ({
    report,
    onDelete,
  }: {
    report: { title: string; monitor_name?: string; report_type: string };
    onDelete?: () => void;
  }) => {
    return (
      <div>
        <span>{report.title}</span>
        {report.monitor_name ? <span>{report.monitor_name}</span> : null}
        {onDelete ? <button type="button" onClick={onDelete}>删除报告</button> : null}
      </div>
    );
  },
}));

vi.mock("@/lib/api", () => ({
  getReports: vi.fn(),
}));

const mockedGetReports = vi.mocked(getReports);

describe("DiscoverPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetReports.mockResolvedValue([] as never);
  });

  it("loads reports without forcing report_type filter", async () => {
    render(<DiscoverPage />);

    await waitFor(() => {
      expect(mockedGetReports).toHaveBeenCalledWith({ limit: 10, page: 1 });
    });

    expect(screen.getByText("今日暂无新报告。")).toBeInTheDocument();
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

  it("renders paper reports in the discover feed", async () => {
    mockedGetReports.mockResolvedValue([
      {
        id: "report-paper",
        user_id: null,
        time_period: "daily",
        report_type: "paper",
        title: "Paper Brief",
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
        monitor_name: "Paper Watch",
        created_at: "2026-03-02T00:00:00Z",
      },
    ] as never);

    render(<DiscoverPage />);

    await waitFor(() => {
      expect(screen.getByText("Paper Brief")).toBeInTheDocument();
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
      expect(screen.getByText("Agent Brief")).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: "删除报告" })).not.toBeInTheDocument();
  });
});
