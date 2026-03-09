import { render, screen } from "@testing-library/react";

import { SourceStatusPanel } from "@/components/SourceStatusPanel";
import type { Source } from "@/lib/api";

function makeSource(overrides: Partial<Source> = {}): Source {
  return {
    id: overrides.id ?? "source-1",
    name: overrides.name ?? "OpenAI",
    category: overrides.category ?? "blog",
    collect_method: overrides.collect_method ?? "rss",
    config: overrides.config ?? { feed_url: "https://openai.com/news/rss.xml" },
    enabled: overrides.enabled ?? true,
    status: overrides.status ?? "healthy",
    last_run: overrides.last_run ?? null,
    last_collected: overrides.last_collected ?? null,
    created_at: overrides.created_at ?? "2026-03-05T00:00:00Z",
    updated_at: overrides.updated_at ?? "2026-03-05T00:00:00Z",
  };
}

describe("SourceStatusPanel brand logos", () => {
  it("uses a website logo image for blog cards", () => {
    render(<SourceStatusPanel sources={[makeSource()]} />);

    const logo = screen.getByAltText("OpenAI logo");
    expect(logo).toHaveAttribute("src", expect.stringContaining("openai.com"));
  });

  it("prefers brand domain mapping for aliases", () => {
    render(
      <SourceStatusPanel
        sources={[
          makeSource({
            id: "source-qwen",
            name: "阿里 Qwen",
            config: { feed_url: "https://qwenlm.github.io/blog/index.xml" },
          }),
        ]}
      />
    );

    const logo = screen.getByAltText("阿里 Qwen logo");
    expect(logo).toHaveAttribute("src", expect.stringContaining("qwen.ai"));
  });

  it("uses explicit ByteDance icon instead of favicon", () => {
    render(
      <SourceStatusPanel
        sources={[
          makeSource({
            id: "source-bytedance",
            name: "字节跳动 Seed",
            config: { url: "https://seed.bytedance.com/zh/blog" },
          }),
        ]}
      />
    );

    expect(screen.queryByAltText("字节跳动 Seed logo")).not.toBeInTheDocument();
    expect(screen.getByLabelText("字节跳动 Seed logo")).toBeInTheDocument();
  });

  it("uses explicit Xiaohongshu icon instead of favicon", () => {
    render(
      <SourceStatusPanel
        sources={[
          makeSource({
            id: "source-xhs",
            name: "小红书",
            config: { url: "https://www.xiaohongshu.com/about/news" },
          }),
        ]}
      />
    );

    expect(screen.queryByAltText("小红书 logo")).not.toBeInTheDocument();
    expect(screen.getByLabelText("小红书 logo")).toBeInTheDocument();
  });
});
