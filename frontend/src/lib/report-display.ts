type ReportType = "daily" | "weekly" | "research" | "paper";

interface ReportDisplayInput {
  report_type: ReportType;
  report_date: string;
  title: string;
  metadata?: Record<string, unknown> | null;
}

function paperMode(metadata: Record<string, unknown> | null | undefined): string {
  return typeof metadata?.paper_mode === "string" ? metadata.paper_mode : "";
}

export function getReportDisplayTitle(report: ReportDisplayInput): string {
  if (report.report_type === "daily" && report.report_date) {
    return `AI 早报 ${report.report_date}`;
  }
  if (report.report_type === "paper" && report.report_date && paperMode(report.metadata) !== "note") {
    return `${report.report_date} 论文推荐`;
  }
  return report.title;
}
