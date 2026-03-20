"use client";

import { motion } from "framer-motion";
import { ChevronRight, Calendar, Trash2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { zhCN } from "date-fns/locale";
import type { ReportTopic } from "@/lib/api";
import { ReportCover } from "./ReportCover";

export interface Report {
    id: string;
    time_period: "daily" | "weekly" | "custom";
    report_type: "daily" | "weekly" | "research" | "paper";
    title: string;
    report_date: string;
    tldr: string[];
    article_count: number;
    topics?: ReportTopic[];
    monitor_id?: string | null;
    monitor_name?: string;
}

interface ReportCardProps {
    report: Report;
    index: number;
    onDelete?: (reportId: string) => void;
    deleting?: boolean;
}

const reportTypeConfig = {
    daily: { label: "日报", color: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" },
    weekly: { label: "周报", color: "bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300" },
    research: { label: "研究", color: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" },
    paper: { label: "论文", color: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300" },
};

export function ReportCard({ report, index, onDelete, deleting = false }: ReportCardProps) {
    const rConfig = reportTypeConfig[report.report_type];

    return (
        <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: index * 0.05, ease: "easeOut" }}
            className="relative"
        >
            {onDelete ? (
                <button
                    type="button"
                    onClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        onDelete(report.id);
                    }}
                    disabled={deleting}
                    className="absolute right-3 top-3 z-20 inline-flex items-center justify-center rounded-md bg-red-50 px-2.5 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-red-900/30 dark:text-red-300 dark:hover:bg-red-900/40"
                    aria-label={`删除报告 ${report.title}`}
                    title="删除报告"
                >
                    <Trash2 className="w-3.5 h-3.5" />
                </button>
            ) : null}
            <Link href={`/reports/${report.id}`} className="block h-full">
                <Card className="group h-full flex flex-col md:flex-row relative overflow-hidden border-border/40 hover:border-border/80 hover:shadow-lg transition-all duration-300 transform-gpu hover:-translate-y-1">
                    <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
                    <div className="absolute top-0 left-0 w-full md:w-[2px] md:h-full h-[2px] bg-gradient-to-r md:bg-gradient-to-b from-blue-500/0 via-blue-500/40 to-blue-500/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

                    {/* Report cover */}
                    <div className="md:w-[32%] lg:w-[28%] shrink-0 flex flex-col items-stretch">
                        <ReportCover reportType={report.report_type} className="h-40 md:h-full w-full rounded-t-xl md:rounded-tr-none md:rounded-l-xl" />
                    </div>

                    <CardContent className="p-4 md:p-5 xl:p-6 pr-14 relative z-10 bg-background/20 flex-1 flex flex-col justify-center">
                        <div className="flex flex-col gap-4">

                            {/* Header: Meta information */}
                            <div className="flex items-center justify-between">
                                <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                                    <Badge variant="secondary" className={`${rConfig.color} border-none font-medium px-2 py-0.5 capitalize`}>
                                        {rConfig.label}
                                    </Badge>
                                    <span className="flex items-center space-x-1 ml-2">
                                        <Calendar className="w-3.5 h-3.5" />
                                        <span>{new Date(report.report_date).toLocaleDateString()}</span>
                                    </span>
                                    <span className="hidden sm:flex items-center space-x-1 opacity-70">
                                        <span>({formatDistanceToNow(new Date(report.report_date), { addSuffix: true, locale: zhCN })})</span>
                                    </span>
                                </div>
                            </div>

                            {/* Title */}
                            <div>
                                <h2 className="text-xl font-semibold tracking-tight leading-snug flex items-center group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                                    {report.title}
                                    <ChevronRight className="w-5 h-5 ml-1 opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-muted-foreground" />
                                </h2>
                                {report.monitor_name ? (
                                    <p className="mt-2 text-sm text-muted-foreground">
                                        所属任务：<span className="font-medium text-foreground/80">{report.monitor_name}</span>
                                    </p>
                                ) : null}
                            </div>

                            {/* TL;DR Bullet Points */}
                            {report.tldr && report.tldr.length > 0 && (
                                <div className="bg-muted/30 rounded-md p-4 space-y-2">

                                    <ul className="space-y-1.5 list-none m-0 p-0 text-sm text-muted-foreground">
                                        {report.tldr.slice(0, 4).map((point, i) => (
                                            <li key={i} className="flex items-start">
                                                <span className="mr-2 mt-1.5 w-1 h-1 rounded-full bg-muted-foreground/50 shrink-0" />
                                                <span className="leading-relaxed line-clamp-3">{point}</span>
                                            </li>
                                        ))}
                                    </ul>
                                    {report.tldr.length > 4 && (
                                        <div className="pt-1 text-xs text-muted-foreground/80 font-medium">
                                            + 还有 {report.tldr.length - 4} 条洞察...
                                        </div>
                                    )}
                                </div>
                            )}

                        </div>
                    </CardContent>
                </Card>
            </Link>
        </motion.div>
    );
}
