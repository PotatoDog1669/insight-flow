interface ReportCoverProps {
  reportType: "daily" | "weekly" | "research";
  className?: string;
}

const coverColors = {
  daily: "bg-emerald-50 dark:bg-emerald-950/30",
  weekly: "bg-indigo-50 dark:bg-indigo-950/30",
  research: "bg-amber-50 dark:bg-amber-950/30",
} as const;

export function ReportCover({ reportType, className = "h-40 md:flex-1 md:h-full sm:h-48 rounded-t-xl" }: ReportCoverProps) {
  return <div className={`${coverColors[reportType]} ${className}`.trim()} />;
}
