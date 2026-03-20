import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { SourceDetailModal } from "@/components/SourceDetailModal";
import { testSource, updateSource, type Source } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    updateSource: vi.fn(),
    testSource: vi.fn(),
  };
});

const mockedUpdateSource = vi.mocked(updateSource);
const mockedTestSource = vi.mocked(testSource);

function makeTwitterSource(overrides: Partial<Source> = {}): Source {
  return {
    id: overrides.id ?? "source-twitter",
    name: overrides.name ?? "X",
    category: overrides.category ?? "social",
    collect_method: overrides.collect_method ?? "twitter_snaplytics",
    config: overrides.config ?? { usernames: ["anthropic"] },
    enabled: overrides.enabled ?? true,
    status: overrides.status ?? "healthy",
    last_run: overrides.last_run ?? null,
    last_collected: overrides.last_collected ?? null,
    created_at: overrides.created_at ?? "2026-03-05T00:00:00Z",
    updated_at: overrides.updated_at ?? "2026-03-05T00:00:00Z",
  };
}

function makeArxivSource(overrides: Partial<Source> = {}): Source {
  return {
    id: overrides.id ?? "source-arxiv",
    name: overrides.name ?? "arXiv",
    category: overrides.category ?? "academic",
    collect_method: overrides.collect_method ?? "rss",
    config:
      overrides.config ??
      {
        arxiv_api: true,
        feed_url: "https://export.arxiv.org/api/query",
        keywords: ["reasoning"],
        categories: ["cs.AI"],
      },
    enabled: overrides.enabled ?? true,
    status: overrides.status ?? "healthy",
    last_run: overrides.last_run ?? null,
    last_collected: overrides.last_collected ?? null,
    created_at: overrides.created_at ?? "2026-03-05T00:00:00Z",
    updated_at: overrides.updated_at ?? "2026-03-05T00:00:00Z",
  };
}

function makeRedditSource(overrides: Partial<Source> = {}): Source {
  return {
    id: overrides.id ?? "source-reddit",
    name: overrides.name ?? "Reddit",
    category: overrides.category ?? "social",
    collect_method: overrides.collect_method ?? "rss",
    config: overrides.config ?? { subreddits: ["LocalLLaMA", "OpenAI"], max_items: 30, fetch_detail: false },
    enabled: overrides.enabled ?? true,
    status: overrides.status ?? "healthy",
    last_run: overrides.last_run ?? null,
    last_collected: overrides.last_collected ?? null,
    created_at: overrides.created_at ?? "2026-03-05T00:00:00Z",
    updated_at: overrides.updated_at ?? "2026-03-05T00:00:00Z",
  };
}

function makeOpenAlexSource(overrides: Partial<Source> = {}): Source {
  return {
    id: overrides.id ?? "source-openalex",
    name: overrides.name ?? "OpenAlex",
    category: overrides.category ?? "academic",
    collect_method: overrides.collect_method ?? "openalex",
    config:
      overrides.config ??
      {
        base_url: "https://api.openalex.org/works",
        keywords: ["reasoning"],
        max_results: 20,
        api_key: "",
        mailto: "research@example.com",
        supports_time_window: true,
        auth_mode: "optional_api_key",
      },
    enabled: overrides.enabled ?? true,
    status: overrides.status ?? "healthy",
    last_run: overrides.last_run ?? null,
    last_collected: overrides.last_collected ?? null,
    created_at: overrides.created_at ?? "2026-03-05T00:00:00Z",
    updated_at: overrides.updated_at ?? "2026-03-05T00:00:00Z",
  };
}

describe("SourceDetailModal social usernames", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUpdateSource.mockResolvedValue(makeTwitterSource() as never);
    mockedTestSource.mockResolvedValue({
      success: true,
      message: "ok",
      sample_articles: [],
    });
  });

  it("persists username immediately when clicking Add", async () => {
    const onUpdated = vi.fn();
    render(
      <SourceDetailModal
        source={makeTwitterSource()}
        onClose={vi.fn()}
        onUpdated={onUpdated}
      />
    );

    fireEvent.change(screen.getByPlaceholderText("@OpenAI"), {
      target: { value: "@OpenAI" },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Add" }));
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockedUpdateSource).toHaveBeenCalledWith("source-twitter", {
      config: expect.objectContaining({
        usernames: ["anthropic", "OpenAI"],
      }),
    });
    expect(onUpdated).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
  });
});

describe("SourceDetailModal reddit subreddits", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUpdateSource.mockResolvedValue(makeRedditSource() as never);
    mockedTestSource.mockResolvedValue({
      success: true,
      message: "ok",
      sample_articles: [],
    });
  });

  it("persists subreddit immediately when clicking Add", async () => {
    const onUpdated = vi.fn();
    render(
      <SourceDetailModal
        source={makeRedditSource()}
        onClose={vi.fn()}
        onUpdated={onUpdated}
      />
    );

    expect(screen.getByText("Tracked Subreddits")).toBeInTheDocument();
    expect(screen.queryByLabelText("Target URL")).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("r/LocalLLaMA"), {
      target: { value: "r/MachineLearning" },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Add" }));
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockedUpdateSource).toHaveBeenCalledWith("source-reddit", {
      config: expect.objectContaining({
        subreddits: ["LocalLLaMA", "OpenAI", "MachineLearning"],
      }),
    });
    expect(onUpdated).toHaveBeenCalledTimes(1);
  });

  it("persists subreddit removal immediately", async () => {
    render(
      <SourceDetailModal
        source={makeRedditSource()}
        onClose={vi.fn()}
        onUpdated={vi.fn()}
      />
    );

    await act(async () => {
      fireEvent.click(screen.getByLabelText("Remove OpenAI"));
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockedUpdateSource).toHaveBeenCalledWith("source-reddit", {
      config: expect.objectContaining({
        subreddits: ["LocalLLaMA"],
      }),
    });
  });
});

