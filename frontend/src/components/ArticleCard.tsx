"use client";

import { motion } from "framer-motion";
import { ExternalLink, Star, FileText } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDistanceToNow } from "date-fns";
import { zhCN } from "date-fns/locale";

export interface Article {
    id: string;
    source_name: string;
    title: string;
    url: string;
    summary: string;
    score: number;
    published_at: string;
    tags: string[];
}

interface ArticleCardProps {
    article: Article;
    index: number;
}

export function ArticleCard({ article, index }: ArticleCardProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: index * 0.05, ease: "easeOut" }}
        >
            <Card className="group relative overflow-hidden border-border/40 bg-card hover:border-border/80 hover:shadow-sm transition-all duration-300">
                <CardContent className="p-6">
                    <div className="flex flex-col gap-4">

                        {/* Header: Meta information */}
                        <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-3 text-sm text-muted-foreground">
                                <span className="flex items-center space-x-1.5 bg-muted/50 px-2.5 py-1 rounded-md">
                                    <FileText className="w-3.5 h-3.5" />
                                    <span className="font-medium text-foreground/80">{article.source_name}</span>
                                </span>
                                <span className="text-muted-foreground/30">•</span>
                                <span>{formatDistanceToNow(new Date(article.published_at), { addSuffix: true, locale: zhCN })}</span>
                            </div>

                            {/* Score Badge */}
                            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-400 text-xs font-semibold">
                                <Star className="w-3.5 h-3.5 fill-current" />
                                <span>{article.score.toFixed(1)}</span>
                            </div>
                        </div>

                        {/* Content Core */}
                        <div>
                            <a href={article.url} target="_blank" rel="noopener noreferrer" className="inline-block group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                                <h2 className="text-xl font-semibold tracking-tight leading-snug mb-2 flex items-center">
                                    {article.title}
                                    <ExternalLink className="w-4 h-4 ml-2 opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-muted-foreground" />
                                </h2>
                            </a>
                            <p className="text-muted-foreground leading-relaxed text-sm">
                                {article.summary}
                            </p>
                        </div>

                        {/* Footer: Tags */}
                        <div className="flex items-center gap-2 pt-2">
                            {article.tags.map((tag) => (
                                <Badge key={tag} variant="secondary" className="bg-muted/40 hover:bg-muted text-xs font-normal text-muted-foreground">
                                    {tag}
                                </Badge>
                            ))}
                        </div>

                    </div>
                </CardContent>
            </Card>
        </motion.div>
    );
}
