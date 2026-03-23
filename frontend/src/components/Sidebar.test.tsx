import { fireEvent, render, screen } from "@testing-library/react";

import { Sidebar } from "@/components/Sidebar";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

describe("Sidebar", () => {
  it("renders Chinese navigation labels", () => {
    render(<Sidebar />);

    expect(screen.queryAllByText("LexDeepResearch")).toHaveLength(0);
    expect(screen.getByRole("link", { name: "首页" })).toBeInTheDocument();
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
    expect(screen.queryByText("Lex Researcher")).not.toBeInTheDocument();
  });

  it("uses a darker sidebar surface than the main page background", () => {
    render(<Sidebar />);

    expect(screen.getByRole("complementary")).toHaveClass("bg-slate-100/95");
  });

  it("shows the updated default admin email in the user menu", () => {
    render(<Sidebar />);

    fireEvent.click(screen.getByRole("button", { name: /researcher/i }));

    expect(screen.getByText("admin@example.com")).toBeInTheDocument();
    expect(screen.queryByText("admin@lexmount.com")).not.toBeInTheDocument();
  });
});
