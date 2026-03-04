"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Play, Plus, Trash2, Activity, Clock, Server, ChevronDown, ChevronRight, History } from "lucide-react";
import {
  cancelMonitorRun,
  createMonitor,
  deleteMonitor,
  getMonitors,
  getSources,
  runMonitor,
  updateMonitor,
  getDestinations,
  getMonitorLogs,
  getMonitorRunEvents,
  getMonitorRuns,
  type Monitor,
  type Source,
  type CollectTask,
  type MonitorRunSummary,
  type TaskEvent,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { Destination } from "@/lib/api";

export default function MonitorsPage() {
  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingMonitorId, setEditingMonitorId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [timePeriod, setTimePeriod] = useState<"daily" | "weekly" | "custom">("daily");
  const [reportType, setReportType] = useState<"daily" | "weekly" | "research" | "">("");
  const [customSchedule, setCustomSchedule] = useState("");
  const [windowHours, setWindowHours] = useState("24");
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [sourceOverrides, setSourceOverrides] = useState<
    Record<string, { max_items?: number; limit?: number; max_results?: number; keywords?: string[]; usernames?: string[] }>
  >({});
  const [expandedSourceCategories, setExpandedSourceCategories] = useState<Record<string, boolean>>({});
  const [selectedDestinations, setSelectedDestinations] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  // Test Run modal state
  const [isTestModalOpen, setIsTestModalOpen] = useState(false);
  const [testMonitor, setTestMonitor] = useState<Monitor | null>(null);
  const [testWindowPreset, setTestWindowPreset] = useState<"24h" | "72h" | "168h" | "custom">("24h");
  const [testWindowCustomValue, setTestWindowCustomValue] = useState("24");
  const [testWindowCustomUnit, setTestWindowCustomUnit] = useState<"hours" | "days">("hours");

  // Dedicated Test Console state
  const [isTestConsoleOpen, setIsTestConsoleOpen] = useState(false);
  const [testConsoleMonitor, setTestConsoleMonitor] = useState<Monitor | null>(null);
  const [testRunId, setTestRunId] = useState<string | null>(null);
  const [testRun, setTestRun] = useState<MonitorRunSummary | null>(null);
  const [testRunEvents, setTestRunEvents] = useState<TaskEvent[]>([]);
  const [testLoading, setTestLoading] = useState(false);
  const [testAutoRefresh, setTestAutoRefresh] = useState(false);
  const [testLastProgressAt, setTestLastProgressAt] = useState<number | null>(null);
  const [testNow, setTestNow] = useState<number>(Date.now());
  const testFingerprintRef = useRef<string>("");

  // Logs modal state
  const [isLogsModalOpen, setIsLogsModalOpen] = useState(false);
  const [logsMonitor, setLogsMonitor] = useState<Monitor | null>(null);
  const [monitorLogs, setMonitorLogs] = useState<CollectTask[]>([]);
  const [monitorRuns, setMonitorRuns] = useState<MonitorRunSummary[]>([]);
  const [runEvents, setRunEvents] = useState<TaskEvent[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [logsFocusRunId, setLogsFocusRunId] = useState<string | null>(null);

  const sourceMap = useMemo(() => {
    const map = new Map<string, Source>();
    sources.forEach((source) => map.set(source.id, source));
    return map;
  }, [sources]);

  const sourceGroups = useMemo(() => {
    const groups = new Map<string, Source[]>();
    sources.forEach((source) => {
      const category = source.category?.trim() || "uncategorized";
      const existing = groups.get(category) ?? [];
      existing.push(source);
      groups.set(category, existing);
    });
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [sources]);

  const focusedRun = useMemo(() => {
    if (monitorRuns.length === 0) return null;
    if (logsFocusRunId) {
      return monitorRuns.find((item) => item.run_id === logsFocusRunId) ?? monitorRuns[0];
    }
    return monitorRuns[0];
  }, [monitorRuns, logsFocusRunId]);

  const focusedTrace = useMemo(() => {
    return runEvents.filter((event) => Boolean(event));
  }, [runEvents]);
  const testOverallProgress = useMemo(() => {
    if (!testRun || testRun.source_total <= 0) return 0;
    return Math.min(100, Math.round((testRun.source_done / testRun.source_total) * 100));
  }, [testRun]);
  const testStageProgress = useMemo(() => {
    const totalSources = testRun?.source_total ?? 0;
    if (totalSources <= 0) return [] as Array<{ stage: string; done: number; total: number }>;

    const stages = ["collect", "window_filter", "process", "persist"];
    const result: Array<{ stage: string; done: number; total: number }> = [];
    for (const stage of stages) {
      const doneIds = new Set<string>();
      for (const event of testRunEvents) {
        if (event.stage !== stage || !event.source_id) continue;
        if (
          event.event_type.endsWith("_success") ||
          event.event_type.endsWith("_failed") ||
          event.event_type.endsWith("_completed") ||
          event.event_type === "source_completed" ||
          event.event_type === "source_failed" ||
          event.event_type === "window_filter_completed"
        ) {
          doneIds.add(event.source_id);
        }
      }
      result.push({ stage, done: doneIds.size, total: totalSources });
    }
    return result;
  }, [testRun, testRunEvents]);
  const testSecondsSinceProgress = testLastProgressAt ? Math.floor((testNow - testLastProgressAt) / 1000) : null;
  const isTestStalled = Boolean(
    testAutoRefresh &&
    testRun?.status === "running" &&
    testLastProgressAt &&
    testNow - testLastProgressAt > 60_000
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [monitorData, sourceData, destData] = await Promise.all([getMonitors(), getSources(), getDestinations()]);
      setMonitors(monitorData);
      setSources(sourceData);

      // We expect the mock API to return the new Notion & Obsidian objects
      setDestinations(destData || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const resetForm = () => {
    setName("");
    setTimePeriod("daily");
    setReportType("");
    setCustomSchedule("");
    setWindowHours("24");
    setSelectedSources([]);
    setSourceOverrides({});
    setExpandedSourceCategories(
      Object.fromEntries(sourceGroups.map(([category]) => [category, true])) as Record<string, boolean>
    );
    setSelectedDestinations([]);
  };

  const openCreateModal = () => {
    setEditingMonitorId(null);
    resetForm();
    setIsModalOpen(true);
  };

  const openEditModal = (monitor: Monitor) => {
    setEditingMonitorId(monitor.id);
    setName(monitor.name);
    setTimePeriod(monitor.time_period);
    setReportType(monitor.time_period === "custom" ? monitor.report_type : "");
    setCustomSchedule(monitor.custom_schedule ?? "");
    setWindowHours(String(monitor.window_hours || 24));
    setSelectedSources(monitor.source_ids);
    setSourceOverrides(monitor.source_overrides ?? {});
    setExpandedSourceCategories(
      Object.fromEntries(sourceGroups.map(([category]) => [category, true])) as Record<string, boolean>
    );
    setSelectedDestinations(monitor.destination_ids);
    setIsModalOpen(true);
  };

  const _applyTestWindowFromHours = (hours: number) => {
    const normalized = Math.max(1, Math.min(168, Math.floor(hours || 24)));
    if (normalized === 24) {
      setTestWindowPreset("24h");
      setTestWindowCustomValue("24");
      setTestWindowCustomUnit("hours");
      return;
    }
    if (normalized === 72) {
      setTestWindowPreset("72h");
      setTestWindowCustomValue("72");
      setTestWindowCustomUnit("hours");
      return;
    }
    if (normalized === 168) {
      setTestWindowPreset("168h");
      setTestWindowCustomValue("7");
      setTestWindowCustomUnit("days");
      return;
    }
    setTestWindowPreset("custom");
    setTestWindowCustomValue(String(normalized));
    setTestWindowCustomUnit("hours");
  };

  const openTestConfigModal = (monitor: Monitor) => {
    setTestMonitor(monitor);
    _applyTestWindowFromHours(Number(monitor.window_hours || 24));
    setIsTestModalOpen(true);
  };

  const closeLogsModal = () => {
    setIsLogsModalOpen(false);
    setLogsFocusRunId(null);
  };

  const fetchLogs = useCallback(async (monitorId: string) => {
    const logs = await getMonitorLogs(monitorId);
    setMonitorLogs(logs);
    return logs;
  }, []);

  const fetchRunsAndEvents = useCallback(
    async (monitorId: string, focusRunId: string | null) => {
      const runs = await getMonitorRuns(monitorId, 40);
      setMonitorRuns(runs);
      const active = (focusRunId ? runs.find((item) => item.run_id === focusRunId) : undefined) ?? runs[0];
      if (!active) {
        setRunEvents([]);
        return { runs, events: [] as TaskEvent[] };
      }
      const events = await getMonitorRunEvents(monitorId, active.run_id);
      setRunEvents(events);
      return { runs, events };
    },
    []
  );

  const refreshTestConsole = useCallback(
    async (monitorId: string, targetRunId: string) => {
      const runs = await getMonitorRuns(monitorId, 40);
      const active = runs.find((item) => item.run_id === targetRunId) ?? null;
      setTestRun(active);
      if (!active) {
        setTestRunEvents([]);
        return;
      }
      const events = await getMonitorRunEvents(monitorId, active.run_id);
      setTestRunEvents(events);

      const fingerprint = JSON.stringify({
        status: active.status,
        error: active.error_message,
        articles: active.articles_count,
        source_done: active.source_done,
        source_total: active.source_total,
        events: events.map((item) => [item.id, item.event_type, item.level]),
      });
      if (fingerprint !== testFingerprintRef.current) {
        testFingerprintRef.current = fingerprint;
        setTestLastProgressAt(Date.now());
      }

      if (!["pending", "running", "cancelling"].includes(active.status)) {
        setTestAutoRefresh(false);
      }
    },
    []
  );

  const openLogsModal = async (monitor: Monitor, focusRunId: string | null = null) => {
    setLogsMonitor(monitor);
    setMonitorLogs([]);
    setMonitorRuns([]);
    setRunEvents([]);
    setLogsFocusRunId(focusRunId);
    setLoadingLogs(true);
    setIsLogsModalOpen(true);
    try {
      const [logs] = await Promise.all([fetchLogs(monitor.id), fetchRunsAndEvents(monitor.id, focusRunId)]);
      void logs;
    } catch (err) {
      console.error("Failed to fetch logs", err);
    } finally {
      setLoadingLogs(false);
    }
  };

  const closeTestConsole = () => {
    setIsTestConsoleOpen(false);
    setTestConsoleMonitor(null);
    setTestRunId(null);
    setTestRun(null);
    setTestRunEvents([]);
    setTestLoading(false);
    setTestAutoRefresh(false);
    setTestLastProgressAt(null);
    testFingerprintRef.current = "";
  };

  const openTestConsoleForRun = async (monitor: Monitor, runId: string) => {
    setIsTestModalOpen(false);
    setIsLogsModalOpen(false);
    setTestConsoleMonitor(monitor);
    setTestRunId(runId);
    setTestRun(null);
    setTestRunEvents([]);
    setTestLoading(true);
    setTestAutoRefresh(true);
    setTestLastProgressAt(Date.now());
    testFingerprintRef.current = "";
    setIsTestConsoleOpen(true);
    try {
      await refreshTestConsole(monitor.id, runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open test console");
      setTestAutoRefresh(false);
    } finally {
      setTestLoading(false);
    }
  };

  const _resolveTestWindowHours = () => {
    if (testWindowPreset === "24h") return 24;
    if (testWindowPreset === "72h") return 72;
    if (testWindowPreset === "168h") return 168;

    const parsed = Number(testWindowCustomValue);
    if (!Number.isFinite(parsed)) return null;
    const normalizedValue = Math.max(1, Math.floor(parsed));
    const hours = testWindowCustomUnit === "days" ? normalizedValue * 24 : normalizedValue;
    return Math.max(1, Math.min(168, hours));
  };

  const handleStartTestRun = async () => {
    if (!testMonitor) return;
    const hours = _resolveTestWindowHours();
    if (!hours) {
      setError("Invalid test window. Please enter a valid value.");
      return;
    }
    setIsTestModalOpen(false);
    setTestConsoleMonitor(testMonitor);
    setTestRunId(null);
    setTestRun(null);
    setTestRunEvents([]);
    setTestLoading(true);
    setTestAutoRefresh(true);
    setTestLastProgressAt(Date.now());
    testFingerprintRef.current = "";
    setIsTestConsoleOpen(true);

    try {
      const runResponse = await runMonitor(testMonitor.id, {
        window_hours: hours,
        trigger_type: "test",
      });
      setTestRunId(runResponse.run_id);
      await refreshTestConsole(testMonitor.id, runResponse.run_id);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test run failed");
      setTestAutoRefresh(false);
    } finally {
      setTestLoading(false);
    }
  };

  useEffect(() => {
    if (!isTestConsoleOpen || !testConsoleMonitor || !testRunId || !testAutoRefresh) return;
    let cancelled = false;

    const poll = async () => {
      try {
        await refreshTestConsole(testConsoleMonitor.id, testRunId);
      } catch (err) {
        if (!cancelled) {
          console.error("Failed to refresh test console", err);
        }
      }
    };

    const timer = window.setInterval(() => {
      void poll();
    }, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [isTestConsoleOpen, testConsoleMonitor, testRunId, testAutoRefresh, refreshTestConsole]);

  useEffect(() => {
    if (!isTestConsoleOpen || !testAutoRefresh) return;
    const timer = window.setInterval(() => {
      setTestNow(Date.now());
    }, 1000);
    return () => {
      window.clearInterval(timer);
    };
  }, [isTestConsoleOpen, testAutoRefresh]);

  useEffect(() => {
    if (!isLogsModalOpen || !logsMonitor) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const [logs] = await Promise.all([
          fetchLogs(logsMonitor.id),
          fetchRunsAndEvents(logsMonitor.id, logsFocusRunId),
        ]);
        if (cancelled) return;
        void logs;
      } catch (err) {
        if (!cancelled) {
          console.error("Failed to refresh logs", err);
        }
      }
    };
    const timer = window.setInterval(() => {
      void poll();
    }, 4000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [isLogsModalOpen, logsMonitor, logsFocusRunId, fetchLogs, fetchRunsAndEvents]);

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingMonitorId(null);
    resetForm();
  };

  const handleToggleSourceCategory = (category: string) => {
    setExpandedSourceCategories((prev) => ({
      ...prev,
      [category]: !(prev[category] ?? true),
    }));
  };

  const handleSubmit = async () => {
    const effectiveReportType =
      timePeriod === "daily" ? "daily" : timePeriod === "weekly" ? "weekly" : reportType;
    if (!name || selectedSources.length === 0 || !effectiveReportType) return;
    setSubmitting(true);
    setError(null);
    const cleanedSourceOverrides = Object.fromEntries(
      Object.entries(sourceOverrides)
        .filter(([sourceId]) => selectedSources.includes(sourceId))
        .map(([sourceId, override]) => {
          const cleaned: { max_items?: number; limit?: number; max_results?: number; keywords?: string[]; usernames?: string[] } = {};

          const maxItems = override?.max_items;
          if (typeof maxItems === "number" && Number.isFinite(maxItems) && maxItems > 0) {
            cleaned.max_items = Math.max(1, Math.min(200, Math.floor(maxItems)));
          }

          const limit = override?.limit;
          if (typeof limit === "number" && Number.isFinite(limit) && limit > 0) {
            cleaned.limit = Math.max(1, Math.min(200, Math.floor(limit)));
          }

          const maxResults = override?.max_results;
          if (typeof maxResults === "number" && Number.isFinite(maxResults) && maxResults > 0) {
            cleaned.max_results = Math.max(1, Math.min(200, Math.floor(maxResults)));
          }

          const keywords = Array.isArray(override?.keywords)
            ? override.keywords
              .map((item) => String(item).trim())
              .filter((item) => item.length > 0)
            : [];
          if (keywords.length > 0) {
            cleaned.keywords = Array.from(new Set(keywords)).slice(0, 20);
          }

          const usernames = Array.isArray(override?.usernames)
            ? override.usernames
              .map((item) => String(item).trim())
              .filter((item) => item.length > 0)
            : null;
          if (usernames !== null) {
            // Null means we didn't touch it (so we want backend to have default), 
            // but an array (even empty) means user set specific sub-accounts.
            cleaned.usernames = Array.from(new Set(usernames));
          }

          return [sourceId, cleaned];
        })
        .filter(([, override]) => Object.keys(override).length > 0)
    ) as Record<string, { max_items?: number; limit?: number; max_results?: number; keywords?: string[]; usernames?: string[] }>;
    const payload = {
      name,
      time_period: timePeriod,
      report_type: effectiveReportType,
      source_ids: selectedSources,
      source_overrides: cleanedSourceOverrides,
      destination_ids: selectedDestinations,
      window_hours: (() => {
        const parsed = Number(windowHours);
        if (!Number.isFinite(parsed)) return 24;
        return Math.max(1, Math.min(168, Math.floor(parsed)));
      })(),
      custom_schedule: timePeriod === "custom" ? customSchedule.trim() || null : null,
    };
    try {
      if (editingMonitorId) {
        const target = monitors.find((item) => item.id === editingMonitorId);
        await updateMonitor(editingMonitorId, {
          ...payload,
          enabled: target?.enabled ?? true,
        });
      } else {
        await createMonitor({
          ...payload,
          enabled: true,
        });
      }
      closeModal();
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : editingMonitorId ? "Update monitor failed" : "Create monitor failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRunNow = async (
    monitor: Monitor,
    options?: { windowHoursOverride?: number },
  ) => {
    try {
      const windowHoursOverride = options?.windowHoursOverride;
      const payload =
        typeof windowHoursOverride === "number" && Number.isFinite(windowHoursOverride)
          ? { window_hours: Math.max(1, Math.min(168, Math.floor(windowHoursOverride))), trigger_type: "manual" as const }
          : undefined;
      await runMonitor(monitor.id, payload);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Run failed");
    }
  };

  const handleTerminateTestRun = async () => {
    if (!testConsoleMonitor || !testRunId || !testRun) return;
    if (!["pending", "running", "cancelling"].includes(testRun.status)) return;
    try {
      await cancelMonitorRun(testConsoleMonitor.id, testRunId);
      await refreshTestConsole(testConsoleMonitor.id, testRunId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Terminate test run failed");
    }
  };

  const handleToggle = async (monitor: Monitor) => {
    try {
      await updateMonitor(monitor.id, { enabled: !monitor.enabled });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  };

  const handleDelete = async (monitorId: string) => {
    try {
      await deleteMonitor(monitorId);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 py-8 md:py-12">
      <header className="mb-10 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-2">Monitors</h1>
          <p className="text-muted-foreground text-sm max-w-2xl">
            Configure automated research tasks and run them on demand.
          </p>
        </div>
        <button
          onClick={openCreateModal}
          className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors bg-foreground text-background shadow hover:bg-foreground/90 h-9 px-4 py-2"
        >
          <Plus className="w-4 h-4 mr-2" />
          Create Monitor
        </button>
      </header>

      {loading && <div className="py-10 text-sm text-muted-foreground">Loading monitors...</div>}
      {error && <div className="py-4 text-sm text-red-500">{error}</div>}

      {!loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {monitors.map((monitor) => (
            <Card
              key={monitor.id}
              onClick={() => openEditModal(monitor)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  openEditModal(monitor);
                }
              }}
              role="button"
              tabIndex={0}
              className={cn(
                "border-border/40 hover:border-border/80 transition-all duration-300 shadow-sm hover:shadow-lg flex flex-col cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                !monitor.enabled && "opacity-70"
              )}
            >
              <CardHeader className="pb-3">
                <CardTitle className="text-lg font-semibold leading-snug">{monitor.name}</CardTitle>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <Badge variant="secondary" className="capitalize bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 border-none">
                    {monitor.time_period}
                  </Badge>
                  {monitor.time_period !== monitor.report_type && (
                    <Badge variant="secondary" className="capitalize bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 border-none">
                      {monitor.report_type} report
                    </Badge>
                  )}
                  <Badge variant="secondary" className={monitor.enabled ? "bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400" : "bg-muted text-muted-foreground"}>
                    {monitor.enabled ? "active" : "paused"}
                  </Badge>
                </div>
              </CardHeader>

              <CardContent className="pb-4 flex-1 text-sm text-muted-foreground space-y-2">
                <div className="flex items-center space-x-2">
                  <Server className="w-4 h-4" />
                  <span>{monitor.source_ids.length} sources</span>
                </div>
                <div className="flex items-center space-x-2">
                  <Clock className="w-4 h-4" />
                  <span>{monitor.last_run ? new Date(monitor.last_run).toLocaleString() : "Never run"}</span>
                </div>
                <div className="text-xs text-muted-foreground/80">
                  {monitor.source_ids.map((sourceId) => sourceMap.get(sourceId)?.name ?? sourceId).join(", ")}
                </div>
              </CardContent>

              <CardFooter className="pt-0 justify-between items-center border-t border-border/40 pb-3 pt-3 mt-auto flex-wrap gap-y-2">
                <button
                  onClick={(event) => {
                    event.stopPropagation();
                    void handleToggle(monitor);
                  }}
                  className={cn(
                    "text-xs px-3 py-1.5 rounded-md transition-colors cursor-pointer",
                    monitor.enabled
                      ? "bg-yellow-50 hover:bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:hover:bg-yellow-900/40 dark:text-yellow-300"
                      : "bg-green-50 hover:bg-green-100 text-green-700 dark:bg-green-900/30 dark:hover:bg-green-900/40 dark:text-green-300"
                  )}
                >
                  {monitor.enabled ? "Pause" : "Resume"}
                </button>
                <div className="flex flex-wrap items-center justify-end gap-2">
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      void openLogsModal(monitor);
                    }}
                    className="text-xs font-medium text-foreground bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 px-3 py-1.5 rounded-md transition-colors flex items-center cursor-pointer"
                  >
                    <History className="w-3.5 h-3.5 mr-1.5" />
                    Logs
                  </button>
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      void handleRunNow(monitor);
                    }}
                    disabled={!monitor.enabled}
                    className="text-xs font-medium text-foreground bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1.5 rounded-md transition-colors flex items-center cursor-pointer disabled:hover:bg-neutral-100 disabled:dark:hover:bg-neutral-800"
                  >
                    <Play className="w-3.5 h-3.5 mr-1.5" />
                    Run
                  </button>
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      openTestConfigModal(monitor);
                    }}
                    disabled={!monitor.enabled}
                    className="text-xs font-medium text-foreground bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1.5 rounded-md transition-colors flex items-center cursor-pointer disabled:hover:bg-neutral-100 disabled:dark:hover:bg-neutral-800"
                  >
                    Test
                  </button>
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      void handleDelete(monitor.id);
                    }}
                    className="text-xs font-medium text-red-600 bg-red-50 hover:bg-red-100 dark:bg-red-900/30 dark:hover:bg-red-900/40 dark:text-red-300 px-3 py-1.5 rounded-md transition-colors flex items-center cursor-pointer hover:opacity-80"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </CardFooter>
            </Card>
          ))}

          {monitors.length === 0 && (
            <div className="col-span-full py-16 text-center border border-dashed border-border/50 bg-muted/10 rounded-xl">
              <p className="text-muted-foreground">No monitors found. Create one to get started.</p>
            </div>
          )}
        </div>
      )}

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={closeModal} />
          <div className="relative bg-card border border-border rounded-xl shadow-lg w-full max-w-xl z-50">
            <div className="px-6 py-4 border-b border-border/40">
              <h2 className="text-xl font-semibold tracking-tight">{editingMonitorId ? "Edit Monitor" : "Create Monitor"}</h2>
            </div>

            <div className="p-6 space-y-5">
              <div className="space-y-2">
                <label className="text-sm font-medium">Name</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Daily AI Brief"
                  className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label htmlFor="monitor-time-period" className="text-sm font-medium">Frequency</label>
                  <select
                    id="monitor-time-period"
                    value={timePeriod}
                    onChange={(e) => setTimePeriod(e.target.value as "daily" | "weekly" | "custom")}
                    className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                  >
                    <option value="daily">daily</option>
                    <option value="weekly">weekly</option>
                    <option value="custom">custom</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Window (hours)</label>
                  <input
                    type="number"
                    min={1}
                    max={168}
                    value={windowHours}
                    onChange={(e) => setWindowHours(e.target.value)}
                    placeholder="24"
                    className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="monitor-report-type" className="text-sm font-medium">Template</label>
                  <select
                    id="monitor-report-type"
                    value={timePeriod === "daily" ? "daily" : timePeriod === "weekly" ? "weekly" : reportType}
                    onChange={(e) => setReportType(e.target.value as "daily" | "weekly" | "research" | "")}
                    disabled={timePeriod !== "custom"}
                    className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                  >
                    <option value="">select template</option>
                    <option value="daily">daily</option>
                    <option value="weekly">weekly</option>
                    <option value="research">research</option>
                  </select>
                </div>
              </div>

              {timePeriod === "custom" && (
                <div className="space-y-2">
                  <label className="text-sm font-medium">Custom Schedule (Cron)</label>
                  <input
                    value={customSchedule}
                    onChange={(e) => setCustomSchedule(e.target.value)}
                    placeholder="e.g. 0 9 * * 1-5"
                    className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                  />
                </div>
              )}

              <div className="space-y-2">
                <label className="text-sm font-medium">Sources</label>
                <div className="max-h-52 overflow-y-auto border border-border/40 rounded-md p-2 space-y-2">
                  {sourceGroups.length === 0 && (
                    <div className="text-xs text-muted-foreground p-2">No sources configured yet.</div>
                  )}
                  {sourceGroups.map(([category, groupedSources]) => (
                    <div key={category} className="space-y-1">
                      <button
                        type="button"
                        onClick={() => handleToggleSourceCategory(category)}
                        aria-expanded={expandedSourceCategories[category] ?? true}
                        className="w-full flex items-center justify-between px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground rounded hover:bg-muted/40"
                      >
                        <span>{`Category: ${category}`}</span>
                        <ChevronDown
                          className={cn(
                            "w-3.5 h-3.5 transition-transform",
                            !(expandedSourceCategories[category] ?? true) && "-rotate-90"
                          )}
                        />
                      </button>
                      {(expandedSourceCategories[category] ?? true) &&
                        groupedSources.map((source) => {
                          const isSelected = selectedSources.includes(source.id);
                          const sourceConfig = (source.config as Record<string, unknown>) ?? {};
                          const isArxivApi = source.collect_method === "rss" && Boolean(sourceConfig.arxiv_api);
                          const isTwitterSnaplytics = source.collect_method === "twitter_snaplytics";
                          const availableUsernames = Array.isArray(sourceConfig.usernames)
                            ? sourceConfig.usernames.filter((u): u is string => typeof u === "string" && u.trim().length > 0)
                            : [];
                          const selectedUsernames = Array.isArray(sourceOverrides[source.id]?.usernames)
                            ? sourceOverrides[source.id]!.usernames!
                            : availableUsernames;
                          const maxItemsValue =
                            typeof sourceOverrides[source.id]?.max_items === "number"
                              ? sourceOverrides[source.id]?.max_items
                              : sourceOverrides[source.id]?.limit;
                          const maxResultsValue = sourceOverrides[source.id]?.max_results;
                          const keywordsValue = Array.isArray(sourceOverrides[source.id]?.keywords)
                            ? sourceOverrides[source.id]?.keywords?.join(", ")
                            : "";
                          return (
                            <div key={source.id} className="px-2 py-1 rounded hover:bg-muted/40">
                              <label className="flex items-center gap-2 text-sm">
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={(e) => {
                                    if (e.target.checked) {
                                      setSelectedSources((prev) => [...prev, source.id]);
                                    } else {
                                      setSelectedSources((prev) => prev.filter((id) => id !== source.id));
                                      setSourceOverrides((prev) => {
                                        const next = { ...prev };
                                        delete next[source.id];
                                        return next;
                                      });
                                    }
                                  }}
                                />
                                <span>{source.name}</span>
                              </label>
                              {isSelected && (
                                <div className="ml-6 mt-2 flex items-center gap-2">
                                  <span className="text-xs text-muted-foreground">Fetch limit</span>
                                  <input
                                    type="number"
                                    min={1}
                                    max={200}
                                    value={typeof maxItemsValue === "number" ? maxItemsValue : ""}
                                    onChange={(e) => {
                                      const nextRaw = e.target.value.trim();
                                      if (!nextRaw) {
                                        setSourceOverrides((prev) => {
                                          const current = { ...(prev[source.id] || {}) };
                                          delete current.max_items;
                                          delete current.limit;
                                          const next = { ...prev };
                                          if (Object.keys(current).length === 0) {
                                            delete next[source.id];
                                          } else {
                                            next[source.id] = current;
                                          }
                                          return next;
                                        });
                                        return;
                                      }
                                      const nextLimit = Number(nextRaw);
                                      if (!Number.isFinite(nextLimit)) return;
                                      const bounded = Math.max(1, Math.min(200, Math.floor(nextLimit)));
                                      setSourceOverrides((prev) => {
                                        const current = { ...(prev[source.id] || {}), max_items: bounded };
                                        delete current.limit;
                                        return {
                                          ...prev,
                                          [source.id]: current,
                                        };
                                      });
                                    }}
                                    aria-label={`Fetch limit for ${source.name}`}
                                    placeholder="default"
                                    className="h-8 w-24 rounded-md border border-input bg-transparent px-2 text-xs"
                                  />
                                  <span className="text-[11px] text-muted-foreground">default: daily 5 / others 20</span>
                                </div>
                              )}
                              {isSelected && isArxivApi && (
                                <div className="ml-6 mt-2 space-y-2">
                                  <div className="flex items-center gap-2">
                                    <span className="text-xs text-muted-foreground">Keywords</span>
                                    <input
                                      type="text"
                                      value={keywordsValue}
                                      onChange={(e) => {
                                        const normalized = e.target.value
                                          .split(",")
                                          .map((item) => item.trim())
                                          .filter((item) => item.length > 0);
                                        if (normalized.length === 0) {
                                          setSourceOverrides((prev) => {
                                            const current = { ...(prev[source.id] || {}) };
                                            delete current.keywords;
                                            const next = { ...prev };
                                            if (Object.keys(current).length === 0) {
                                              delete next[source.id];
                                            } else {
                                              next[source.id] = current;
                                            }
                                            return next;
                                          });
                                          return;
                                        }
                                        setSourceOverrides((prev) => ({
                                          ...prev,
                                          [source.id]: {
                                            ...(prev[source.id] || {}),
                                            keywords: Array.from(new Set(normalized)).slice(0, 20),
                                          },
                                        }));
                                      }}
                                      aria-label={`Keywords for ${source.name}`}
                                      placeholder="reasoning, agent, multimodal"
                                      className="h-8 flex-1 rounded-md border border-input bg-transparent px-2 text-xs"
                                    />
                                  </div>
                                  <div className="flex items-center gap-2">
                                    <span className="text-xs text-muted-foreground">Max results</span>
                                    <input
                                      type="number"
                                      min={1}
                                      max={200}
                                      value={typeof maxResultsValue === "number" ? maxResultsValue : ""}
                                      onChange={(e) => {
                                        const nextRaw = e.target.value.trim();
                                        if (!nextRaw) {
                                          setSourceOverrides((prev) => {
                                            const current = { ...(prev[source.id] || {}) };
                                            delete current.max_results;
                                            const next = { ...prev };
                                            if (Object.keys(current).length === 0) {
                                              delete next[source.id];
                                            } else {
                                              next[source.id] = current;
                                            }
                                            return next;
                                          });
                                          return;
                                        }
                                        const nextLimit = Number(nextRaw);
                                        if (!Number.isFinite(nextLimit)) return;
                                        const bounded = Math.max(1, Math.min(200, Math.floor(nextLimit)));
                                        setSourceOverrides((prev) => ({
                                          ...prev,
                                          [source.id]: { ...(prev[source.id] || {}), max_results: bounded },
                                        }));
                                      }}
                                      aria-label={`Max results for ${source.name}`}
                                      placeholder="default"
                                      className="h-8 w-24 rounded-md border border-input bg-transparent px-2 text-xs"
                                    />
                                  </div>
                                </div>
                              )}
                              {isSelected && isTwitterSnaplytics && availableUsernames.length > 0 && (
                                <div className="ml-6 mt-2 space-y-2">
                                  <div className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Accounts</div>
                                  <div className="grid grid-cols-2 gap-2">
                                    {availableUsernames.map((username) => {
                                      const isSubSelected = selectedUsernames.includes(username);
                                      return (
                                        <label key={username} className="flex items-center gap-2 text-xs truncate cursor-pointer hover:text-foreground">
                                          <input
                                            type="checkbox"
                                            checked={isSubSelected}
                                            onChange={(e) => {
                                              const checked = e.target.checked;
                                              setSourceOverrides((prev) => {
                                                const current = { ...(prev[source.id] || {}) };
                                                let nextUsernames = Array.isArray(current.usernames) ? current.usernames : availableUsernames;
                                                if (checked) {
                                                  nextUsernames = [...nextUsernames, username];
                                                } else {
                                                  nextUsernames = nextUsernames.filter((u) => u !== username);
                                                }
                                                nextUsernames = Array.from(new Set(nextUsernames));
                                                return {
                                                  ...prev,
                                                  [source.id]: {
                                                    ...current,
                                                    usernames: nextUsernames
                                                  }
                                                };
                                              });
                                            }}
                                            className="rounded border-input text-foreground focus:ring-foreground accent-foreground w-3 h-3"
                                          />
                                          <span className="truncate" title={username}>{username}</span>
                                        </label>
                                      );
                                    })}
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })}
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Destinations (Optional)</label>
                <div className="max-h-40 overflow-y-auto border border-border/40 rounded-md p-2 space-y-1">
                  {destinations.filter(d => d.enabled).length === 0 && (
                    <div className="text-xs text-muted-foreground p-2">
                      No active destinations configured. Please set them up in the Destinations tab.
                    </div>
                  )}
                  {destinations.filter(d => d.enabled).map((dest) => (
                    <label key={dest.id} className="flex items-center gap-2 text-sm px-2 py-1.5 rounded hover:bg-muted/40 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedDestinations.includes(dest.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedDestinations((prev) => [...prev, dest.id]);
                          } else {
                            setSelectedDestinations((prev) => prev.filter((id) => id !== dest.id));
                          }
                        }}
                      />
                      <span className="font-medium">{dest.name}</span>
                      <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 border-primary/20 bg-primary/5 text-primary capitalize ml-auto">
                        {dest.type}
                      </Badge>
                    </label>
                  ))}
                </div>
                <p className="text-[10px] text-muted-foreground">Select where to push the generated reports dynamically. Only active destinations are shown.</p>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-border/40 flex items-center justify-end gap-3">
              <button onClick={closeModal} className="px-4 py-2 text-sm font-medium hover:bg-muted rounded-md transition-colors">
                Cancel
              </button>
              <button
                onClick={() => void handleSubmit()}
                disabled={!name || selectedSources.length === 0 || (timePeriod === "custom" && !reportType) || submitting}
                className="px-4 py-2 text-sm font-medium bg-foreground text-background hover:bg-foreground/90 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors"
              >
                {editingMonitorId ? submitting ? "Saving..." : "Save" : submitting ? "Creating..." : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}

      {isTestModalOpen && testMonitor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={() => setIsTestModalOpen(false)} />
          <div className="relative bg-card border border-border rounded-xl shadow-lg w-full max-w-md z-50 animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-4 border-b border-border/40">
              <h2 className="text-lg font-semibold tracking-tight">Test Run: {testMonitor.name}</h2>
            </div>

            <div className="p-6 space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Time Window</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setTestWindowPreset("24h")}
                    className={cn(
                      "h-9 rounded-md border text-xs font-medium",
                      testWindowPreset === "24h" ? "border-blue-500 bg-blue-50 text-blue-700" : "border-border"
                    )}
                  >
                    Last 24h
                  </button>
                  <button
                    type="button"
                    onClick={() => setTestWindowPreset("72h")}
                    className={cn(
                      "h-9 rounded-md border text-xs font-medium",
                      testWindowPreset === "72h" ? "border-blue-500 bg-blue-50 text-blue-700" : "border-border"
                    )}
                  >
                    Last 3d
                  </button>
                  <button
                    type="button"
                    onClick={() => setTestWindowPreset("168h")}
                    className={cn(
                      "h-9 rounded-md border text-xs font-medium",
                      testWindowPreset === "168h" ? "border-blue-500 bg-blue-50 text-blue-700" : "border-border"
                    )}
                  >
                    Last 7d
                  </button>
                  <button
                    type="button"
                    onClick={() => setTestWindowPreset("custom")}
                    className={cn(
                      "h-9 rounded-md border text-xs font-medium",
                      testWindowPreset === "custom" ? "border-blue-500 bg-blue-50 text-blue-700" : "border-border"
                    )}
                  >
                    Custom
                  </button>
                </div>
                {testWindowPreset === "custom" && (
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min={1}
                      max={testWindowCustomUnit === "days" ? 7 : 168}
                      value={testWindowCustomValue}
                      onChange={(e) => setTestWindowCustomValue(e.target.value)}
                      placeholder="24"
                      className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                      autoFocus
                    />
                    <select
                      value={testWindowCustomUnit}
                      onChange={(e) => setTestWindowCustomUnit(e.target.value as "hours" | "days")}
                      className="h-10 rounded-md border border-input bg-transparent px-2 text-sm"
                    >
                      <option value="hours">hours</option>
                      <option value="days">days</option>
                    </select>
                  </div>
                )}
                <p className="text-xs text-muted-foreground">
                  For test runs, max range is 7 days (168 hours).
                </p>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-border/40 flex items-center justify-end gap-3 bg-muted/20 rounded-b-xl">
              <button
                onClick={() => setIsTestModalOpen(false)}
                className="px-4 py-2 text-sm font-medium hover:bg-muted rounded-md transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleStartTestRun()}
                disabled={testWindowPreset === "custom" && (!testWindowCustomValue || Number(testWindowCustomValue) <= 0)}
                className="px-4 py-2 text-sm font-medium bg-foreground text-background hover:bg-foreground/90 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors flex items-center"
              >
                Start Test Run
              </button>
            </div>
          </div>
        </div>
      )}

      {isTestConsoleOpen && testConsoleMonitor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={closeTestConsole} />
          <div className="relative bg-card border border-border rounded-xl shadow-lg w-full max-w-2xl z-50 flex flex-col max-h-[85vh]">
            <div className="px-6 py-4 border-b border-border/40 flex items-center justify-between shrink-0">
              <h2 className="text-xl font-semibold tracking-tight">Test Console: {testConsoleMonitor.name}</h2>
              <div className="flex items-center gap-2">
                {testRun && ["pending", "running", "cancelling"].includes(testRun.status) && (
                  <button
                    type="button"
                    onClick={() => void handleTerminateTestRun()}
                    className="text-[11px] font-medium px-2 py-1 rounded border border-red-300 text-red-700 bg-red-50 hover:bg-red-100 dark:border-red-700 dark:text-red-300 dark:bg-red-900/20 dark:hover:bg-red-900/30"
                  >
                    Terminate
                  </button>
                )}
                <button
                  onClick={closeTestConsole}
                  className="text-muted-foreground hover:text-foreground p-1 rounded-md transition-colors"
                >
                  ✕
                </button>
              </div>
            </div>
            <div className="p-6 overflow-y-auto min-h-[300px]">
              {testLoading && !testRun ? (
                <div className="text-sm text-muted-foreground text-center py-10">Starting test run...</div>
              ) : !testRun ? (
                <div className="text-sm text-muted-foreground text-center py-10">No test run context found.</div>
              ) : (
                <div className="space-y-4">
                  <div className="rounded-lg border border-border/50 bg-muted/20 p-3 text-xs space-y-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="secondary" className="text-[10px] uppercase bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400">
                        Test
                      </Badge>
                      <span className="font-mono text-muted-foreground break-all">run: {testRun.run_id}</span>
                      <span className="text-muted-foreground">status: {testRun.status}</span>
                      <span className="text-muted-foreground">
                        progress: {testRun.source_done}/{testRun.source_total} ({testOverallProgress}%)
                      </span>
                      {testSecondsSinceProgress !== null && (
                        <span className="text-muted-foreground">last progress: {testSecondsSinceProgress}s ago</span>
                      )}
                    </div>
                    <div className="h-1.5 rounded bg-muted">
                      <div
                        className="h-1.5 rounded bg-emerald-500 transition-all"
                        style={{ width: `${testOverallProgress}%` }}
                      />
                    </div>
                    {testStageProgress.length > 0 && (
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                        {testStageProgress.map((item) => (
                          <div key={item.stage} className="rounded border border-border/40 px-2 py-1">
                            <div className="text-[10px] uppercase text-muted-foreground">{item.stage}</div>
                            <div className="text-xs font-medium">
                              {item.done}/{item.total}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    {isTestStalled && (
                      <div className="text-red-600 dark:text-red-400">
                        No stage progress for over 60s. Likely stuck in current stage.
                      </div>
                    )}
                    <div className="pt-1">
                      <button
                        type="button"
                        onClick={() => {
                          setIsTestConsoleOpen(false);
                          void openLogsModal(testConsoleMonitor, testRun.run_id);
                        }}
                        className="text-[11px] font-medium px-2 py-1 rounded border border-border hover:bg-muted"
                      >
                        View In Logs
                      </button>
                    </div>
                  </div>

                  <div className="border border-border/40 rounded-lg p-4 bg-muted/10">
                    <div className="text-xs font-medium mb-2">Event Timeline (Current Test Run)</div>
                    {testRunEvents.length === 0 ? (
                      <div className="text-xs text-muted-foreground">No event logs yet.</div>
                    ) : (
                      <div className="space-y-2">
                        {testRunEvents.map((event, idx) => {
                          const stage = String(event.stage ?? "-");
                          const level = String(event.level ?? "info");
                          const eventType = String(event.event_type ?? "-");
                          return (
                            <div key={`${event.id}-${idx}`} className="rounded border border-border/30 bg-background/60 p-2">
                              <div className="flex items-center gap-2 text-xs">
                                <span className="font-mono text-muted-foreground">
                                  {event.created_at ? new Date(event.created_at).toLocaleTimeString() : "--:--:--"}
                                </span>
                                <span className="font-medium">{stage}</span>
                                <span className="text-muted-foreground">{eventType}</span>
                                <Badge variant="secondary" className={cn(
                                  "text-[10px] uppercase",
                                  level === "info" && "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400",
                                  level === "warning" && "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400",
                                  level === "error" && "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400"
                                )}>
                                  {level}
                                </Badge>
                              </div>
                              <div className="mt-1 text-xs break-all whitespace-pre-wrap">{event.message}</div>
                              {event.payload && Object.keys(event.payload).length > 0 && (
                                <pre className="mt-1 text-[11px] text-muted-foreground whitespace-pre-wrap break-all">
                                  {JSON.stringify(event.payload, null, 2)}
                                </pre>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {isLogsModalOpen && logsMonitor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={closeLogsModal} />
          <div className="relative bg-card border border-border rounded-xl shadow-lg w-full max-w-2xl z-50 flex flex-col max-h-[85vh]">
            <div className="px-6 py-4 border-b border-border/40 flex items-center justify-between shrink-0">
              <h2 className="text-xl font-semibold tracking-tight">Run History: {logsMonitor.name}</h2>
              <button
                onClick={closeLogsModal}
                className="text-muted-foreground hover:text-foreground p-1 rounded-md transition-colors"
              >
                ✕
              </button>
            </div>
            <div className="p-6 overflow-y-auto min-h-[300px]">
              {loadingLogs ? (
                <div className="text-sm text-muted-foreground text-center py-10">Loading logs...</div>
              ) : monitorRuns.length === 0 && monitorLogs.length === 0 ? (
                <div className="text-sm text-muted-foreground text-center py-10">No run history found.</div>
              ) : (
                <div className="space-y-3">
                  {monitorRuns.map((run) => {
                    const isRunExpanded = logsFocusRunId === run.run_id;
                    const runTrace = isRunExpanded ? focusedTrace : [];
                    return (
                      <div key={run.run_id} className="border border-border/40 rounded-lg bg-muted/10 overflow-hidden">
                        <div
                          role="button"
                          tabIndex={0}
                          onClick={() => {
                            if (isRunExpanded) {
                              setLogsFocusRunId(null);
                            } else {
                              setLogsFocusRunId(run.run_id);
                            }
                          }}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              if (isRunExpanded) {
                                setLogsFocusRunId(null);
                              } else {
                                setLogsFocusRunId(run.run_id);
                              }
                            }
                          }}
                          className="w-full text-left p-4 hover:bg-muted/30 transition-colors cursor-pointer"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-2">
                              {isRunExpanded ? (
                                <ChevronDown className="w-4 h-4 shrink-0 text-muted-foreground" />
                              ) : (
                                <ChevronRight className="w-4 h-4 shrink-0 text-muted-foreground" />
                              )}
                              <Badge variant="secondary" className={cn(
                                "text-[10px] uppercase",
                                run.status === "success" && "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400",
                                run.status === "failed" && "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400",
                                run.status === "running" && "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400",
                                run.status === "partial_success" && "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400",
                                run.status === "cancelling" && "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
                                run.status === "cancelled" && "bg-neutral-200 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300"
                              )}>
                                {run.status}
                              </Badge>
                              <span className="text-xs text-muted-foreground">
                                {run.started_at ? new Date(run.started_at).toLocaleString() : "Unknown time"}
                              </span>
                              {run.trigger_type && (
                                <Badge variant="secondary" className="text-[10px] uppercase bg-neutral-200 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300">
                                  {run.trigger_type}
                                </Badge>
                              )}
                            </div>
                            <span className="text-xs font-mono text-muted-foreground break-all">
                              {run.run_id.slice(0, 8)}... {run.articles_count} articles
                            </span>
                          </div>
                          <div className="text-xs text-muted-foreground ml-6">
                            Sources: {run.source_done}/{run.source_total}
                            {run.source_failed > 0 ? `, failed ${run.source_failed}` : ""}
                          </div>
                          {run.error_message && (
                            <div className="mt-2 ml-6 text-xs text-red-600 bg-red-50 dark:bg-red-900/20 dark:text-red-400 p-2 rounded break-all whitespace-pre-wrap">
                              {run.error_message}
                            </div>
                          )}
                          {run.trigger_type === "test" && ["pending", "running", "cancelling"].includes(run.status) && (
                            <div className="mt-2 ml-6">
                              <button
                                type="button"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  void openTestConsoleForRun(logsMonitor, run.run_id);
                                }}
                                className="text-[11px] font-medium px-2 py-1 rounded border border-blue-300 text-blue-700 bg-blue-50 hover:bg-blue-100 dark:border-blue-700 dark:text-blue-300 dark:bg-blue-900/20 dark:hover:bg-blue-900/30"
                              >
                                Back To Test
                              </button>
                            </div>
                          )}
                        </div>

                        {isRunExpanded && (
                          <div className="border-t border-border/30 bg-neutral-950 rounded-b-lg overflow-hidden">
                            {runTrace.length === 0 ? (
                              <div className="px-4 py-3 text-xs text-neutral-500 font-mono">Loading events...</div>
                            ) : (
                              <div className="font-mono text-[12px] leading-relaxed max-h-[50vh] overflow-y-auto">
                                {runTrace.map((event, idx) => {
                                  const ts = event.created_at ? new Date(event.created_at).toLocaleTimeString() : "--:--:--";
                                  const stage = String(event.stage ?? "-");
                                  const level = String(event.level ?? "info");
                                  const eventType = String(event.event_type ?? "-");
                                  const hasPayload = event.payload && Object.keys(event.payload).length > 0;
                                  const levelColor = level === "error"
                                    ? "text-red-400"
                                    : level === "warning"
                                      ? "text-yellow-400"
                                      : "text-blue-400";
                                  return (
                                    <div
                                      key={`${event.id}-${idx}`}
                                      className={cn(
                                        "px-4 py-1.5 border-b border-neutral-800/60 hover:bg-neutral-900/80",
                                        level === "error" && "bg-red-950/30",
                                        level === "warning" && "bg-yellow-950/20"
                                      )}
                                    >
                                      <div className="flex items-start gap-2">
                                        <span className="text-neutral-500 shrink-0">{ts}</span>
                                        <span className={cn("uppercase text-[10px] font-bold shrink-0 mt-px", levelColor)}>
                                          {level.padEnd(5)}
                                        </span>
                                        <span className="text-emerald-400 shrink-0">[{stage}]</span>
                                        <span className="text-neutral-300">{eventType}</span>
                                      </div>
                                      {event.message && (
                                        <div className="text-neutral-400 pl-[calc(8ch+10ch+2rem)] whitespace-pre-wrap break-all">
                                          {event.message}
                                        </div>
                                      )}
                                      {hasPayload && (
                                        <pre className="text-neutral-600 pl-[calc(8ch+10ch+2rem)] whitespace-pre-wrap break-all">
                                          {JSON.stringify(event.payload, null, 2)}
                                        </pre>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="mt-8 text-xs text-muted-foreground flex items-center gap-2">
        <Activity className="w-3.5 h-3.5" />
        Monitor runs create task records and feed the daily pipeline.
      </div>
    </div>
  );
}
