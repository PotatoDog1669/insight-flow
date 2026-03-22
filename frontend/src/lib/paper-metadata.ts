import type { Report } from "./api";

export type PaperMode = "digest" | "note";

export interface PaperNoteLink {
  report_id: string;
  paper_identity?: string;
  title?: string;
}

export interface PaperReportMetadata {
  paper_mode?: PaperMode;
  paper_note_links?: PaperNoteLink[];
  parent_report_id?: string;
}

export function asPaperMetadata(report: Report): PaperReportMetadata {
  const raw = (report.metadata ?? {}) as Record<string, unknown>;

  const paper_mode =
    typeof raw.paper_mode === "string" && (raw.paper_mode === "digest" || raw.paper_mode === "note")
      ? raw.paper_mode
      : undefined;

  const parent_report_id = typeof raw.parent_report_id === "string" ? raw.parent_report_id : undefined;

  const rawLinks = Array.isArray(raw.paper_note_links) ? raw.paper_note_links : [];
  const paper_note_links: PaperNoteLink[] = rawLinks
    .map((item) => (item ?? {}) as Record<string, unknown>)
    .map((item) => ({
      report_id: typeof item.report_id === "string" ? item.report_id : "",
      paper_identity: typeof item.paper_identity === "string" ? item.paper_identity : undefined,
      title: typeof item.title === "string" ? item.title : undefined,
    }))
    .filter((item) => item.report_id);

  return {
    paper_mode,
    parent_report_id,
    paper_note_links: paper_note_links.length ? paper_note_links : undefined,
  };
}

