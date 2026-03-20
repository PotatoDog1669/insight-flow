import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import LibraryPage from "@/app/library/page";
import { deleteReport, getReportFilters, getReports } from "@/lib/api";

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
    report: { id: string; title: string; monitor_name?: string; report_type: string };
    onDelete?: (id: string) => void;
  }) => {
    if (report.report_type === "paper") {
      throw new Error("paper report cards are not wired yet");
    }
    return (
      <div>
        <span>{report.title}</span>
        {report.monitor_name ? <span>{report.monitor_name}</span> : null}
        {onDelete ? (
          <button type="button" onClick={() => onDelete(report.id)}>
            Delete {report.title}
          </button>
        ) : null}
      </div>
    );
  },
}));

vi.mock("@/lib/api", () => ({
  getReports: vi.fn(),
  getReportFilters: vi.fn(),
  deleteReport: vi.fn(),
}));

const mockedGetReports = vi.mocked(getReports);
const mockedGetReportFilters = vi.mocked(getReportFilters);
const mockedDeleteReport = vi.mocked(deleteReport);

describe("LibraryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockedGetReports.mockResolvedValue([
      {
        id: "report-1",
        user_id: null,
        time_period: "daily",
        report_type: "daily",
        title: "Agent Report",
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
      {
        id: "report-2",
        user_id: null,
        time_period: "weekly",
        report_type: "weekly",
        title: "Infra Report",
        report_date: "2026-03-01",
        tldr: [],
        article_count: 1,
        topics: [],
        events: [],
        global_tldr: "",
        content: "",
        article_ids: [],
        published_to: [],
        metadata: {},
        monitor_id: "monitor-2",
        monitor_name: "Infra Watch",
        created_at: "2026-03-01T00:00:00Z",
      },
    ] as never);
    mockedGetReportFilters.mockResolvedValue({
      time_periods: ["daily", "weekly"],
      report_types: ["daily", "weekly"],
      categories: [],
      monitors: [
        { id: "monitor-1", name: "Agent Watch" },
        { id: "monitor-2", name: "Infra Watch" },
      ],
    } as never);
    mockedDeleteReport.mockResolvedValue(undefined as never);
  });

  it("filters reports by monitor", async () => {
    render(<LibraryPage />);

    await waitFor(() => {
      expect(screen.getByText("Agent Report")).toBeInTheDocument();
      expect(screen.getByText("Infra Report")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("任务主题"), {
      target: { value: "monitor-1" },
    });

    expect(screen.getByText("Agent Report")).toBeInTheDocument();
    expect(screen.queryByText("Infra Report")).not.toBeInTheDocument();
  });

  it("deletes a report from the archive list", async () => {
    render(<LibraryPage />);

    await waitFor(() => {
      expect(screen.getByText("Agent Report")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Delete Agent Report" }));

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalledWith("确认删除这份报告吗？");
      expect(mockedDeleteReport).toHaveBeenCalledWith("report-1");
    });
    expect(screen.queryByText("Agent Report")).not.toBeInTheDocument();
  });

  it("does not delete when the archive confirmation is cancelled", async () => {
    vi.mocked(window.confirm).mockReturnValue(false);
    render(<LibraryPage />);

    await waitFor(() => {
      expect(screen.getByText("Agent Report")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Delete Agent Report" }));

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalledWith("确认删除这份报告吗？");
    });
    expect(mockedDeleteReport).not.toHaveBeenCalled();
    expect(screen.getByText("Agent Report")).toBeInTheDocument();
  });

  it("renders paper reports in the archive list", async () => {
    mockedGetReports.mockResolvedValue([
      {
        id: "report-paper",
        user_id: null,
        time_period: "daily",
        report_type: "paper",
        title: "Paper Report",
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
        monitor_id: "monitor-3",
        monitor_name: "Paper Watch",
        created_at: "2026-03-02T00:00:00Z",
      },
    ] as never);

    render(<LibraryPage />);

    await waitFor(() => {
      expect(screen.getByText("Paper Report")).toBeInTheDocument();
    });
  });
});
