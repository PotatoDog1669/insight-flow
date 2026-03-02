import { fireEvent, render, screen } from "@testing-library/react";

import { ReportDocument } from "@/components/report/ReportDocument";

describe("ReportDocument", () => {
  it("collapses runtime meta by default and toggles event sections", () => {
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

    fireEvent.click(screen.getByRole("button", { name: /Event A #1/i }));
    expect(screen.getByText("Body")).toBeInTheDocument();
  });
});
