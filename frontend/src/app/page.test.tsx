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
  ReportCard: ({ report }: { report: { title: string } }) => <div>{report.title}</div>,
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

    expect(screen.getByText("No fresh reports available today.")).toBeInTheDocument();
  });

  it("shows timeout error when reports request hangs", async () => {
    vi.useFakeTimers();
    try {
      mockedGetReports.mockImplementation(() => new Promise(() => {}) as never);
      render(<DiscoverPage />);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(15000);
      });

      expect(screen.getByText("Failed to load reports: Request timeout after 15s")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
