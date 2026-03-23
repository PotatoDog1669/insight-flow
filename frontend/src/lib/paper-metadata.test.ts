import { asPaperMetadata } from "./paper-metadata";
import type { Report } from "./api";

function makeReport(metadata: Record<string, unknown>): Report {
  return {
    id: "r1",
    user_id: null,
    monitor_id: "m1",
    monitor_name: "Monitor",
    time_period: "daily",
    report_type: "paper",
    title: "Paper Digest",
    report_date: "2026-03-20",
    tldr: [],
    article_count: 0,
    topics: [],
    events: [],
    global_tldr: "",
    content: "",
    article_ids: [],
    published_to: [],
    metadata,
    created_at: "2026-03-20T00:00:00Z",
  };
}

describe("asPaperMetadata", () => {
  it("parses digest metadata with note links", () => {
    const report = makeReport({
      paper_mode: "digest",
      paper_note_links: [
        { report_id: "note-1", paper_identity: "paper:1234", title: "Note 1" },
        { report_id: "note-2" },
      ],
    });

    const meta = asPaperMetadata(report);

    expect(meta.paper_mode).toBe("digest");
    expect(meta.parent_report_id).toBeUndefined();
    expect(meta.paper_note_links).toEqual([
      { report_id: "note-1", paper_identity: "paper:1234", title: "Note 1" },
      { report_id: "note-2" },
    ]);
  });

  it("parses note metadata with parent report id", () => {
    const report = makeReport({
      paper_mode: "note",
      parent_report_id: "digest-1",
    });

    const meta = asPaperMetadata(report);

    expect(meta.paper_mode).toBe("note");
    expect(meta.parent_report_id).toBe("digest-1");
    expect(meta.paper_note_links).toBeUndefined();
  });

  it("handles malformed metadata safely", () => {
    const report = makeReport({
      paper_mode: "unknown",
      parent_report_id: 123,
      paper_note_links: [
        { report_id: 1 },
        { report_id: "note-1", title: 42 },
        "invalid",
      ],
    } as never);

    const meta = asPaperMetadata(report);

    expect(meta.paper_mode).toBeUndefined();
    expect(meta.parent_report_id).toBeUndefined();
    expect(meta.paper_note_links).toEqual([{ report_id: "note-1" }]);
  });
});
