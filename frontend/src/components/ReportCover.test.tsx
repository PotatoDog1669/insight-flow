import { render, screen } from "@testing-library/react";

import { ReportCover } from "@/components/ReportCover";

describe("ReportCover", () => {
  it.each([
    ["daily", "bg-emerald-50", "dark:bg-emerald-950/30"],
    ["weekly", "bg-indigo-50", "dark:bg-indigo-950/30"],
    ["research", "bg-amber-50", "dark:bg-amber-950/30"],
  ] as const)("renders %s as a plain color block", (reportType, lightClass, darkClass) => {
    const { container } = render(<ReportCover reportType={reportType} className="custom-cover" />);

    const cover = container.firstElementChild;

    expect(cover).not.toBeNull();
    expect(cover).toHaveClass("custom-cover", lightClass, darkClass);
    expect(cover?.childElementCount).toBe(0);
    expect(cover).toBeEmptyDOMElement();
    expect(container.querySelectorAll("svg")).toHaveLength(0);
    expect(screen.queryByText(/Insights|OpenAI|Google|Anthropic|Meta|Apple|X|GitHub|NVIDIA/)).not.toBeInTheDocument();
  });
});