describe("SourceDetailModal target url", () => {
  it("prefills blog scraper url from target_url when config only has site_key", () => {
    const source = {
      ...makeTwitterSource({
        id: "source-blog",
        name: "Anthropic",
        category: "blog",
        collect_method: "blog_scraper",
        config: { site_key: "anthropic", max_items: 20 },
      }),
      target_url: "https://anthropic.com/news",
    } as Source;

    render(
      <SourceDetailModal
        source={source}
        onClose={vi.fn()}
        onUpdated={vi.fn()}
      />
    );

    expect(screen.getByDisplayValue("https://anthropic.com/news")).toBeInTheDocument();
  });
});

describe("SourceDetailModal arXiv test controls", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUpdateSource.mockResolvedValue(makeArxivSource() as never);
    mockedTestSource.mockResolvedValue({
      success: true,
      message: "ok",
      fetched_count: 12,
      matched_count: 3,
      effective_keywords: ["agent", "multimodal"],
      effective_max_results: 12,
      window_start: "2026-03-01T00:00:00Z",
      window_end: "2026-03-15T23:59:59Z",
      sample_articles: [],
    });
  });

  it("renders arxiv-specific test controls and submits test-only params", async () => {
    render(
      <SourceDetailModal
        source={makeArxivSource()}
        onClose={vi.fn()}
        onUpdated={vi.fn()}
      />
    );

    expect(screen.getByText("arXiv Test")).toBeInTheDocument();
    expect(screen.getByLabelText("Keywords for arXiv test")).toBeInTheDocument();
    expect(screen.getByLabelText("Max results for arXiv test")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Last 15 Days" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Start time for arXiv test")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("End time for arXiv test")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Keywords for arXiv test"), {
      target: { value: "agent, multimodal" },
    });
    fireEvent.change(screen.getByLabelText("Max results for arXiv test"), {
      target: { value: "40" },
    });
    fireEvent.change(screen.getByLabelText("Start date for arXiv test"), {
      target: { value: "2026-03-01" },
    });
    fireEvent.change(screen.getByLabelText("End date for arXiv test"), {
      target: { value: "2026-03-15" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Run Test" }));

    await waitFor(() => {
      expect(mockedTestSource).toHaveBeenCalledWith(
        "source-arxiv",
        {
          keywords: ["agent", "multimodal"],
          max_results: 40,
          start_at: new Date(2026, 2, 1, 0, 0, 0, 0).toISOString(),
          end_at: new Date(2026, 2, 15, 23, 59, 59, 999).toISOString(),
        }
      );
    });
  });

  it("keeps generic sources on the old connectivity test UI", () => {
    render(
      <SourceDetailModal
        source={makeTwitterSource()}
        onClose={vi.fn()}
        onUpdated={vi.fn()}
      />
    );

    expect(screen.getByText("Connectivity Test")).toBeInTheDocument();
    expect(screen.queryByLabelText("Keywords for arXiv test")).not.toBeInTheDocument();
  });

  it("renders shared academic api controls and api key input for openalex", async () => {
    mockedUpdateSource.mockResolvedValue(makeOpenAlexSource() as never);
    mockedTestSource.mockResolvedValue({
      success: true,
      message: "ok",
      fetched_count: 2,
      matched_count: 1,
      effective_keywords: ["agent"],
      effective_max_results: 2,
      window_start: "2026-03-01T00:00:00Z",
      window_end: "2026-03-15T23:59:59Z",
      sample_articles: [],
    });

    render(
      <SourceDetailModal
        source={makeOpenAlexSource()}
        onClose={vi.fn()}
        onUpdated={vi.fn()}
      />
    );

    expect(screen.getByText("Academic API Test")).toBeInTheDocument();
    expect(screen.getByLabelText("Keywords for academic API test")).toBeInTheDocument();
    expect(screen.getByLabelText("Max results for academic API test")).toBeInTheDocument();
    expect(screen.getByLabelText("Start date for academic API test")).toBeInTheDocument();
    expect(screen.getByLabelText("End date for academic API test")).toBeInTheDocument();
    expect(screen.getByLabelText("API Key")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Keywords for academic API test"), {
      target: { value: "agent" },
    });
    fireEvent.change(screen.getByLabelText("Max results for academic API test"), {
      target: { value: "2" },
    });
    fireEvent.change(screen.getByLabelText("Start date for academic API test"), {
      target: { value: "2026-03-01" },
    });
    fireEvent.change(screen.getByLabelText("End date for academic API test"), {
      target: { value: "2026-03-15" },
    });
    fireEvent.change(screen.getByLabelText("API Key"), {
      target: { value: "demo-key" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(mockedUpdateSource).toHaveBeenCalledWith(
        "source-openalex",
        {
          config: expect.objectContaining({
            api_key: "demo-key",
          }),
        }
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "Run Test" }));

    await waitFor(() => {
      expect(mockedTestSource).toHaveBeenCalledWith(
        "source-openalex",
        {
          keywords: ["agent"],
          max_results: 2,
          start_at: new Date(2026, 2, 1, 0, 0, 0, 0).toISOString(),
          end_at: new Date(2026, 2, 15, 23, 59, 59, 999).toISOString(),
        }
      );
    });
  });
});
