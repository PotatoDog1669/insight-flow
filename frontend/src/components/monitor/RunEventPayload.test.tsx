import { render, screen } from "@testing-library/react";

import { RunEventPayload } from "@/components/monitor/RunEventPayload";

describe("RunEventPayload", () => {
  it("renders kept and dropped sections for transparent log payloads", () => {
    render(
      <RunEventPayload
        payload={{
          kind: "transparent_log",
          summary: {
            provider: "llm_openai",
            kept: 2,
            dropped: 1,
          },
          sections: [
            {
              title: "Kept Items",
              type: "article_items",
              count: 2,
              artifact_path: "output/run_artifacts/run-1/source_a/03_pipeline_filter_kept.json",
              items: [
                {
                  title: "GPT-5.3 Instant System Card",
                  source_name: "OpenAI",
                  external_id: "article-1",
                  url: "https://openai.com/a",
                },
              ],
            },
            {
              title: "Dropped Items",
              type: "article_items",
              count: 1,
              artifact_path: "output/run_artifacts/run-1/source_a/03_pipeline_filter_dropped.json",
              items: [
                {
                  title: "Careers",
                  source_name: "Seed",
                  reason: "filtered_out_by_provider",
                },
              ],
            },
          ],
        }}
      />
    );

    expect(screen.getByText("Kept Items")).toBeInTheDocument();
    expect(screen.getByText("Dropped Items")).toBeInTheDocument();
    expect(screen.getByText("GPT-5.3 Instant System Card")).toBeInTheDocument();
    expect(screen.getByText("Careers")).toBeInTheDocument();
    expect(screen.getByText("filtered_out_by_provider")).toBeInTheDocument();
    expect(screen.getAllByText(/03_pipeline_filter_/)).toHaveLength(2);
  });

  it("falls back to json for unknown payloads", () => {
    render(<RunEventPayload payload={{ foo: "bar" }} />);

    expect(screen.getByText(/"foo": "bar"/)).toBeInTheDocument();
  });
});
