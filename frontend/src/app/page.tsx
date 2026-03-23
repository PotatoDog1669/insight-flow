"use client";

import { useEffect, useState } from "react";
import { ReportCard, type Report as ReportCardModel } from "@/components/ReportCard";
import {
  createMonitor,
  getDestinations,
  getReports,
  getSources,
  type Destination,
  type MonitorAgentDraftResponse,
  type MonitorAgentResponse,
  type MonitorAgentStatusStreamEvent,
  type MonitorCreate,
  type MonitorSourceOverride,
  type Report as APIReport,
  type Source,
  streamMonitorAgentMessage,
} from "@/lib/api";
import { getReportDisplayTitle } from "@/lib/report-display";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, ChevronDown } from "lucide-react";

const DISCOVER_REPORTS_TIMEOUT_MS = 15_000;
const LATEST_REPORT_LIMIT = 3;
const QUICK_PROMPTS = [
  "关注 agent 前沿内容",
  "跟踪 AI 初创公司动态",
  "追踪多模态论文进展",
  "关注开源模型与工具发布",
];

type DraftSourceOption = {
  id: string;
  label: string;
  selected: boolean;
  reason?: string;
};

type InquiryTurn = {
  id: string;
  role: "user" | "assistant";
  body: string;
  progressSteps?: MonitorAgentStatusStreamEvent[];
};

type ActiveAssistantTurn = {
  body: string;
  progressSteps: MonitorAgentStatusStreamEvent[];
};

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const timerId = setTimeout(() => {
      reject(new Error(`Request timeout after ${Math.round(timeoutMs / 1000)}s`));
    }, timeoutMs);
    promise.then(
      (value) => {
        clearTimeout(timerId);
        resolve(value);
      },
      (error: unknown) => {
        clearTimeout(timerId);
        reject(error);
      }
    );
  });
}

function toCardReport(report: APIReport): ReportCardModel {
  return {
    id: report.id,
    time_period: report.time_period,
    report_type: report.report_type,
    title: getReportDisplayTitle(report),
    report_date: report.report_date,
    tldr: report.tldr,
    article_count: report.article_count,
    topics: report.topics,
    monitor_id: report.monitor_id,
    monitor_name: report.monitor_name,
  };
}

