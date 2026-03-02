import { fireEvent, render, screen } from "@testing-library/react";

import { ReportOutline } from "@/components/report/ReportOutline";

describe("ReportOutline", () => {
  it("renders heading anchors for parsed outline items", () => {
    const onNavigate = vi.fn();
    render(
      <ReportOutline
        items={[
          { id: "summary", title: "全局总结与锐评", level: 2, kind: "summary", eventIndex: null },
          { id: "event-1", title: "Event A #1", level: 2, kind: "event", eventIndex: 1 },
        ]}
        activeId="summary"
        onNavigate={onNavigate}
      />
    );

    const summaryLink = screen.getByRole("link", { name: "全局总结与锐评" });
    expect(summaryLink).toHaveAttribute("href", "#summary");

    fireEvent.click(summaryLink);
    expect(onNavigate).toHaveBeenCalledWith("summary");
  });

  it("highlights the active outline item", () => {
    render(
      <ReportOutline
        items={[
          { id: "summary", title: "全局总结与锐评", level: 2, kind: "summary", eventIndex: null },
          { id: "event-1", title: "Event A #1", level: 2, kind: "event", eventIndex: 1 },
        ]}
        activeId="event-1"
        onNavigate={() => {}}
      />
    );

    const activeLink = screen.getByRole("link", { name: "Event A #1" });
    expect(activeLink.className).toContain("font-medium");
    expect(activeLink).toHaveAttribute("aria-current", "true");
  });
});
