import { fireEvent, render, screen } from "@testing-library/react";

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
  it("prefers a bundled local logo image for known blog cards", () => {
    render(<SourceStatusPanel sources={[makeSource()]} />);

    const logo = screen.getByAltText("OpenAI logo");
    expect(logo).toHaveAttribute("src", expect.stringContaining("/logos/openai"));
    expect(logo).not.toHaveAttribute("src", expect.stringContaining("google.com/s2/favicons"));
  });

  it("prefers a bundled local logo image for aliases", () => {
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
    expect(logo).toHaveAttribute("src", expect.stringContaining("/logos/alibaba-qwen"));
  });

  it("prefers a bundled local logo image for academic sources", () => {
    render(
      <SourceStatusPanel
        sources={[
          makeSource({
            id: "source-openalex",
            name: "OpenAlex",
            category: "academic",
            collect_method: "openalex_api",
            config: { base_url: "https://api.openalex.org/works" },
          }),
        ]}
      />
    );

    const logo = screen.getByAltText("OpenAlex logo");
    expect(logo).toHaveAttribute("src", expect.stringContaining("/logos/openalex"));
  });

  it("uses the official bundled PubMed logo asset", () => {
    render(
      <SourceStatusPanel
        sources={[
          makeSource({
            id: "source-pubmed",
            name: "PubMed",
            category: "academic",
            collect_method: "pubmed_api",
            config: { base_url: "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/" },
          }),
        ]}
      />
    );

    const logo = screen.getByAltText("PubMed logo");
    expect(logo).toHaveAttribute("src", expect.stringContaining("/logos/pubmed-logo"));
  });

  it("uses the official bundled Europe PMC logo asset", () => {
    render(
      <SourceStatusPanel
        sources={[
          makeSource({
            id: "source-europe-pmc",
            name: "Europe PMC",
            category: "academic",
            collect_method: "europe_pmc_api",
            config: { base_url: "https://www.ebi.ac.uk/europepmc/webservices/rest/search" },
          }),
        ]}
      />
    );

    const logo = screen.getByAltText("Europe PMC logo");
    expect(logo).toHaveAttribute("src", expect.stringContaining("/logos/europe-pmc-logo"));
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

  it("shows all social sources in the social media tab", () => {
    render(
      <SourceStatusPanel
        sources={[
          makeSource({ id: "source-x", name: "X", category: "social", collect_method: "twitter_snaplytics" }),
          makeSource({ id: "source-reddit", name: "Reddit", category: "social", collect_method: "rss" }),
          makeSource({ id: "source-openai", name: "OpenAI", category: "blog", collect_method: "rss" }),
        ]}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /Social Media/i }));

    expect(screen.getByText("X")).toBeInTheDocument();
    expect(screen.getByText("Reddit")).toBeInTheDocument();
    expect(screen.queryByText("OpenAI")).not.toBeInTheDocument();
  });
});
