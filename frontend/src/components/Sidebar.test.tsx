import { render, screen } from "@testing-library/react";

import { Sidebar } from "@/components/Sidebar";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

describe("Sidebar", () => {
  it("renders Chinese navigation labels", () => {
    render(<Sidebar />);

    expect(screen.getByRole("link", { name: "报告" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "任务" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "归档" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "信息源" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "模型配置" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "输出配置" })).toBeInTheDocument();
  });

  it("uses Insight Flow brand and no legacy brand text", () => {
    render(<Sidebar />);

    expect(screen.getAllByText("Insight Flow").length).toBeGreaterThan(0);
    expect(screen.queryByText("LexDeepResearch")).not.toBeInTheDocument();
  });
});
