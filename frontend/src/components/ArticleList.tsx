"use client";

import { Article } from "@/lib/api";

interface ArticleListProps {
    articles: Article[];
}

export default function ArticleList({ articles }: ArticleListProps) {
    if (articles.length === 0) {
        return (
            <div className="text-center py-12 text-gray-500">
                暂无采集数据，请先触发一次采集任务。
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {articles.map((article) => (
                <div
                    key={article.id}
                    className="p-4 rounded-lg border border-gray-200 hover:border-indigo-300 transition-colors"
                >
                    <div className="flex items-start justify-between">
                        <div className="flex-1">
                            <h3 className="font-semibold text-lg">
                                {article.url ? (
                                    <a
                                        href={article.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="hover:text-indigo-600 transition-colors"
                                    >
                                        {article.title}
                                    </a>
                                ) : (
                                    article.title
                                )}
                            </h3>
                            {article.summary && (
                                <p className="mt-1 text-gray-600 text-sm">{article.summary}</p>
                            )}
                            <div className="mt-2 flex items-center gap-3 text-xs text-gray-400">
                                <span>{article.status}</span>
                                <span>·</span>
                                <span>{new Date(article.collected_at).toLocaleString("zh-CN")}</span>
                                {article.ai_score !== null && (
                                    <>
                                        <span>·</span>
                                        <span>⭐ {article.ai_score.toFixed(2)}</span>
                                    </>
                                )}
                            </div>
                            {article.keywords.length > 0 && (
                                <div className="mt-2 flex flex-wrap gap-1">
                                    {article.keywords.map((kw) => (
                                        <span
                                            key={kw}
                                            className="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 text-xs"
                                        >
                                            {kw}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            ))}
        </div>
    );
}
