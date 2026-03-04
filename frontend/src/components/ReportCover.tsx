"use client";

import { useMemo } from "react";
import { Bot, Sparkles, Github, Asterisk, Globe, LayoutGrid, Twitter, Cpu, Eye, Code, Zap } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Topic } from "./ReportCard";

interface ReportCoverProps {
    topics?: Topic[];
    date: string;
    className?: string;
}

type BrandConfig = {
    bg: string;
    logoText: string;
    textColor: string;
    icon: LucideIcon;
    iconColors: string;
    dateColor: string;
};

const BRAND_CONFIGS: Record<string, BrandConfig> = {
    gemini: {
        bg: "bg-[#eef5ff] dark:bg-blue-950/30",
        logoText: "Gemini",
        textColor: "text-[#1a1a1a] dark:text-white",
        icon: Sparkles,
        iconColors: "text-blue-500 bg-blue-50",
        dateColor: "text-blue-500"
    },
    openai: {
        bg: "bg-[#e5e5e5]/80 dark:bg-neutral-900/40",
        logoText: "OpenAI",
        textColor: "text-[#1a1a1a] dark:text-white",
        icon: Bot,
        iconColors: "text-neutral-800 bg-neutral-100",
        dateColor: "text-neutral-600 dark:text-neutral-400"
    },
    nvidia: {
        bg: "bg-[#f0f7e6] dark:bg-green-950/30",
        logoText: "NVIDIA",
        textColor: "text-[#1a1a1a] dark:text-white",
        icon: Eye,
        iconColors: "text-green-700 bg-green-100",
        dateColor: "text-green-600"
    },
    anthropic: {
        bg: "bg-[#fff0e5] dark:bg-orange-950/30",
        logoText: "Anthropic",
        textColor: "text-[#1a1a1a] dark:text-white",
        icon: Asterisk,
        iconColors: "text-orange-600 bg-orange-100",
        dateColor: "text-orange-500"
    },
    github: {
        bg: "bg-slate-100 dark:bg-slate-900/40",
        logoText: "GitHub",
        textColor: "text-[#1a1a1a] dark:text-white",
        icon: Github,
        iconColors: "text-slate-800 bg-slate-200",
        dateColor: "text-slate-500 dark:text-slate-400"
    },
    microsoft: {
        bg: "bg-sky-50 dark:bg-sky-950/30",
        logoText: "Microsoft",
        textColor: "text-[#1a1a1a] dark:text-white",
        icon: LayoutGrid,
        iconColors: "text-sky-600 bg-sky-100",
        dateColor: "text-sky-600"
    },
    twitter: {
        bg: "bg-slate-50 dark:bg-slate-950/30",
        logoText: "X",
        textColor: "text-[#1a1a1a] dark:text-white",
        icon: Twitter,
        iconColors: "text-slate-700 bg-slate-200",
        dateColor: "text-slate-500 dark:text-slate-400"
    },
    default: {
        bg: "bg-indigo-50/80 dark:bg-indigo-950/30",
        logoText: "Insights",
        textColor: "text-[#1a1a1a] dark:text-white",
        icon: Globe,
        iconColors: "text-indigo-600 bg-indigo-100",
        dateColor: "text-indigo-500"
    }
};

const RANDOM_ICONS = [
    { icon: Cpu, colors: "text-pink-500 bg-pink-50" },
    { icon: Code, colors: "text-cyan-600 bg-cyan-50" },
    { icon: Zap, colors: "text-yellow-600 bg-yellow-50" },
    { icon: Globe, colors: "text-fuchsia-600 bg-fuchsia-50" }
];

export function ReportCover({ topics, date, className = "h-40 md:flex-1 md:h-full sm:h-48 rounded-t-xl" }: ReportCoverProps) {
    const { mainTopic, subTopics } = useMemo(() => {
        if (!topics || topics.length === 0) {
            return { mainTopic: BRAND_CONFIGS.default, subTopics: [BRAND_CONFIGS.openai, BRAND_CONFIGS.gemini, BRAND_CONFIGS.github] };
        }

        // Sort by weight descending
        const sorted = [...topics].sort((a, b) => b.weight - a.weight);

        const getMainConfig = (name: string) => {
            const key = name.toLowerCase();
            // Prefix matching logic or exact
            const matchedKey = Object.keys(BRAND_CONFIGS).find(k => key.includes(k));
            return matchedKey ? BRAND_CONFIGS[matchedKey] : BRAND_CONFIGS.default;
        };

        const main = getMainConfig(sorted[0].name);

        // Generate up to 6 sub-icons to fill the pill
        const sub = sorted.slice(1, 7).map(t => getMainConfig(t.name));

        // Fill the rest with random generic icons if less than 6
        const filledSub = [...sub];
        while (filledSub.length < 6) {
            const g = RANDOM_ICONS[filledSub.length % RANDOM_ICONS.length];
            filledSub.push({
                bg: "", logoText: "", textColor: "",
                icon: g.icon, iconColors: g.colors,
                dateColor: ""
            });
        }

        return { mainTopic: main, subTopics: filledSub };
    }, [topics]);

    return (
        <div title={date || "Latest"} className={`relative w-full overflow-hidden transition-colors duration-500 ${mainTopic.bg} ${className}`}>

            {/* Left hanging tab (Icons grid), rooted to bottom */}
            <div className="absolute left-3 xl:left-5 bottom-0 w-[100px] xl:w-[112px] bg-card rounded-t-[20px] xl:rounded-t-[24px] shadow-[0_-8px_30px_rgba(0,0,0,0.06)] border-t border-x border-border/10 pb-5 pt-4 z-10 transition-shadow flex flex-col items-center">
                <div className="grid grid-cols-2 gap-1.5 place-items-center w-fit">
                    {subTopics.slice(0, 6).map((topic, i) => {
                        const Icon = topic.icon;
                        return (
                            <div key={i} className={`w-9 h-9 xl:w-10 xl:h-10 rounded-full flex items-center justify-center ${topic.iconColors} shadow-sm ring-1 ring-black/5 dark:ring-white/10`}>
                                <Icon className="w-4 h-4 xl:w-5 xl:h-5" strokeWidth={1.5} />
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Right hanging tab (Brand Name), rooted to top */}
            <div className="absolute right-3 xl:right-5 top-0 w-[100px] xl:w-[112px] h-[72px] xl:h-[84px] bg-card rounded-b-[20px] xl:rounded-b-[24px] shadow-[0_8px_25px_rgba(0,0,0,0.05)] border-b border-x border-border/10 flex flex-col justify-center items-center z-10">
                <h3 className={`text-base xl:text-lg font-bold tracking-tight ${mainTopic.textColor}`}>
                    {mainTopic.logoText}
                </h3>
            </div>

        </div>
    );
}
