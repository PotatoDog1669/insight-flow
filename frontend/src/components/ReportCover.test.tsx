import { render, screen } from "@testing-library/react";

import { ReportCover } from "@/components/ReportCover";

describe("ReportCover", () => {
  it.each([
    ["daily", "from-emerald-100", "dark:from-emerald-950/80"],
    ["weekly", "from-indigo-100", "dark:from-indigo-950/80"],
    ["research", "from-amber-100", "dark:from-amber-950/80"],
  ] as const)("renders %s with the current gradient cover treatment", (reportType, lightClass, darkClass) => {
    const { container } = render(<ReportCover reportType={reportType} className="custom-cover" />);

    const cover = container.firstElementChild;

    expect(cover).not.toBeNull();
    expect(cover).toHaveClass("custom-cover", "bg-gradient-to-br", lightClass, darkClass);
    expect(cover?.childElementCount).toBeGreaterThan(0);
    expect(container.querySelectorAll("svg")).toHaveLength(1);
    expect(screen.queryByText(/Insights|OpenAI|Google|Anthropic|Meta|Apple|X|GitHub|NVIDIA/)).not.toBeInTheDocument();
  });
});
