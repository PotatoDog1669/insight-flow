import { fireEvent, render, screen } from "@testing-library/react";

import { ReportMetaPanel } from "@/components/report/ReportMetaPanel";

describe("ReportMetaPanel", () => {
  it("shows event count, source count and topic chips", () => {
    const onTopicSelect = vi.fn();
    render(
      <ReportMetaPanel
        eventCount={3}
        sourceCount={2}
        topics={[
          { name: "agent", weight: 3 },
          { name: "safety", weight: 2 },
        ]}
        onTopicSelect={onTopicSelect}
      />
    );

    expect(screen.getByText("3 events")).toBeInTheDocument();
    expect(screen.getByText("2 sources")).toBeInTheDocument();
    const topicButton = screen.getByRole("button", { name: "agent" });
    expect(topicButton).toBeInTheDocument();

    fireEvent.click(topicButton);
    expect(onTopicSelect).toHaveBeenCalledWith("agent");
  });
});