export default function DiscoverPage() {
  const router = useRouter();
  const [reports, setReports] = useState<ReportCardModel[]>([]);
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [replyMessage, setReplyMessage] = useState("");
  const [conversationId, setConversationId] = useState<string | undefined>(undefined);
  const [agentResponse, setAgentResponse] = useState<MonitorAgentResponse | null>(null);
  const [turns, setTurns] = useState<InquiryTurn[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [draftPayload, setDraftPayload] = useState<MonitorCreate | null>(null);
  const [draftSourceOptions, setDraftSourceOptions] = useState<DraftSourceOption[]>([]);
  const [draftSourceKeywordInputs, setDraftSourceKeywordInputs] = useState<Record<string, string>>({});
  const [expandedSourceCategories, setExpandedSourceCategories] = useState<Record<string, boolean>>({});
  const [activeAssistantTurn, setActiveAssistantTurn] = useState<ActiveAssistantTurn | null>(null);
  const [savingDraft, setSavingDraft] = useState(false);
  const [saveDraftError, setSaveDraftError] = useState<string | null>(null);
  const [saveDraftSuccess, setSaveDraftSuccess] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [data, destinationData, sourceData] = await withTimeout(
          Promise.all([getReports({ limit: 10, page: 1 }), getDestinations(), getSources()]),
          DISCOVER_REPORTS_TIMEOUT_MS
        );
        const filtered = data.filter((report) => {
          if (report.report_type !== "paper") return true;
          const rawMeta = (report.metadata ?? {}) as Record<string, unknown>;
          return rawMeta.paper_mode !== "note";
        });
        setReports(filtered.map(toCardReport));
        setDestinations(destinationData);
        setSources(sourceData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const latestReports = reports.slice(0, LATEST_REPORT_LIMIT);
  const draftResponse = agentResponse?.mode === "draft" ? agentResponse : null;
  const draftHasSelectedSources = (draftPayload?.source_ids.length || 0) > 0;
  const enabledDestinations = destinations.filter((item) => item.enabled);
  const enabledSources = sources.filter((item) => item.enabled);
  const sourceGroups = groupSourcesByCategory(enabledSources);
  const hasConversation = turns.length > 0 || agentResponse !== null || submitting;
  const showDraftCardLoader = Boolean(
    submitting &&
      !draftResponse &&
      activeAssistantTurn?.body &&
      activeAssistantTurn.progressSteps.some((step) => step.key === "draft")
  );

  const openInquiry = (nextMessage: string) => {
    setSaveDraftError(null);
    setSaveDraftSuccess(null);
    setDraftPayload(null);
    setDraftSourceOptions([]);
    setDraftSourceKeywordInputs({});
    setAgentResponse(null);
    setTurns([]);
    setActiveAssistantTurn(null);
    return submitInquiry({ text: nextMessage, resetConversation: true });
  };

  const submitInquiry = async ({
    text,
    resetConversation = false,
  }: {
    text: string;
    resetConversation?: boolean;
  }) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setSubmitting(true);
    setTurns((current) => [...current, { id: `user-${current.length + 1}`, role: "user", body: trimmed }]);
    setActiveAssistantTurn({ body: "", progressSteps: [] });

    let streamedBody = "";
    let streamedSteps: MonitorAgentStatusStreamEvent[] = [];
    try {
      const response = await streamMonitorAgentMessage(
        {
          message: trimmed,
          conversation_id: resetConversation ? undefined : conversationId,
        },
        {
          onStatus: (event) => {
            streamedSteps = upsertProgressStep(streamedSteps, event);
            setActiveAssistantTurn((current) => ({
              body: current?.body || "",
              progressSteps: upsertProgressStep(current?.progressSteps || [], event),
            }));
          },
          onMessageDelta: (event) => {
            streamedBody += event.delta;
            setActiveAssistantTurn((current) => ({
              body: `${current?.body || ""}${event.delta}`,
              progressSteps: current?.progressSteps || [],
            }));
          },
        }
      );
      setConversationId(response.conversation_id);
      setAgentResponse(response);
      setTurns((current) => [
        ...current,
        {
          id: `assistant-${current.length + 1}`,
          role: "assistant",
          body: streamedBody || response.message || (response.mode === "draft" ? "Draft ready." : ""),
          progressSteps: streamedSteps,
        },
      ]);
      if (response.mode === "draft") {
        setDraftPayload(normalizeMonitorPayload(response.monitor_payload));
        setDraftSourceOptions(extractDraftSourceOptions(response));
        setDraftSourceKeywordInputs(extractDraftSourceKeywordInputs(response.monitor_payload));
      } else {
        setDraftPayload(null);
        setDraftSourceOptions([]);
        setDraftSourceKeywordInputs({});
      }
    } finally {
      setActiveAssistantTurn(null);
      setSubmitting(false);
    }
  };

  const handleStartInquiry = async () => {
    const trimmed = message.trim();
    if (!trimmed) return;
    setMessage("");
    await openInquiry(trimmed);
  };

  const handleReply = async () => {
    const trimmed = replyMessage.trim();
    if (!trimmed) return;
    setReplyMessage("");
    await submitInquiry({ text: trimmed });
  };

  const handleQuickPrompt = (prompt: string) => {
    setMessage(prompt);
  };

  const handleMessageKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }
    event.preventDefault();
    void handleStartInquiry();
  };

  const handleReplyKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }
    event.preventDefault();
    void handleReply();
  };

  const handleCloseInquiry = () => {
    setConversationId(undefined);
    setMessage("");
    setReplyMessage("");
    setTurns([]);
    setActiveAssistantTurn(null);
    setAgentResponse(null);
    setDraftPayload(null);
    setDraftSourceOptions([]);
    setDraftSourceKeywordInputs({});
    setSaveDraftError(null);
    setSaveDraftSuccess(null);
  };

  const handleDraftNameChange = (name: string) => {
    setDraftPayload((current) => (current ? { ...current, name } : current));
  };

  const handleDraftTimePeriodChange = (timePeriod: MonitorCreate["time_period"]) => {
    setDraftPayload((current) => {
      if (!current) return current;
      return {
        ...current,
        time_period: timePeriod,
        custom_schedule: timePeriod === "custom" ? current.custom_schedule || "0 9 * * *" : current.custom_schedule,
      };
    });
  };

  const handleDraftReportTypeChange = (reportType: NonNullable<MonitorCreate["report_type"]>) => {
    setDraftPayload((current) => (current ? { ...current, report_type: reportType } : current));
  };

  const handleDraftCustomScheduleChange = (customSchedule: string) => {
    setDraftPayload((current) => (current ? { ...current, custom_schedule: customSchedule } : current));
  };

  const handleDraftSourceToggle = (sourceId: string) => {
    setDraftPayload((payload) => {
      if (!payload) return payload;
      const selectedSourceIds = new Set(payload.source_ids);
      const nextSourceOverrides = { ...(payload.source_overrides || {}) };
      if (selectedSourceIds.has(sourceId)) {
        selectedSourceIds.delete(sourceId);
        delete nextSourceOverrides[sourceId];
      } else {
        selectedSourceIds.add(sourceId);
      }
      return {
        ...payload,
        source_ids: Array.from(selectedSourceIds),
        source_overrides: nextSourceOverrides,
      };
    });
    setDraftSourceOptions((current) =>
      current.map((item) => (item.id === sourceId ? { ...item, selected: !item.selected } : item))
    );
    setDraftSourceKeywordInputs((current) => {
      const next = { ...current };
      if (sourceId in next) {
        delete next[sourceId];
      }
      return next;
    });
  };

  const handleDraftSourceUsernamesChange = (sourceId: string, usernames: string[]) => {
    setDraftPayload((current) => {
      if (!current) return current;
      return {
        ...current,
        source_overrides: upsertDraftSourceOverride(current.source_overrides || {}, sourceId, {
          ...(current.source_overrides?.[sourceId] || {}),
          usernames: dedupeStrings(usernames),
        }),
      };
    });
  };

  const handleDraftSourceSubredditsChange = (sourceId: string, subreddits: string[]) => {
    setDraftPayload((current) => {
      if (!current) return current;
      return {
        ...current,
        source_overrides: upsertDraftSourceOverride(current.source_overrides || {}, sourceId, {
          ...(current.source_overrides?.[sourceId] || {}),
          subreddits: normalizeRedditSubreddits(subreddits),
        }),
      };
    });
  };

  const handleDraftSourceKeywordsInputChange = (sourceId: string, value: string) => {
    setDraftSourceKeywordInputs((current) => ({
      ...current,
      [sourceId]: value,
    }));
    setDraftPayload((current) => {
      if (!current) return current;
      return {
        ...current,
        source_overrides: upsertDraftSourceOverride(current.source_overrides || {}, sourceId, {
          ...(current.source_overrides?.[sourceId] || {}),
          keywords: parseKeywordInput(value),
        }),
      };
    });
  };

  const handleDraftSourceMaxResultsChange = (sourceId: string, rawValue: string) => {
    setDraftPayload((current) => {
      if (!current) return current;
      const nextOverride = { ...(current.source_overrides?.[sourceId] || {}) };
      const trimmed = rawValue.trim();
      if (!trimmed) {
        delete nextOverride.max_results;
      } else {
        const parsed = Number(trimmed);
        if (!Number.isFinite(parsed)) {
          return current;
        }
        nextOverride.max_results = Math.max(1, Math.min(200, Math.floor(parsed)));
      }
      return {
        ...current,
        source_overrides: upsertDraftSourceOverride(current.source_overrides || {}, sourceId, nextOverride),
      };
    });
  };

  const handleToggleSourceCategory = (category: string) => {
    setExpandedSourceCategories((current) => ({
      ...current,
      [category]: !(current[category] ?? true),
    }));
  };

  const handleDraftDestinationToggle = (destinationId: string) => {
    setDraftPayload((current) => {
      if (!current) return current;
      const selected = Array.isArray(current.destination_instance_ids) ? current.destination_instance_ids : [];
      const nextSelection = selected.includes(destinationId)
        ? selected.filter((id) => id !== destinationId)
        : [...selected, destinationId];
      return {
        ...current,
        destination_instance_ids: nextSelection,
      };
    });
  };

  const handleSaveDraft = async () => {
    if (!draftPayload) return;
    setSavingDraft(true);
    setSaveDraftError(null);
    setSaveDraftSuccess(null);
    try {
      await createMonitor({
        ...draftPayload,
        source_ids: draftPayload.source_ids,
        window_hours: deriveWindowHours(draftPayload.report_type || "daily"),
        custom_schedule: draftPayload.time_period === "custom" ? draftPayload.custom_schedule : null,
      });
      setSaveDraftSuccess("监控已保存，正在跳转…");
      router.push("/monitors");
    } catch (err) {
      setSaveDraftError(err instanceof Error ? err.message : "保存 monitor 失败");
    } finally {
      setSavingDraft(false);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top,_rgba(210,224,244,0.58),_transparent_34%),linear-gradient(180deg,_#f6f8fc_0%,_#f9fbff_40%,_#ffffff_100%)]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,_rgba(255,255,255,0.88),_transparent_24%),radial-gradient(circle_at_80%_0%,_rgba(210,225,244,0.32),_transparent_20%)]" />

      <div className="relative mx-auto flex min-h-screen max-w-6xl flex-col px-4 pb-10 pt-6 md:px-8">
        <header className="flex items-center justify-between pb-6">
          <div />
          {hasConversation ? (
            <button
              type="button"
              onClick={handleCloseInquiry}
              className="rounded-full border border-slate-200/80 bg-white/85 px-4 py-2 text-sm font-medium text-slate-600 shadow-sm transition hover:border-slate-300 hover:text-slate-900"
            >
              New inquiry
            </button>
          ) : null}
        </header>

        {!hasConversation ? (
          <>
            <section className="flex flex-1 flex-col items-center justify-center pb-12 pt-12 text-center">
              {/* Greeting */}
              <div className="mb-8 flex flex-col items-center gap-3">
                <h1 className="font-serif text-[2.25rem] leading-tight tracking-tight text-slate-800">
                  Researcher, 想了解些什么？
                </h1>
              </div>

              {/* Input Box - Gemini Style */}
              <div className="w-full max-w-3xl px-4">
                <div className="group relative mx-auto w-full">
                  <div className="absolute -inset-1 rounded-[2.5rem] bg-gradient-to-b from-slate-200/50 to-slate-100/30 opacity-0 transition-opacity group-focus-within:opacity-100" />
                  <div className="relative flex w-full items-end gap-2 rounded-[2rem] border border-slate-200/80 bg-white/95 p-2.5 shadow-[0_8px_30px_rgba(0,0,0,0.04)] backdrop-blur-xl">
                    <textarea
                      value={message}
                      onChange={(event) => setMessage(event.target.value)}
                      onKeyDown={handleMessageKeyDown}
                      placeholder="Scout for what matters next"
                      rows={1}
                      className="w-full resize-none border-0 bg-transparent px-4 py-3 text-base text-slate-700 outline-none placeholder:text-slate-400 md:text-lg"
                      style={{ minHeight: '52px', maxHeight: '200px' }}
                    />
                    <button
                      type="button"
                      onClick={handleStartInquiry}
                      disabled={!message.trim()}
                      className="mb-1 mr-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-500 transition hover:bg-slate-200 hover:text-slate-800 disabled:opacity-50 disabled:hover:bg-slate-100 disabled:hover:text-slate-500"
                    >
                      <ArrowRight className="h-5 w-5" />
                    </button>
                  </div>
                </div>

                {/* Quick Prompts */}
                <div className="mt-8 flex flex-wrap items-center justify-center gap-2.5">
                  {QUICK_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => handleQuickPrompt(prompt)}
                      className="rounded-full border border-slate-200/70 bg-white/60 px-4 py-2 text-[13px] text-slate-600 shadow-[0_2px_8px_rgba(102,126,156,0.04)] backdrop-blur-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:bg-white hover:text-slate-900"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            </section>

            <section className="pb-10">
              <div className="mb-5 flex items-end justify-between gap-4">
                <div>
                  <h2 className="font-serif text-2xl text-slate-700 md:text-3xl">Recent briefs</h2>
                  <p className="mt-2 text-sm text-slate-500">A quick look at the latest generated reports.</p>
                </div>
                <Link
                  href="/library"
                  className="inline-flex items-center gap-1 text-sm font-medium text-slate-600 transition hover:text-slate-900"
                >
                  View library
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>

              {loading && <div className="py-10 text-sm text-muted-foreground">正在加载报告...</div>}
              {error && <div className="py-10 text-sm text-red-500">加载报告失败：{error}</div>}

              {!loading && !error && (
                <div className="space-y-6">
                    {latestReports.map((report, index) => (
                      <ReportCard key={report.id} report={report} index={index} entrySource="home" />
                    ))}
                  {latestReports.length === 0 ? (
                    <div className="rounded-3xl border border-dashed border-slate-300 bg-white/70 px-6 py-16 text-center text-sm text-slate-500">
                      今日暂无新报告。
                    </div>
                  ) : null}
                </div>
              )}
            </section>
          </>
        ) : (
          <div className="flex flex-1 flex-col pb-40">
            <section
              role="region"
              aria-label="Agent conversation"
              className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 pb-8 pt-4"
            >
              <div className="space-y-6">
                {turns.map((turn) => (
                  <div key={turn.id} className={turn.role === "user" ? "flex justify-end" : "flex justify-start"}>
                    {turn.role === "user" ? (
                      <div className="inline-flex max-w-[min(82%,42rem)] rounded-[1.6rem] rounded-tr-md border border-slate-200/80 bg-white/95 px-5 py-4 text-base leading-7 text-slate-700 shadow-[0_10px_28px_rgba(120,135,160,0.08)]">
                        {turn.body}
                      </div>
                    ) : (
                      <div className="max-w-3xl pt-0.5">
                        <div className="text-base leading-8 text-slate-700">{turn.body}</div>
                      </div>
                    )}
                  </div>
                ))}

                {activeAssistantTurn ? (
                  <div className="flex justify-start">
                    <div className="max-w-3xl pt-0.5">
                      {activeAssistantTurn.body ? (
                        <div className="text-base leading-8 text-slate-700">{activeAssistantTurn.body}</div>
                      ) : (
                        <AssistantLoader />
                      )}
                    </div>
                  </div>
                ) : null}

                {showDraftCardLoader ? <DraftCardLoader /> : null}

                {draftResponse && draftPayload ? (
                  <div data-testid="monitor-draft-card" className="max-w-[46rem]">
                    <div className="rounded-[1.5rem] border border-emerald-200/80 bg-white/94 p-5 shadow-[0_18px_44px_rgba(92,136,112,0.08)]">
                      <div className="mb-4 flex flex-col gap-2.5 border-b border-slate-200/70 pb-4 md:flex-row md:items-start md:justify-between">
                        <div>
                          <div className="text-xs uppercase tracking-[0.24em] text-emerald-600">监控草案</div>
                          <h3 className="mt-2 font-serif text-[1.65rem] leading-tight text-slate-800">{draftPayload.name}</h3>
                          {draftResponse.draft.summary ? (
                            <p className="mt-2.5 max-w-xl text-sm leading-6 text-slate-500">{draftResponse.draft.summary}</p>
                          ) : null}
                        </div>
                        <div className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-500">
                          默认模型 {draftPayload.ai_provider || "llm_openai"}
                        </div>
                      </div>

                      <div className="space-y-3.5">
                        <label className="block">
                          <span className="mb-1.5 block text-sm font-medium text-slate-700">监控名称</span>
                          <input
                            aria-label="监控名称"
                            value={draftPayload.name}
                            onChange={(event) => handleDraftNameChange(event.target.value)}
                            className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-700 outline-none"
                          />
                        </label>

                        <div data-testid="draft-type-frequency-row" className="grid gap-3 md:grid-cols-2">
                          <label className="block">
                            <span className="mb-1.5 block text-sm font-medium text-slate-700">报告类型</span>
                            <select
                              aria-label="报告类型"
                              value={draftPayload.report_type || "daily"}
                              onChange={(event) =>
                                handleDraftReportTypeChange(event.target.value as NonNullable<MonitorCreate["report_type"]>)
                              }
                              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-700 outline-none"
                            >
                              <option value="daily">日报</option>
                              <option value="weekly">周报</option>
                              <option value="research">深度研究</option>
                              <option value="paper">论文推荐</option>
                            </select>
                          </label>
                          <label className="block">
                            <span className="mb-1.5 block text-sm font-medium text-slate-700">频率</span>
                            <select
                              aria-label="频率"
                              value={draftPayload.time_period}
                              onChange={(event) =>
                                handleDraftTimePeriodChange(event.target.value as MonitorCreate["time_period"])
                              }
                              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-700 outline-none md:max-w-[12rem]"
                            >
                              <option value="daily">每天</option>
                              <option value="weekly">每周</option>
                              <option value="custom">自定义</option>
                            </select>
                          </label>
                        </div>

                        {draftPayload.time_period === "custom" ? (
                          <label className="block">
                            <span className="mb-1.5 block text-sm font-medium text-slate-700">Cron 表达式</span>
                            <input
                              value={draftPayload.custom_schedule || ""}
                              onChange={(event) => handleDraftCustomScheduleChange(event.target.value)}
                              placeholder="0 9 * * *"
                              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-700 outline-none"
                            />
                          </label>
                        ) : null}

                        <div>
                          <div className="mb-2 text-sm font-medium text-slate-700">信息源</div>
                          <div className="max-h-52 space-y-2 overflow-y-auto rounded-xl border border-slate-200/80 p-2">
                            {sourceGroups.length === 0 ? (
                              <div className="px-2 py-2 text-xs text-slate-500">暂未配置任何信息源。</div>
                            ) : (
                              sourceGroups.map(([category, groupedSources]) => (
                                <div key={category} className="space-y-1">
                                  <button
                                    type="button"
                                    onClick={() => handleToggleSourceCategory(category)}
                                    aria-expanded={expandedSourceCategories[category] ?? true}
                                    className="flex w-full items-center justify-between rounded-lg px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500 transition hover:bg-slate-100/80"
                                  >
                                    <span>{`分类: ${category}`}</span>
                                    <ChevronDown
                                      className={`h-3.5 w-3.5 transition-transform ${
                                        !(expandedSourceCategories[category] ?? true) ? "-rotate-90" : ""
                                      }`}
                                    />
                                  </button>
                                  {(expandedSourceCategories[category] ?? true) &&
                                    groupedSources.map((source) => {
                                      const isSelected = draftPayload.source_ids.includes(source.id);
                                      const sourceConfig = (source.config as Record<string, unknown>) ?? {};
                                      const isArxivApi = source.collect_method === "rss" && Boolean(sourceConfig.arxiv_api);
                                      const isAcademicApi =
                                        source.category === "academic" &&
                                        (isArxivApi || ["openalex", "europe_pmc", "pubmed", "rss"].includes(source.collect_method));
                                      const isTwitterSnaplytics = source.collect_method === "twitter_snaplytics";
                                      const isConfigurableReddit = isConfigurableRedditSource(source);
                                      const availableUsernames = Array.isArray(sourceConfig.usernames)
                                        ? sourceConfig.usernames.filter(
                                            (item): item is string => typeof item === "string" && item.trim().length > 0
                                          )
                                        : [];
                                      const availableSubreddits = Array.isArray(sourceConfig.subreddits)
                                        ? normalizeRedditSubreddits(
                                            sourceConfig.subreddits.filter(
                                              (item): item is string => typeof item === "string" && item.trim().length > 0
                                            )
                                          )
                                        : [];
                                      const selectedUsernames = Array.isArray(draftPayload.source_overrides?.[source.id]?.usernames)
                                        ? dedupeStrings(draftPayload.source_overrides?.[source.id]?.usernames || [])
                                        : availableUsernames;
                                      const selectedSubreddits = Array.isArray(draftPayload.source_overrides?.[source.id]?.subreddits)
                                        ? normalizeRedditSubreddits(draftPayload.source_overrides?.[source.id]?.subreddits || [])
                                        : availableSubreddits;
                                      const keywordInputValue =
                                        draftSourceKeywordInputs[source.id] ??
                                        (Array.isArray(draftPayload.source_overrides?.[source.id]?.keywords)
                                          ? (draftPayload.source_overrides?.[source.id]?.keywords || []).join(", ")
                                          : "");
                                      const maxResultsValue =
                                        typeof draftPayload.source_overrides?.[source.id]?.max_results === "number"
                                          ? draftPayload.source_overrides?.[source.id]?.max_results
                                          : "";
                                      return (
                                        <div key={source.id} className="rounded-lg px-2 py-1.5 transition hover:bg-slate-50">
                                          <label className="flex items-center gap-2 text-sm text-slate-700">
                                            <input
                                              type="checkbox"
                                              aria-label={source.name}
                                              checked={isSelected}
                                              onChange={() => handleDraftSourceToggle(source.id)}
                                              className="h-4 w-4"
                                            />
                                            <span>{source.name}</span>
                                          </label>
                                          {isSelected && isTwitterSnaplytics && availableUsernames.length > 0 ? (
                                            <div className="ml-6 mt-2 space-y-2">
                                              <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
                                                账号列表
                                              </div>
                                              <div className="grid gap-2 md:grid-cols-2">
                                                {availableUsernames.map((username) => {
                                                  const checked = selectedUsernames.includes(username);
                                                  return (
                                                    <label
                                                      key={username}
                                                      className="flex items-center gap-2 text-xs text-slate-600"
                                                    >
                                                      <input
                                                        type="checkbox"
                                                        aria-label={`X 账号 ${username}`}
                                                        checked={checked}
                                                        onChange={(event) => {
                                                          const nextUsernames = event.target.checked
                                                            ? [...selectedUsernames, username]
                                                            : selectedUsernames.filter((item) => item !== username);
                                                          handleDraftSourceUsernamesChange(source.id, nextUsernames);
                                                        }}
                                                        className="h-3.5 w-3.5"
                                                      />
                                                      <span>{username}</span>
                                                    </label>
                                                  );
                                                })}
                                              </div>
                                            </div>
                                          ) : null}
                                          {isSelected && isConfigurableReddit && availableSubreddits.length > 0 ? (
                                            <div className="ml-6 mt-2 space-y-2">
                                              <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
                                                版块列表
                                              </div>
                                              <div className="grid gap-2 md:grid-cols-2">
                                                {availableSubreddits.map((subreddit) => {
                                                  const checked = selectedSubreddits.includes(subreddit);
                                                  return (
                                                    <label
                                                      key={subreddit}
                                                      className="flex items-center gap-2 text-xs text-slate-600"
                                                    >
                                                      <input
                                                        type="checkbox"
                                                        aria-label={`Reddit 版块 ${subreddit}`}
                                                        checked={checked}
                                                        onChange={(event) => {
                                                          const nextSubreddits = event.target.checked
                                                            ? [...selectedSubreddits, subreddit]
                                                            : selectedSubreddits.filter((item) => item !== subreddit);
                                                          handleDraftSourceSubredditsChange(source.id, nextSubreddits);
                                                        }}
                                                        className="h-3.5 w-3.5"
                                                      />
                                                      <span>{subreddit}</span>
                                                    </label>
                                                  );
                                                })}
                                              </div>
                                            </div>
                                          ) : null}
                                          {isSelected && isAcademicApi ? (
                                            <div className="ml-6 mt-2 space-y-2">
                                              <div className="flex items-center gap-2">
                                                <span className="text-xs text-slate-500">学术关键词</span>
                                                <input
                                                  type="text"
                                                  aria-label={`学术关键词 ${source.name}`}
                                                  value={keywordInputValue}
                                                  onChange={(event) =>
                                                    handleDraftSourceKeywordsInputChange(source.id, event.target.value)
                                                  }
                                                  placeholder="reasoning, agent, multimodal"
                                                  className="h-8 flex-1 rounded-md border border-slate-200 bg-slate-50 px-2 text-xs text-slate-700 outline-none"
                                                />
                                              </div>
                                              <div className="flex items-center gap-2">
                                                <span className="text-xs text-slate-500">最大结果数</span>
                                                <input
                                                  type="number"
                                                  min={1}
                                                  max={200}
                                                  aria-label={`最大结果数 ${source.name}`}
                                                  value={maxResultsValue}
                                                  onChange={(event) =>
                                                    handleDraftSourceMaxResultsChange(source.id, event.target.value)
                                                  }
                                                  placeholder="默认"
                                                  className="h-8 w-24 rounded-md border border-slate-200 bg-slate-50 px-2 text-xs text-slate-700 outline-none"
                                                />
                                              </div>
                                            </div>
                                          ) : null}
                                        </div>
                                      );
                                    })}
                                </div>
                              ))
                            )}
                          </div>
                        </div>

                        <div>
                          <div className="mb-2 text-sm font-medium text-slate-700">输出位置</div>
                          <div className="space-y-2">
                            {enabledDestinations.length === 0 ? (
                              <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-500">
                                当前没有任何激活的输出流配置，请前往“输出配置”页配置。
                              </div>
                            ) : (
                              enabledDestinations.map((destination) => {
                                const selected = (draftPayload.destination_instance_ids || []).includes(destination.id);
                                return (
                                  <label
                                    key={destination.id}
                                    className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm"
                                  >
                                    <input
                                      type="checkbox"
                                      aria-label={destination.name}
                                      checked={selected}
                                      onChange={() => handleDraftDestinationToggle(destination.id)}
                                      className="h-4 w-4"
                                    />
                                    <span className="font-medium text-slate-700">{destination.name}</span>
                                    <span className="ml-auto text-xs capitalize text-slate-500">{destination.type}</span>
                                  </label>
                                );
                              })
                            )}
                          </div>
                        </div>

                        {saveDraftError ? <div className="text-sm text-red-500">保存失败：{saveDraftError}</div> : null}
                        {saveDraftSuccess ? <div className="text-sm text-emerald-700">{saveDraftSuccess}</div> : null}

                        <div className="flex items-center justify-between gap-3 border-t border-slate-200 pt-3.5">
                          <div className="text-xs text-slate-500">保存后将直接按当前配置创建任务。</div>
                          <button
                            type="button"
                            onClick={() => void handleSaveDraft()}
                            disabled={savingDraft || !draftPayload.name.trim() || !draftHasSelectedSources}
                            className="rounded-full bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {savingDraft ? "保存中..." : "保存任务"}
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            </section>

            <div className="fixed bottom-4 left-1/2 z-40 w-[min(52rem,calc(100vw-2rem))] -translate-x-1/2 md:left-[calc(50%+8rem)] md:w-[min(48rem,calc(100vw-20rem))]">
              <div className="mx-auto w-full rounded-[2rem] border border-slate-200/80 bg-white/95 p-4 shadow-[0_28px_70px_rgba(103,134,166,0.16)] backdrop-blur-xl">
                <div className="flex flex-col">
                  <textarea
                    value={replyMessage}
                    onChange={(event) => setReplyMessage(event.target.value)}
                    onKeyDown={handleReplyKeyDown}
                    placeholder="Continue refining this monitor…"
                    className="min-h-20 flex-1 resize-none rounded-[1.4rem] border-0 bg-transparent px-3 py-3 text-base text-slate-700 outline-none placeholder:text-slate-400"
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function normalizeMonitorPayload(payload: MonitorCreate): MonitorCreate {
  return {
    ...payload,
    report_type: payload.report_type || "daily",
    source_overrides: payload.source_overrides || {},
    destination_ids: payload.destination_ids || [],
    destination_instance_ids: payload.destination_instance_ids || [],
    window_hours: payload.window_hours || 24,
    custom_schedule: payload.custom_schedule ?? "0 9 * * *",
    enabled: payload.enabled ?? true,
  };
}

function deriveWindowHours(reportType: NonNullable<MonitorCreate["report_type"]>): number {
  return reportType === "weekly" ? 24 * 7 : 24;
}

function dedupeStrings(values: string[]): string[] {
  const normalized: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const cleaned = value.trim();
    if (!cleaned) continue;
    const key = cleaned.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    normalized.push(cleaned);
  }
  return normalized;
}

function upsertDraftSourceOverride(
  overrides: Record<string, MonitorSourceOverride>,
  sourceId: string,
  nextOverride: MonitorSourceOverride
): Record<string, MonitorSourceOverride> {
  const cleaned = cleanDraftSourceOverride(nextOverride);
  const nextOverrides = { ...overrides };
  if (Object.keys(cleaned).length === 0) {
    delete nextOverrides[sourceId];
  } else {
    nextOverrides[sourceId] = cleaned;
  }
  return nextOverrides;
}

function cleanDraftSourceOverride(override: MonitorSourceOverride): MonitorSourceOverride {
  const cleaned: MonitorSourceOverride = {};
  if (typeof override.max_items === "number") {
    cleaned.max_items = override.max_items;
  }
  if (typeof override.limit === "number") {
    cleaned.limit = override.limit;
  }
  if (typeof override.max_results === "number") {
    cleaned.max_results = override.max_results;
  }
  if (Array.isArray(override.keywords)) {
    const keywords = dedupeStrings(override.keywords);
    if (keywords.length > 0) {
      cleaned.keywords = keywords;
    }
  }
  if (Array.isArray(override.expanded_keywords)) {
    const expandedKeywords = dedupeStrings(override.expanded_keywords);
    if (expandedKeywords.length > 0) {
      cleaned.expanded_keywords = expandedKeywords;
    }
  }
  if (Array.isArray(override.usernames)) {
    const usernames = dedupeStrings(override.usernames);
    if (usernames.length > 0) {
      cleaned.usernames = usernames;
    }
  }
  if (Array.isArray(override.subreddits)) {
    const subreddits = normalizeRedditSubreddits(override.subreddits);
    if (subreddits.length > 0) {
      cleaned.subreddits = subreddits;
    }
  }
  return cleaned;
}

function groupSourcesByCategory(sources: Source[]): Array<[string, Source[]]> {
  const groups = new Map<string, Source[]>();
  for (const source of sources) {
    const category = source.category || "uncategorized";
    const current = groups.get(category) || [];
    current.push(source);
    groups.set(category, current);
  }
  return Array.from(groups.entries()).map(([category, items]) => [
    category,
    [...items].sort((left, right) => left.name.localeCompare(right.name)),
  ]);
}

function extractDraftSourceOptions(response: MonitorAgentDraftResponse): DraftSourceOption[] {
  const selectedSourceIds = new Set(response.monitor_payload.source_ids);
  return response.draft.sections
    .flatMap((section) => section.items)
    .filter((item) => item.type === "source" && item.source_id)
    .map((item) => ({
      id: item.source_id as string,
      label: item.label,
      selected: selectedSourceIds.has(item.source_id as string),
      reason: item.reason,
    }));
}

function extractDraftSourceKeywordInputs(payload: MonitorCreate): Record<string, string> {
  const entries = Object.entries(payload.source_overrides || {});
  return Object.fromEntries(
    entries
      .filter(([, override]) => Array.isArray(override.keywords) && override.keywords.length > 0)
      .map(([sourceId, override]) => [sourceId, override.keywords!.join(", ")])
  );
}

function parseKeywordInput(value: string): string[] {
  return dedupeStrings(
    value
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
  );
}

function upsertProgressStep(
  steps: MonitorAgentStatusStreamEvent[],
  nextStep: MonitorAgentStatusStreamEvent
): MonitorAgentStatusStreamEvent[] {
  const filtered = steps.filter((step) => step.key !== nextStep.key);
  return [...filtered, nextStep];
}

function AssistantLoader() {
  return (
    <div
      data-testid="agent-loader"
      aria-label="Assistant is responding"
      className="inline-flex items-center gap-2 rounded-full border border-slate-200/80 bg-white/88 px-3 py-2 shadow-[0_10px_24px_rgba(107,127,149,0.10)]"
    >
      <span className="h-2.5 w-2.5 rounded-full bg-slate-500/80 animate-[bounce_0.95s_ease-in-out_infinite]" />
      <span
        className="h-2.5 w-2.5 rounded-full bg-slate-300 animate-[bounce_0.95s_ease-in-out_infinite]"
        style={{ animationDelay: "0.18s" }}
      />
    </div>
  );
}

function DraftCardLoader() {
  return (
    <div data-testid="draft-card-loader" className="max-w-[46rem]">
      <div className="rounded-[1.5rem] border border-emerald-100/90 bg-white/92 p-5 shadow-[0_18px_44px_rgba(92,136,112,0.06)]">
        <div className="flex items-center justify-between gap-4 border-b border-slate-200/70 pb-4">
          <div className="space-y-2">
            <div className="h-3 w-28 rounded-full bg-emerald-100/90" />
            <div className="h-8 w-64 rounded-full bg-slate-200/90" />
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200/80 bg-slate-50 px-3 py-2">
            <span className="h-2.5 w-2.5 rounded-full bg-slate-500/80 animate-[bounce_0.95s_ease-in-out_infinite]" />
            <span
              className="h-2.5 w-2.5 rounded-full bg-slate-300 animate-[bounce_0.95s_ease-in-out_infinite]"
              style={{ animationDelay: "0.18s" }}
            />
          </div>
        </div>
        <div className="mt-4 grid gap-3">
          <div className="h-11 rounded-xl bg-slate-100/90" />
          <div className="grid gap-3 md:grid-cols-2">
            <div className="h-11 rounded-xl bg-slate-100/90" />
            <div className="h-11 rounded-xl bg-slate-100/90" />
          </div>
          <div className="h-20 rounded-xl border border-dashed border-slate-200 bg-slate-50/90" />
        </div>
      </div>
    </div>
  );
}

function normalizeRedditSubreddits(values: string[]): string[] {
  const normalized: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const cleaned = normalizeRedditSubreddit(value);
    if (!cleaned) continue;
    const key = cleaned.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    normalized.push(cleaned);
  }
  return normalized;
}

function normalizeRedditSubreddit(value: string): string {
  const raw = value.trim();
  if (!raw) return "";
  let normalized = raw.toLowerCase().startsWith("r/") ? raw.slice(2) : raw;
  normalized = normalized.trim().replace(/^\/+|\/+$/g, "");
  if (!normalized || /[\s/]/.test(normalized)) return "";
  return normalized;
}

function isConfigurableRedditSource(source: Source): boolean {
  if (source.collect_method !== "rss") return false;
  const config = source.config;
  if (!config || typeof config !== "object" || Array.isArray(config)) {
    return source.name.trim().toLowerCase() === "reddit";
  }
  return Array.isArray((config as Record<string, unknown>).subreddits) || source.name.trim().toLowerCase() === "reddit";
}
