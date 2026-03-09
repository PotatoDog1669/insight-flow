import { fireEvent, render, screen, waitFor } from "@testing-library/react";

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
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => {
      expect(mockedUpdateSource).toHaveBeenCalledWith("source-twitter", {
        config: expect.objectContaining({
          usernames: ["anthropic", "OpenAI"],
        }),
      });
    });
    expect(onUpdated).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
  });
});
