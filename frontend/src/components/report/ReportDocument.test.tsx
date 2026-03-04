import { fireEvent, render, screen } from "@testing-library/react";

import { ReportDocument } from "@/components/report/ReportDocument";

describe("ReportDocument", () => {
  it("collapses runtime meta by default and renders event sections", () => {
    render(
      <ReportDocument
        content={`# T
生成时间(UTC): 2026-03-02T00:00:00Z
样本输入数: 5

## 全局总结与锐评
A

## 正文

---
## Event A #1
Body`}
        events={[]}
        globalTldr=""
        topics={[]}
      />
    );

    const metaButton = screen.getByRole("button", { name: /运行元信息/i });
    expect(metaButton).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("样本输入数: 5")).not.toBeInTheDocument();

    fireEvent.click(metaButton);
    expect(metaButton).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("样本输入数: 5")).toBeInTheDocument();

    expect(screen.getByRole("heading", { name: /Event A #1/i, level: 2 })).toBeInTheDocument();
    expect(screen.getByText("Body")).toBeInTheDocument();
  });

  it("renders all event sections provided in content", () => {
    const eventSections = Array.from({ length: 20 })
      .map((_, idx) => `---\n## Event ${idx + 1} #${idx + 1}\nBody ${idx + 1}`)
      .join("\n\n");
    render(
      <ReportDocument
        content={`# T\n\n## 正文\n\n${eventSections}`}
        events={[]}
        globalTldr=""
        topics={[]}
      />
    );

    expect(screen.getByRole("heading", { name: /Event 15 #15/i, level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Event 16 #16/i, level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Event 20 #20/i, level: 2 })).toBeInTheDocument();
    expect(screen.getByText("Body 20")).toBeInTheDocument();
  });
});
