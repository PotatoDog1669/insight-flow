import { Calendar, Layers, BookOpen, Sparkles } from "lucide-react";

interface ReportCoverProps {
  reportType: "daily" | "weekly" | "research";
  className?: string;
}

const coverConfig = {
  daily: {
    bg: "from-emerald-100 via-teal-50 to-emerald-50 dark:from-emerald-950/80 dark:via-teal-900/60 dark:to-emerald-950/50",
    icon: Calendar,
    accent: "text-emerald-600/10 dark:text-emerald-400/10",
    dot: "bg-emerald-500",
    glow: "bg-emerald-300/30 dark:bg-emerald-700/20",
  },
  weekly: {
    bg: "from-indigo-100 via-blue-50 to-indigo-50 dark:from-indigo-950/80 dark:via-blue-900/60 dark:to-indigo-950/50",
    icon: Layers,
    accent: "text-indigo-600/10 dark:text-indigo-400/10",
    dot: "bg-indigo-500",
    glow: "bg-indigo-300/30 dark:bg-indigo-700/20",
  },
  research: {
    bg: "from-amber-100 via-orange-50 to-amber-50 dark:from-amber-950/80 dark:via-orange-900/60 dark:to-amber-950/50",
    icon: BookOpen,
    accent: "text-amber-600/10 dark:text-amber-400/10",
    dot: "bg-amber-500",
    glow: "bg-amber-300/30 dark:bg-amber-700/20",
  },
} as const;

export function ReportCover({ reportType, className = "h-40 md:flex-1 md:h-full sm:h-48 rounded-t-xl" }: ReportCoverProps) {
  const config = coverConfig[reportType];
  const Icon = config.icon;

  return (
    <div className={`relative overflow-hidden bg-gradient-to-br ${config.bg} ${className}`.trim()}>
      {/* Glow orb */}
      <div className={`absolute -right-12 -top-12 w-40 h-40 blur-3xl rounded-full ${config.glow}`} />
      <div className={`absolute -left-12 -bottom-12 w-48 h-48 blur-3xl rounded-full ${config.glow}`} />

      {/* Grid Pattern */}
      <div
        className="absolute inset-0 opacity-[0.03] dark:opacity-[0.05]"
        style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, currentColor 1px, transparent 0)', backgroundSize: '16px 16px' }}
      />
      
      {/* Diagonal stripes */}
      <div className="absolute inset-0 opacity-10 dark:opacity-20"
        style={{ background: 'repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(0,0,0,0.02) 10px, rgba(0,0,0,0.02) 20px)' }}
      />

      {/* Large watermark icon */}
      <div className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 ${config.accent}`}>
        <Icon strokeWidth={1} className="w-24 h-24 sm:w-28 sm:h-28 md:w-36 md:h-36 lg:w-48 lg:h-48 -rotate-[12deg]" />
      </div>
      
      {/* Decorative top left dots */}
      <div className="absolute top-4 left-4 flex gap-1.5 opacity-60">
        <div className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
        <div className={`w-1.5 h-1.5 rounded-full ${config.dot} opacity-50`} />
        <div className={`w-1.5 h-1.5 rounded-full ${config.dot} opacity-20`} />
      </div>

      {/* Shine overlay */}
      <div className="absolute top-0 right-0 w-full h-full bg-gradient-to-b from-white/20 dark:from-white/5 to-transparent pointer-events-none" />
    </div>
  );
}
