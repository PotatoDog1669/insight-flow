"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Play, Plus, Trash2, Activity, Clock, Server, ChevronDown, ChevronRight, History, Calendar, Loader2 } from "lucide-react";
import {
  cancelMonitorRun,
  createMonitor,
  deleteMonitor,
  getProviders,
  getMonitorAIRoutingDefaults,
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
  type MonitorAIRouting,
  type MonitorAIRoutingDefaults,
  type MonitorAIProviderName,
  type MonitorAIStageName,
  type Provider,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { RunEventPayload } from "@/components/monitor/RunEventPayload";
import { cn } from "@/lib/utils";
import type { Destination } from "@/lib/api";

const STAGE_PROVIDER_OPTIONS: Record<MonitorAIStageName, MonitorAIProviderName[]> = {
  filter: ["rule", "llm_codex", "llm_openai"],
  keywords: ["rule", "llm_codex", "llm_openai"],
  global_summary: ["llm_codex", "llm_openai"],
  report: ["llm_codex", "llm_openai"],
};

const MODEL_PROVIDER_OPTIONS: Array<Exclude<MonitorAIProviderName, "rule">> = ["llm_codex", "llm_openai"];
const ACTIVE_RUN_STATUSES = ["pending", "running", "cancelling"] as const;
const isActiveRunStatus = (status: string) =>
  ACTIVE_RUN_STATUSES.includes(status as (typeof ACTIVE_RUN_STATUSES)[number]);
const WINDOW_PRESET_OPTIONS = [
  { value: "24", label: "1 天", hours: 24 },
  { value: "72", label: "3 天", hours: 72 },
  { value: "168", label: "7 天", hours: 168 },
  { value: "custom", label: "自定义", hours: null },
] as const;

type WindowPresetValue = (typeof WINDOW_PRESET_OPTIONS)[number]["value"];
type CustomWindowUnit = "hours" | "days";
type ReportType = "daily" | "weekly" | "research" | "paper";
type ScheduleWeekday = "0" | "1" | "2" | "3" | "4" | "5" | "6";

const DEFAULT_DAILY_SCHEDULE_TIME = "06:30";
const DEFAULT_WEEKLY_SCHEDULE_TIME = "20:00";
const DEFAULT_WEEKLY_DAY: ScheduleWeekday = "0";
const DEFAULT_CUSTOM_INTERVAL_DAYS = "2";
const LEGACY_SCHEDULE_NOTICE = "当前任务仍在使用旧版执行计划；如果修改这里的频率或时间，保存后会切换为新的设置。";
const WEEKDAY_OPTIONS: Array<{ value: ScheduleWeekday; label: string }> = [
  { value: "1", label: "周一" },
  { value: "2", label: "周二" },
  { value: "3", label: "周三" },
  { value: "4", label: "周四" },
  { value: "5", label: "周五" },
  { value: "6", label: "周六" },
  { value: "0", label: "周日" },
];

type ParsedScheduleFormState = {
  scheduleTime: string;
  weeklyDay: ScheduleWeekday;
  customIntervalDays: string;
  rawScheduleFallback: string | null;
  scheduleNotice: string | null;
};

const padTwoDigits = (value: number) => String(value).padStart(2, "0");

const defaultScheduleStateForTimePeriod = (timePeriod: "daily" | "weekly" | "custom"): ParsedScheduleFormState => ({
  scheduleTime: timePeriod === "weekly" ? DEFAULT_WEEKLY_SCHEDULE_TIME : DEFAULT_DAILY_SCHEDULE_TIME,
  weeklyDay: DEFAULT_WEEKLY_DAY,
  customIntervalDays: DEFAULT_CUSTOM_INTERVAL_DAYS,
  rawScheduleFallback: null,
  scheduleNotice: null,
});

const normalizeWeekdayToken = (token: string): ScheduleWeekday | null => {
  const normalized = token.trim().toLowerCase();
  const aliasMap: Record<string, ScheduleWeekday> = {
    "0": "0",
    "7": "0",
    sun: "0",
    sunday: "0",
    "1": "1",
    mon: "1",
    monday: "1",
    "2": "2",
    tue: "2",
    tues: "2",
    tuesday: "2",
    "3": "3",
    wed: "3",
    wednesday: "3",
    "4": "4",
    thu: "4",
    thur: "4",
    thurs: "4",
    thursday: "4",
    "5": "5",
    fri: "5",
    friday: "5",
    "6": "6",
    sat: "6",
    saturday: "6",
  };
  return aliasMap[normalized] ?? null;
};

const parseIntervalSchedule = (customSchedule: string | null): { intervalDays: string; scheduleTime: string } | null => {
  const raw = customSchedule?.trim() ?? "";
  const match = raw.match(/^interval:(\d{1,3})@(\d{1,2}):(\d{2})$/i);
  if (!match) return null;

  const intervalDays = Math.max(1, Math.min(365, Number(match[1]) || 1));
  const hour = Math.max(0, Math.min(23, Number(match[2]) || 0));
  const minute = Math.max(0, Math.min(59, Number(match[3]) || 0));
  return {
    intervalDays: String(intervalDays),
    scheduleTime: `${padTwoDigits(hour)}:${padTwoDigits(minute)}`,
  };
};

const parseScheduleFormState = (
  timePeriod: "daily" | "weekly" | "custom",
  customSchedule: string | null
): ParsedScheduleFormState => {
  const defaults = defaultScheduleStateForTimePeriod(timePeriod);
  const rawSchedule = customSchedule?.trim() ?? "";
  if (!rawSchedule) return defaults;

  if (timePeriod === "custom") {
    const intervalSchedule = parseIntervalSchedule(rawSchedule);
    if (intervalSchedule) {
      return {
        ...defaults,
        scheduleTime: intervalSchedule.scheduleTime,
        customIntervalDays: intervalSchedule.intervalDays,
      };
    }
  }

  const match = rawSchedule.match(/^(\d{1,2}) (\d{1,2}) \* \* ([^ ]+)$/);
  if (!match) {
    return {
      ...defaults,
      rawScheduleFallback: rawSchedule,
      scheduleNotice: LEGACY_SCHEDULE_NOTICE,
    };
  }

  const minute = Number(match[1]);
  const hour = Number(match[2]);
  if (!Number.isInteger(minute) || minute < 0 || minute > 59 || !Number.isInteger(hour) || hour < 0 || hour > 23) {
    return {
      ...defaults,
      rawScheduleFallback: rawSchedule,
      scheduleNotice: LEGACY_SCHEDULE_NOTICE,
    };
  }

  const scheduleTime = `${padTwoDigits(hour)}:${padTwoDigits(minute)}`;
  const dayField = match[3];
  if (timePeriod === "daily" && dayField === "*") {
    return { ...defaults, scheduleTime };
  }

  const weekday = normalizeWeekdayToken(dayField);
  if (timePeriod === "weekly" && weekday) {
    return { ...defaults, scheduleTime, weeklyDay: weekday };
  }
  if (timePeriod === "custom") {
    return {
      ...defaults,
      scheduleTime,
      rawScheduleFallback: rawSchedule,
      scheduleNotice: LEGACY_SCHEDULE_NOTICE,
    };
  }

  return {
    ...defaults,
    rawScheduleFallback: rawSchedule,
    scheduleNotice: LEGACY_SCHEDULE_NOTICE,
  };
};

const buildStructuredScheduleCron = (
  timePeriod: "daily" | "weekly" | "custom",
  scheduleTime: string,
  weeklyDay: ScheduleWeekday,
  customIntervalDays: string
): string => {
  const [hourText = "0", minuteText = "0"] = scheduleTime.split(":");
  const hour = Math.max(0, Math.min(23, Number(hourText) || 0));
  const minute = Math.max(0, Math.min(59, Number(minuteText) || 0));
  if (timePeriod === "daily") {
    return `${minute} ${hour} * * *`;
  }
  if (timePeriod === "weekly") {
    return `${minute} ${hour} * * ${weeklyDay}`;
  }
  const intervalDays = Math.max(1, Math.min(365, Number(customIntervalDays) || 1));
  return `interval:${intervalDays}@${padTwoDigits(hour)}:${padTwoDigits(minute)}`;
};

const resolveMonitorDestinationSelections = (
  monitor: Pick<Monitor, "destination_ids" | "destination_instance_ids">,
  destinations: Destination[],
): string[] => {
  const destinationInstanceIds = Array.isArray(monitor.destination_instance_ids) ? monitor.destination_instance_ids : [];
  const destinationIds = Array.isArray(monitor.destination_ids) ? monitor.destination_ids : [];
  const selectedIds = destinationInstanceIds.length > 0 ? destinationInstanceIds : destinationIds;
  if (selectedIds.length === 0) {
    return [];
  }

  const knownIds = new Set(destinations.map((destination) => destination.id));
  const instanceIdByType = new Map<Destination["type"], string>();

  for (const destination of destinations) {
    if (destination.enabled && !instanceIdByType.has(destination.type)) {
      instanceIdByType.set(destination.type, destination.id);
    }
  }
  for (const destination of destinations) {
    if (!instanceIdByType.has(destination.type)) {
      instanceIdByType.set(destination.type, destination.id);
    }
  }

  return Array.from(
    new Set(
      selectedIds
        .map((item) => {
          if (knownIds.has(item)) {
            return item;
          }
          return instanceIdByType.get(item as Destination["type"]) ?? null;
        })
        .filter((item): item is string => Boolean(item)),
    ),
  );
};

const weekdayLabel = (value: ScheduleWeekday): string =>
  WEEKDAY_OPTIONS.find((option) => option.value === value)?.label ?? value;

const formatMonitorScheduleSummary = (monitor: Pick<Monitor, "time_period" | "custom_schedule">): string => {
  if (monitor.time_period === "custom") {
    const intervalSchedule = parseIntervalSchedule(monitor.custom_schedule);
    if (intervalSchedule) {
      return `每 ${intervalSchedule.intervalDays} 天 ${intervalSchedule.scheduleTime}`;
    }
  }
  const parsed = parseScheduleFormState(monitor.time_period, monitor.custom_schedule);
  if (monitor.time_period === "daily") {
    return `每天 ${parsed.scheduleTime}`;
  }
  if (monitor.time_period === "weekly") {
    return `每${weekdayLabel(parsed.weeklyDay)} ${parsed.scheduleTime}`;
  }
  return parsed.rawScheduleFallback ? "旧版自定义计划" : "自定义更新";
};
type SourceOverrideFormState = {
  max_items?: number;
  limit?: number;
  max_results?: number;
  keywords?: string[];
  usernames?: string[];
  subreddits?: string[];
};

const recommendedReportTypeForTimePeriod = (timePeriod: "daily" | "weekly" | "custom"): ReportType => {
  if (timePeriod === "daily") return "daily";
  if (timePeriod === "weekly") return "weekly";
  return "research";
};

export default function MonitorsPage() {
  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingMonitorId, setEditingMonitorId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [timePeriod, setTimePeriod] = useState<"daily" | "weekly" | "custom">("daily");
  const [reportType, setReportType] = useState<ReportType>(recommendedReportTypeForTimePeriod("daily"));
  const [reportTypeTouched, setReportTypeTouched] = useState(false);
  const [scheduleTime, setScheduleTime] = useState(DEFAULT_DAILY_SCHEDULE_TIME);
  const [weeklyDay, setWeeklyDay] = useState<ScheduleWeekday>(DEFAULT_WEEKLY_DAY);
  const [customIntervalDays, setCustomIntervalDays] = useState(DEFAULT_CUSTOM_INTERVAL_DAYS);
  const [scheduleRawFallback, setScheduleRawFallback] = useState<string | null>(null);
  const [scheduleNotice, setScheduleNotice] = useState<string | null>(null);
  const [isScheduleDirty, setIsScheduleDirty] = useState(false);
  const [windowPreset, setWindowPreset] = useState<WindowPresetValue>("24");
  const [customWindowValue, setCustomWindowValue] = useState("24");
  const [customWindowUnit, setCustomWindowUnit] = useState<CustomWindowUnit>("hours");
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [sourceOverrides, setSourceOverrides] = useState<Record<string, SourceOverrideFormState>>({});
  const [expandedSourceCategories, setExpandedSourceCategories] = useState<Record<string, boolean>>({});
  const [selectedDestinationInstances, setSelectedDestinationInstances] = useState<string[]>([]);
  const [aiRouting, setAiRouting] = useState<MonitorAIRouting>({ stages: {}, providers: {} });
  const [aiRoutingDefaults, setAiRoutingDefaults] = useState<MonitorAIRoutingDefaults | null>(null);
  const [isAiRoutingExpanded, setIsAiRoutingExpanded] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Logs modal state
  const [isLogsModalOpen, setIsLogsModalOpen] = useState(false);
  const [logsMonitor, setLogsMonitor] = useState<Monitor | null>(null);
  const [monitorLogs, setMonitorLogs] = useState<CollectTask[]>([]);
  const [monitorRuns, setMonitorRuns] = useState<MonitorRunSummary[]>([]);
  const [runEvents, setRunEvents] = useState<TaskEvent[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [logsFocusRunId, setLogsFocusRunId] = useState<string | null>(null);
  const [terminatingRunIds, setTerminatingRunIds] = useState<Record<string, boolean>>({});
  const [startingRunIds, setStartingRunIds] = useState<Record<string, boolean>>({});
  const [togglingMonitorIds, setTogglingMonitorIds] = useState<Record<string, boolean>>({});
  const [deletingMonitorIds, setDeletingMonitorIds] = useState<Record<string, boolean>>({});
  const [openingLogsMonitorId, setOpeningLogsMonitorId] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const sourceMap = useMemo(() => {
    const map = new Map<string, Source>();
    sources.forEach((source) => map.set(source.id, source));
    return map;
  }, [sources]);

  const providerMap = useMemo(() => {
    const map = new Map<Exclude<MonitorAIProviderName, "rule">, Provider>();
    providers.forEach((provider) => {
      map.set(provider.id, provider);
    });
    return map;
  }, [providers]);

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

  const focusedTrace = useMemo(() => {
    return runEvents.filter((event) => Boolean(event));
  }, [runEvents]);

  const applyWindowHoursToForm = useCallback((hours: number | null | undefined) => {
    const normalized = typeof hours === "number" && Number.isFinite(hours)
      ? Math.max(1, Math.min(168, Math.floor(hours)))
      : 24;
    const matchedPreset = WINDOW_PRESET_OPTIONS.find((option) => option.hours === normalized);
    if (matchedPreset) {
      setWindowPreset(matchedPreset.value);
      setCustomWindowValue(String(normalized));
      setCustomWindowUnit("hours");
      return;
    }

    setWindowPreset("custom");
    if (normalized % 24 === 0) {
      setCustomWindowValue(String(normalized / 24));
      setCustomWindowUnit("days");
      return;
    }
    setCustomWindowValue(String(normalized));
    setCustomWindowUnit("hours");
  }, []);

  const resolvedWindowHours = useMemo(() => {
    const presetHours = WINDOW_PRESET_OPTIONS.find((option) => option.value === windowPreset)?.hours;
    if (presetHours !== null && presetHours !== undefined) {
      return presetHours;
    }
    const parsed = Number(customWindowValue);
    if (!Number.isFinite(parsed)) return 24;
    const normalized = customWindowUnit === "days" ? parsed * 24 : parsed;
    return Math.max(1, Math.min(168, Math.floor(normalized)));
  }, [customWindowUnit, customWindowValue, windowPreset]);

  const applyScheduleToForm = useCallback((nextTimePeriod: "daily" | "weekly" | "custom", nextCustomSchedule: string | null) => {
    const parsed = parseScheduleFormState(nextTimePeriod, nextCustomSchedule);
    setScheduleTime(parsed.scheduleTime);
    setWeeklyDay(parsed.weeklyDay);
    setCustomIntervalDays(parsed.customIntervalDays);
    setScheduleRawFallback(parsed.rawScheduleFallback);
    setScheduleNotice(parsed.scheduleNotice);
    setIsScheduleDirty(false);
  }, []);

  const effectiveCustomSchedule = useMemo(() => {
    if (scheduleRawFallback && !isScheduleDirty) {
      return scheduleRawFallback;
    }
    return buildStructuredScheduleCron(timePeriod, scheduleTime, weeklyDay, customIntervalDays);
  }, [customIntervalDays, isScheduleDirty, scheduleRawFallback, scheduleTime, timePeriod, weeklyDay]);

  const markScheduleChanged = useCallback(() => {
    setIsScheduleDirty(true);
    setScheduleRawFallback(null);
    setScheduleNotice(null);
  }, []);

  const loadData = useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent === true;
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const [monitorData, sourceData, providerData, destData, defaultRoutingData] = await Promise.all([
        getMonitors(),
        getSources(),
        getProviders().catch(() => []),
        getDestinations(),
        getMonitorAIRoutingDefaults().catch(() => null),
      ]);
      setMonitors(monitorData);
      setSources(sourceData);
      setProviders(providerData || []);

      // We expect the mock API to return the new Notion & Obsidian objects
      setDestinations(destData || []);
      setAiRoutingDefaults(defaultRoutingData);
    } catch (err) {
      if (!silent) {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    if (!actionNotice) return;
    const timer = window.setTimeout(() => {
      setActionNotice(null);
    }, 5000);
    return () => {
      window.clearTimeout(timer);
    };
  }, [actionNotice]);

  useEffect(() => {
    if (!reportTypeTouched) {
      setReportType(recommendedReportTypeForTimePeriod(timePeriod));
    }
  }, [reportTypeTouched, timePeriod]);

  const normalizeAiRoutingForForm = useCallback((raw: MonitorAIRouting | undefined): MonitorAIRouting => {
    const stages: Partial<Record<MonitorAIStageName, { primary: MonitorAIProviderName }>> = {};
    const providers: Partial<Record<MonitorAIProviderName, { model?: string; timeout_sec?: number; max_retry?: number }>> = {};

    const stagePayload = raw?.stages ?? {};
    for (const stage of Object.keys(STAGE_PROVIDER_OPTIONS) as MonitorAIStageName[]) {
      const value = stagePayload[stage]?.primary;
      if (value && STAGE_PROVIDER_OPTIONS[stage].includes(value)) {
        stages[stage] = { primary: value };
      }
    }

    const providerPayload = raw?.providers ?? {};
    for (const providerName of Object.keys(providerPayload) as MonitorAIProviderName[]) {
      const config = providerPayload[providerName];
      if (!config) continue;
      const cleaned: { model?: string; timeout_sec?: number; max_retry?: number } = {};
      const model = typeof config.model === "string" ? config.model.trim() : "";
      if (model) cleaned.model = model;
      if (typeof config.timeout_sec === "number" && Number.isFinite(config.timeout_sec) && config.timeout_sec >= 1) {
        cleaned.timeout_sec = Math.floor(config.timeout_sec);
      }
      if (typeof config.max_retry === "number" && Number.isFinite(config.max_retry) && config.max_retry >= 0) {
        cleaned.max_retry = Math.floor(config.max_retry);
      }
      if (Object.keys(cleaned).length > 0) {
        providers[providerName] = cleaned;
      }
    }

    return { stages, providers };
  }, []);

  const cleanAiRoutingForSubmit = useCallback((raw: MonitorAIRouting): MonitorAIRouting | undefined => {
    const normalized = normalizeAiRoutingForForm(raw);
    const stageEntries = Object.entries(normalized.stages ?? {}).filter(([, value]) => Boolean(value?.primary));
    const providerEntries = Object.entries(normalized.providers ?? {}).filter(([, value]) => {
      if (!value) return false;
      return Boolean((value.model && value.model.trim()) || typeof value.timeout_sec === "number" || typeof value.max_retry === "number");
    });

    if (stageEntries.length === 0 && providerEntries.length === 0) {
      return undefined;
    }
    return {
      stages: Object.fromEntries(stageEntries),
      providers: Object.fromEntries(providerEntries),
    };
  }, [normalizeAiRoutingForForm]);

  const selectedAiProviders = useMemo(() => {
    const stageValues = aiRouting.stages ?? {};
    const providers = new Set<Exclude<MonitorAIProviderName, "rule">>();
    for (const stageName of Object.keys(stageValues) as MonitorAIStageName[]) {
      const provider = stageValues[stageName]?.primary;
      if (provider && provider !== "rule") {
        providers.add(provider);
      }
    }
    for (const providerName of Object.keys(aiRouting.providers ?? {}) as MonitorAIProviderName[]) {
      if (providerName !== "rule") {
        providers.add(providerName);
      }
    }
    return Array.from(providers);
  }, [aiRouting]);

  const unconfiguredAiProviders = useMemo(() => {
    return selectedAiProviders.filter((providerId) => {
      const provider = providerMap.get(providerId);
      return provider ? !provider.enabled : false;
    });
  }, [providerMap, selectedAiProviders]);

  useEffect(() => {
    if (!isModalOpen) return;
    if (unconfiguredAiProviders.length === 0) return;
    setIsAiRoutingExpanded(true);
  }, [isModalOpen, unconfiguredAiProviders]);

  const aiRoutingInheritLabel = useCallback((stage: MonitorAIStageName) => {
    const current = aiRoutingDefaults?.stages?.[stage];
    const normalized = typeof current === "string" ? current.trim() : "";
    if (normalized && STAGE_PROVIDER_OPTIONS[stage].includes(normalized as MonitorAIProviderName)) {
      return `inherit (current: ${normalized})`;
    }
    return "inherit default";
  }, [aiRoutingDefaults]);

  const resetForm = () => {
    setName("");
    setTimePeriod("daily");
    setReportType(recommendedReportTypeForTimePeriod("daily"));
    setReportTypeTouched(false);
    applyScheduleToForm("daily", null);
    applyWindowHoursToForm(24);
    setSelectedSources([]);
    setSourceOverrides({});
    setExpandedSourceCategories(
      Object.fromEntries(sourceGroups.map(([category]) => [category, true])) as Record<string, boolean>
    );
    setSelectedDestinationInstances([]);
    setAiRouting({ stages: {}, providers: {} });
    setIsAiRoutingExpanded(false);
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
    setReportType(monitor.report_type);
    setReportTypeTouched(monitor.report_type !== recommendedReportTypeForTimePeriod(monitor.time_period));
    applyScheduleToForm(monitor.time_period, monitor.custom_schedule);
    applyWindowHoursToForm(monitor.window_hours || 24);
    setSelectedSources(monitor.source_ids);
    setSourceOverrides(monitor.source_overrides ?? {});
    setExpandedSourceCategories(
      Object.fromEntries(sourceGroups.map(([category]) => [category, true])) as Record<string, boolean>
    );
    setSelectedDestinationInstances(resolveMonitorDestinationSelections(monitor, destinations));
    setAiRouting(normalizeAiRoutingForForm(monitor.ai_routing));
    setIsModalOpen(true);
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
      setError(err instanceof Error ? err.message : "Failed to fetch logs");
      setActionNotice({
        type: "error",
        message: "Failed to open logs. Please try again.",
      });
    } finally {
      setLoadingLogs(false);
    }
  };

  const handleOpenLogs = async (monitor: Monitor) => {
    setOpeningLogsMonitorId(monitor.id);
    setError(null);
    setActionNotice(null);
    try {
      await openLogsModal(monitor);
    } finally {
      setOpeningLogsMonitorId((current) => (current === monitor.id ? null : current));
    }
  };

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
          setError(err instanceof Error ? err.message : "Failed to refresh logs");
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

  const handleTimePeriodChange = (nextTimePeriod: "daily" | "weekly" | "custom") => {
    markScheduleChanged();
    setTimePeriod(nextTimePeriod);
    if (nextTimePeriod === "daily" && !scheduleTime) {
      setScheduleTime(DEFAULT_DAILY_SCHEDULE_TIME);
    }
    if (nextTimePeriod === "weekly") {
      setScheduleTime((current) => current || DEFAULT_WEEKLY_SCHEDULE_TIME);
    }
    if (nextTimePeriod === "custom") {
      setScheduleTime((current) => current || DEFAULT_DAILY_SCHEDULE_TIME);
      setCustomIntervalDays((current) => current || DEFAULT_CUSTOM_INTERVAL_DAYS);
    }
  };

  const handleAiStageProviderChange = (stage: MonitorAIStageName, nextValue: string) => {
    setAiRouting((prev) => {
      const nextStages = { ...(prev.stages ?? {}) };
      const provider = nextValue as MonitorAIProviderName;
      if (!nextValue) {
        delete nextStages[stage];
      } else if (STAGE_PROVIDER_OPTIONS[stage].includes(provider)) {
        nextStages[stage] = { primary: provider };
      }
      return { ...prev, stages: nextStages };
    });
  };

  const handleAiProviderConfigChange = (
    provider: Exclude<MonitorAIProviderName, "rule">,
    key: "model" | "timeout_sec" | "max_retry",
    rawValue: string
  ) => {
    setAiRouting((prev) => {
      const nextProviders = { ...(prev.providers ?? {}) };
      const current = { ...(nextProviders[provider] ?? {}) };

      if (key === "model") {
        const normalized = rawValue.trim();
        if (normalized) {
          current.model = normalized;
        } else {
          delete current.model;
        }
      } else {
        const text = rawValue.trim();
        if (!text) {
          delete current[key];
        } else {
          const parsed = Number(text);
          if (!Number.isFinite(parsed)) {
            return prev;
          }
          const bounded = key === "timeout_sec" ? Math.max(1, Math.floor(parsed)) : Math.max(0, Math.floor(parsed));
          current[key] = bounded;
        }
      }

      if (Object.keys(current).length === 0) {
        delete nextProviders[provider];
      } else {
        nextProviders[provider] = current;
      }
      return { ...prev, providers: nextProviders };
    });
  };

  const handleSubmit = async () => {
    const effectiveReportType = reportType;
    if (!name || selectedSources.length === 0 || !effectiveReportType) return;
    setSubmitting(true);
    setError(null);
    const cleanedSourceOverrides = Object.fromEntries(
      Object.entries(sourceOverrides)
        .filter(([sourceId]) => selectedSources.includes(sourceId))
        .map(([sourceId, override]) => {
          const cleaned: SourceOverrideFormState = {};

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

          const subreddits = Array.isArray(override?.subreddits)
            ? normalizeRedditSubreddits(
              override.subreddits
                .map((item) => String(item).trim())
                .filter((item) => item.length > 0)
            )
            : null;
          if (subreddits !== null) {
            cleaned.subreddits = subreddits;
          }

          return [sourceId, cleaned];
        })
        .filter(([, override]) => Object.keys(override).length > 0)
    ) as Record<string, SourceOverrideFormState>;
    const cleanedAiRouting = cleanAiRoutingForSubmit(aiRouting);
    const payload = {
      name,
      time_period: timePeriod,
      report_type: effectiveReportType,
      source_ids: selectedSources,
      source_overrides: cleanedSourceOverrides,
      ai_routing: cleanedAiRouting,
      destination_instance_ids: selectedDestinationInstances,
      window_hours: resolvedWindowHours,
      custom_schedule: effectiveCustomSchedule,
    };
    try {
      if (editingMonitorId) {
        const target = monitors.find((item) => item.id === editingMonitorId);
        await updateMonitor(editingMonitorId, {
          ...payload,
          ai_routing: cleanedAiRouting ?? null,
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

  const handleRunNow = async (monitor: Monitor) => {
    setError(null);
    setActionNotice(null);
    setStartingRunIds((prev) => ({ ...prev, [monitor.id]: true }));
    try {
      const runResponse = await runMonitor(monitor.id);
      setStartingRunIds((prev) => {
        const next = { ...prev };
        delete next[monitor.id];
        return next;
      });
      setActionNotice({
        type: "success",
        message: `Run started. Open Logs to follow progress. Run ID: ${runResponse.run_id}`,
      });
      void loadData({ silent: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Run failed";
      setError(message);
      setActionNotice({
        type: "error",
        message: "Failed to start run.",
      });
      setStartingRunIds((prev) => {
        const next = { ...prev };
        delete next[monitor.id];
        return next;
      });
    }
  };

  const handleTerminateRunFromLogs = async (monitorId: string, runId: string) => {
    setTerminatingRunIds((prev) => ({ ...prev, [runId]: true }));
    try {
      await cancelMonitorRun(monitorId, runId);
      await fetchRunsAndEvents(monitorId, runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Terminate run failed");
    } finally {
      setTerminatingRunIds((prev) => {
        const next = { ...prev };
        delete next[runId];
        return next;
      });
    }
  };

  const handleToggle = async (monitor: Monitor) => {
    setError(null);
    setActionNotice(null);
    setTogglingMonitorIds((prev) => ({ ...prev, [monitor.id]: true }));
    try {
      await updateMonitor(monitor.id, { enabled: !monitor.enabled });
      await loadData();
      setActionNotice({
        type: "success",
        message: monitor.enabled ? "Monitor paused." : "Monitor resumed.",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Update failed";
      setError(message);
      setActionNotice({
        type: "error",
        message: "Failed to update monitor status.",
      });
    } finally {
      setTogglingMonitorIds((prev) => {
        const next = { ...prev };
        delete next[monitor.id];
        return next;
      });
    }
  };

  const handleDelete = async (monitorId: string) => {
    setError(null);
    setActionNotice(null);
    setDeletingMonitorIds((prev) => ({ ...prev, [monitorId]: true }));
    try {
      await deleteMonitor(monitorId);
      await loadData();
      setActionNotice({
        type: "success",
        message: "Monitor deleted.",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Delete failed";
      setError(message);
      setActionNotice({
        type: "error",
        message: "Failed to delete monitor.",
      });
    } finally {
      setDeletingMonitorIds((prev) => {
        const next = { ...prev };
        delete next[monitorId];
        return next;
      });
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 py-8 md:py-12">
      <header className="mb-10 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-2">任务</h1>
          <p className="text-muted-foreground text-sm max-w-2xl">
            配置自动化研究任务并按需运行。
          </p>
        </div>
        <button
          onClick={openCreateModal}
          className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors bg-foreground text-background shadow hover:bg-foreground/90 h-9 px-4 py-2"
        >
          <Plus className="w-4 h-4 mr-2" />
          创建任务
        </button>
      </header>

      {loading && <div className="py-10 text-sm text-muted-foreground">Loading monitors...</div>}
      {error && <div className="py-4 text-sm text-red-500">{error}</div>}
      {actionNotice && (
        <div
          className={cn(
            "py-3 px-4 text-sm rounded-md border",
            actionNotice.type === "success"
              ? "text-green-700 bg-green-50 border-green-200 dark:text-green-300 dark:bg-green-900/20 dark:border-green-900/40"
              : "text-red-700 bg-red-50 border-red-200 dark:text-red-300 dark:bg-red-900/20 dark:border-red-900/40"
          )}
        >
          {actionNotice.message}
        </div>
      )}

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
                    {monitor.report_type === "daily" ? "日报" : monitor.report_type === "weekly" ? "周报" : monitor.report_type === "research" ? "研究" : monitor.report_type === "paper" ? "论文" : monitor.report_type}
                  </Badge>
                  <Badge variant="secondary" className={monitor.enabled ? "bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400" : "bg-muted text-muted-foreground"}>
                    {monitor.enabled ? "运行中" : "已暂停"}
                  </Badge>
                </div>
              </CardHeader>

              <CardContent className="pb-4 flex-1 text-sm text-muted-foreground space-y-2">
                <div className="flex items-center space-x-2">
                  <Server className="w-4 h-4" />
                  <span>{monitor.source_ids.length} 个信息源</span>
                </div>
                <div className="flex items-center space-x-2">
                  <Calendar className="w-4 h-4" />
                  <span>{formatMonitorScheduleSummary(monitor)}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <Clock className="w-4 h-4" />
                  <span>{monitor.last_run ? new Date(monitor.last_run).toLocaleString() : "从未运行"}</span>
                </div>
                <div className="text-xs text-muted-foreground/80">
                  {monitor.source_ids.map((sourceId) => sourceMap.get(sourceId)?.name ?? sourceId).join(", ")}
                </div>
              </CardContent>

              <CardFooter className="pt-0 justify-between items-center border-t border-border/40 pb-3 pt-3 mt-auto">
                <button
                  type="button"
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    void handleToggle(monitor);
                  }}
                  disabled={Boolean(togglingMonitorIds[monitor.id]) || Boolean(deletingMonitorIds[monitor.id])}
                  className={cn(
                    "text-xs px-3 py-1.5 rounded-md transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed",
                    monitor.enabled
                      ? "bg-yellow-50 hover:bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:hover:bg-yellow-900/40 dark:text-yellow-300"
                      : "bg-green-50 hover:bg-green-100 text-green-700 dark:bg-green-900/30 dark:hover:bg-green-900/40 dark:text-green-300"
                  )}
                >
                  {togglingMonitorIds[monitor.id] ? "更新中..." : monitor.enabled ? "暂停" : "恢复"}
                </button>
                <div className="flex items-center justify-end gap-1.5 ml-2">
                  <button
                    type="button"
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      void handleOpenLogs(monitor);
                    }}
                    disabled={openingLogsMonitorId === monitor.id || Boolean(deletingMonitorIds[monitor.id])}
                    className="text-xs font-medium text-foreground bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 px-2.5 py-1.5 rounded-md transition-colors flex items-center cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:bg-neutral-100 disabled:dark:hover:bg-neutral-800"
                  >
                    {openingLogsMonitorId === monitor.id ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <>
                        <History className="w-3.5 h-3.5 mr-1" />
                        日志
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      void handleRunNow(monitor);
                    }}
                    disabled={!monitor.enabled || Boolean(startingRunIds[monitor.id]) || Boolean(deletingMonitorIds[monitor.id])}
                    className="text-xs font-medium text-foreground bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 disabled:opacity-50 disabled:cursor-not-allowed px-2.5 py-1.5 rounded-md transition-colors flex items-center cursor-pointer disabled:hover:bg-neutral-100 disabled:dark:hover:bg-neutral-800"
                  >
                    {startingRunIds[monitor.id] ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                        启动中...
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5 mr-1" />
                        运行
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      void handleDelete(monitor.id);
                    }}
                    disabled={Boolean(deletingMonitorIds[monitor.id])}
                    className="text-xs font-medium text-red-600 bg-red-50 hover:bg-red-100 dark:bg-red-900/30 dark:hover:bg-red-900/40 dark:text-red-300 px-2 py-1.5 rounded-md transition-colors flex items-center cursor-pointer hover:opacity-80 disabled:opacity-60 disabled:cursor-not-allowed"
                    title="Delete Monitor"
                  >
                    {deletingMonitorIds[monitor.id] ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="w-3.5 h-3.5" />
                    )}
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
          <div className="relative bg-card border border-border rounded-xl shadow-lg w-full max-w-xl z-50 flex flex-col max-h-[85vh]">
            <div className="px-6 py-4 border-b border-border/40 shrink-0">
              <h2 className="text-xl font-semibold tracking-tight">{editingMonitorId ? "编辑任务" : "创建任务"}</h2>
            </div>

            <div className="p-6 space-y-5 overflow-y-auto">
              <div className="space-y-2">
                <label className="text-sm font-medium">名称</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="例如：每日 AI 简报"
                  className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                />
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <label htmlFor="monitor-time-period" className="text-sm font-medium">更新频率</label>
                  <select
                    id="monitor-time-period"
                    value={timePeriod}
                    onChange={(e) => handleTimePeriodChange(e.target.value as "daily" | "weekly" | "custom")}
                    className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                  >
                    <option value="daily">每日</option>
                    <option value="weekly">每周</option>
                    <option value="custom">自定义</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label htmlFor="monitor-window-preset" className="text-sm font-medium">时间窗口</label>
                  <select
                    id="monitor-window-preset"
                    aria-label="时间窗口"
                    value={windowPreset}
                    onChange={(e) => setWindowPreset(e.target.value as WindowPresetValue)}
                    className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                  >
                    {WINDOW_PRESET_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  <p className="text-[11px] text-muted-foreground">控制每次抓取时回看的内容范围。</p>
                </div>
                <div className="space-y-2">
                  <label htmlFor="monitor-report-type" className="text-sm font-medium">报告模板</label>
                  <select
                    id="monitor-report-type"
                    value={timePeriod === "daily" ? "daily" : timePeriod === "weekly" ? "weekly" : reportType}
                    disabled={timePeriod !== "custom"}
                    aria-label="报告模板"
                    onChange={(e) => {
                      const nextReportType = e.target.value as ReportType;
                      setReportType(nextReportType);
                      setReportTypeTouched(nextReportType !== recommendedReportTypeForTimePeriod(timePeriod));
                    }}
                    className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                  >
                    <option value="daily">日报</option>
                    <option value="weekly">周报</option>
                    <option value="research">研究</option>
                    <option value="paper">论文</option>
                  </select>
                  <p className="text-[11px] text-muted-foreground">
                    {`推荐模板：${recommendedReportTypeForTimePeriod(timePeriod) === "daily" ? "日报" : recommendedReportTypeForTimePeriod(timePeriod) === "weekly" ? "周报" : "研究"}，也可以按需自行调整。`}
                  </p>
                </div>
              </div>

              {windowPreset === "custom" && (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-[minmax(0,1fr)_160px]">
                  <div className="space-y-2">
                    <label htmlFor="monitor-custom-window-value" className="text-sm font-medium">自定义时间窗口数值</label>
                    <input
                      id="monitor-custom-window-value"
                      aria-label="自定义时间窗口数值"
                      type="number"
                      min={1}
                      max={customWindowUnit === "days" ? 7 : 168}
                      value={customWindowValue}
                      onChange={(e) => setCustomWindowValue(e.target.value)}
                      placeholder={customWindowUnit === "days" ? "2" : "12"}
                      className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                    />
                  </div>
                  <div className="space-y-2">
                    <label htmlFor="monitor-custom-window-unit" className="text-sm font-medium">自定义时间窗口单位</label>
                    <select
                      id="monitor-custom-window-unit"
                      aria-label="自定义时间窗口单位"
                      value={customWindowUnit}
                      onChange={(e) => setCustomWindowUnit(e.target.value as CustomWindowUnit)}
                      className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                    >
                      <option value="hours">小时</option>
                      <option value="days">天</option>
                    </select>
                  </div>
                </div>
              )}

              <div className="space-y-3 rounded-md border border-border/40 p-4">
                <div className="space-y-1">
                  <div className="text-sm font-medium">执行计划</div>
                  <p className="text-[11px] text-muted-foreground">设置这个任务在什么时间自动运行。</p>
                </div>

                {timePeriod === "daily" && (
                  <div className="space-y-2">
                    <label htmlFor="monitor-schedule-time" className="text-sm font-medium">执行时间</label>
                    <input
                      id="monitor-schedule-time"
                      aria-label="执行时间"
                      type="time"
                      value={scheduleTime}
                      onChange={(e) => {
                        markScheduleChanged();
                        setScheduleTime(e.target.value || DEFAULT_DAILY_SCHEDULE_TIME);
                      }}
                      className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm md:w-56"
                    />
                  </div>
                )}

                {timePeriod === "weekly" && (
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <label htmlFor="monitor-weekly-day" className="text-sm font-medium">执行星期</label>
                      <select
                        id="monitor-weekly-day"
                        aria-label="执行星期"
                        value={weeklyDay}
                        onChange={(e) => {
                          markScheduleChanged();
                          setWeeklyDay(e.target.value as ScheduleWeekday);
                        }}
                        className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                      >
                        {WEEKDAY_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="monitor-schedule-time" className="text-sm font-medium">执行时间</label>
                      <input
                        id="monitor-schedule-time"
                        aria-label="执行时间"
                        type="time"
                        value={scheduleTime}
                        onChange={(e) => {
                          markScheduleChanged();
                          setScheduleTime(e.target.value || DEFAULT_WEEKLY_SCHEDULE_TIME);
                        }}
                        className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                      />
                    </div>
                  </div>
                )}

                {timePeriod === "custom" && (
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-[180px_220px]">
                    <div className="space-y-2">
                      <label htmlFor="monitor-custom-interval-days" className="text-sm font-medium">更新间隔（天）</label>
                      <input
                        id="monitor-custom-interval-days"
                        aria-label="更新间隔（天）"
                        type="number"
                        min={1}
                        max={365}
                        value={customIntervalDays}
                        onChange={(e) => {
                          markScheduleChanged();
                          setCustomIntervalDays(e.target.value);
                        }}
                        className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                      />
                      <p className="text-[11px] text-muted-foreground">表示任务每隔几天自动运行一次。</p>
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="monitor-schedule-time" className="text-sm font-medium">执行时间</label>
                      <input
                        id="monitor-schedule-time"
                        aria-label="执行时间"
                        type="time"
                        value={scheduleTime}
                        onChange={(e) => {
                          markScheduleChanged();
                          setScheduleTime(e.target.value || DEFAULT_DAILY_SCHEDULE_TIME);
                        }}
                        className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                      />
                    </div>
                  </div>
                )}

                {scheduleNotice && (
                  <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-3 text-xs text-amber-900">
                    {scheduleNotice}
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">信息源</label>
                <div className="max-h-52 overflow-y-auto border border-border/40 rounded-md p-2 space-y-2">
                  {sourceGroups.length === 0 && (
                    <div className="text-xs text-muted-foreground p-2">暂未配置任何信息源。</div>
                  )}
                  {sourceGroups.map(([category, groupedSources]) => (
                    <div key={category} className="space-y-1">
                      <button
                        type="button"
                        onClick={() => handleToggleSourceCategory(category)}
                        aria-expanded={expandedSourceCategories[category] ?? true}
                        className="w-full flex items-center justify-between px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground rounded hover:bg-muted/40"
                      >
                        <span>{`分类: ${category}`}</span>
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
                          const isAcademicApi =
                            source.category === "academic" &&
                            (isArxivApi || ["openalex", "europe_pmc", "pubmed"].includes(source.collect_method));
                          const isTwitterSnaplytics = source.collect_method === "twitter_snaplytics";
                          const isConfigurableReddit = isConfigurableRedditSource(source);
                          const availableUsernames = Array.isArray(sourceConfig.usernames)
                            ? sourceConfig.usernames.filter((u): u is string => typeof u === "string" && u.trim().length > 0)
                            : [];
                          const availableSubreddits = Array.isArray(sourceConfig.subreddits)
                            ? normalizeRedditSubreddits(
                              sourceConfig.subreddits.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
                            )
                            : [];
                          const selectedUsernames = Array.isArray(sourceOverrides[source.id]?.usernames)
                            ? sourceOverrides[source.id]!.usernames!
                            : availableUsernames;
                          const selectedSubreddits = Array.isArray(sourceOverrides[source.id]?.subreddits)
                            ? normalizeRedditSubreddits(sourceOverrides[source.id]!.subreddits!)
                            : availableSubreddits;
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
                                  <span className="text-xs text-muted-foreground">获取限制</span>
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
                                    placeholder="默认"
                                    className="h-8 w-24 rounded-md border border-input bg-transparent px-2 text-xs"
                                  />
                                  <span className="text-[11px] text-muted-foreground">默认：每日 5 篇 / 其他 20 篇</span>
                                </div>
                              )}
                              {isSelected && isAcademicApi && (
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
                                  <div className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider mb-1">账号列表</div>
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
                              {isSelected && isConfigurableReddit && availableSubreddits.length > 0 && (
                                <div className="ml-6 mt-2 space-y-2">
                                  <div className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider mb-1">版块列表</div>
                                  <div className="grid grid-cols-2 gap-2">
                                    {availableSubreddits.map((subreddit) => {
                                      const isSubSelected = selectedSubreddits.includes(subreddit);
                                      return (
                                        <label key={subreddit} className="flex items-center gap-2 text-xs truncate cursor-pointer hover:text-foreground">
                                          <input
                                            type="checkbox"
                                            checked={isSubSelected}
                                            onChange={(e) => {
                                              const checked = e.target.checked;
                                              setSourceOverrides((prev) => {
                                                const current = { ...(prev[source.id] || {}) };
                                                let nextSubreddits = Array.isArray(current.subreddits) ? current.subreddits : availableSubreddits;
                                                if (checked) {
                                                  nextSubreddits = [...nextSubreddits, subreddit];
                                                } else {
                                                  nextSubreddits = nextSubreddits.filter((item) => item !== subreddit);
                                                }
                                                return {
                                                  ...prev,
                                                  [source.id]: {
                                                    ...current,
                                                    subreddits: normalizeRedditSubreddits(nextSubreddits),
                                                  },
                                                };
                                              });
                                            }}
                                            className="rounded border-input text-foreground focus:ring-foreground accent-foreground w-3 h-3"
                                          />
                                          <span className="truncate" title={subreddit}>{subreddit}</span>
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

              <div className="space-y-3 border border-border/40 rounded-md p-3">
                <button
                  type="button"
                  aria-label="AI 路由配置（高级）"
                  aria-expanded={isAiRoutingExpanded}
                  onClick={() => setIsAiRoutingExpanded((prev) => !prev)}
                  className="flex w-full items-start justify-between gap-3 rounded-md text-left hover:bg-muted/30 px-1 py-1 transition-colors"
                >
                  <div>
                    <div className="text-sm font-medium">AI 路由配置（高级）</div>
                    <p className="text-[11px] text-muted-foreground mt-1">
                      在此覆盖该任务中不同阶段的模型配置。如果留空，则继承全局默认设置。
                      {aiRoutingDefaults?.profile_name ? `（当前为 ${aiRoutingDefaults.profile_name}）` : ""}
                    </p>
                  </div>
                  {isAiRoutingExpanded ? (
                    <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                  )}
                </button>
                {isAiRoutingExpanded && (
                  <>
                    {unconfiguredAiProviders.length > 0 && (
                      <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-200">
                        以下 provider 尚未在模型配置中启用：{unconfiguredAiProviders.join(", ")}。你仍然可以保存任务，但运行时可能失败。
                      </div>
                    )}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div className="space-y-1.5">
                    <label htmlFor="monitor-ai-filter-provider" className="text-xs font-medium text-muted-foreground">过滤阶段提供商</label>
                    <select
                      id="monitor-ai-filter-provider"
                      aria-label="Filter stage provider"
                      value={aiRouting.stages?.filter?.primary ?? ""}
                      onChange={(e) => handleAiStageProviderChange("filter", e.target.value)}
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-2 py-1 text-xs"
                    >
                      <option value="">{aiRoutingInheritLabel("filter")}</option>
                      {STAGE_PROVIDER_OPTIONS.filter.map((provider) => (
                        <option key={provider} value={provider}>{provider}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label htmlFor="monitor-ai-keywords-provider" className="text-xs font-medium text-muted-foreground">提取关键字阶段提供商</label>
                    <select
                      id="monitor-ai-keywords-provider"
                      aria-label="Keywords stage provider"
                      value={aiRouting.stages?.keywords?.primary ?? ""}
                      onChange={(e) => handleAiStageProviderChange("keywords", e.target.value)}
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-2 py-1 text-xs"
                    >
                      <option value="">{aiRoutingInheritLabel("keywords")}</option>
                      {STAGE_PROVIDER_OPTIONS.keywords.map((provider) => (
                        <option key={provider} value={provider}>{provider}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label htmlFor="monitor-ai-global-summary-provider" className="text-xs font-medium text-muted-foreground">全局摘要阶段提供商</label>
                    <select
                      id="monitor-ai-global-summary-provider"
                      aria-label="Global summary stage provider"
                      value={aiRouting.stages?.global_summary?.primary ?? ""}
                      onChange={(e) => handleAiStageProviderChange("global_summary", e.target.value)}
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-2 py-1 text-xs"
                    >
                      <option value="">{aiRoutingInheritLabel("global_summary")}</option>
                      {STAGE_PROVIDER_OPTIONS.global_summary.map((provider) => (
                        <option key={provider} value={provider}>{provider}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label htmlFor="monitor-ai-report-provider" className="text-xs font-medium text-muted-foreground">生成报告阶段提供商</label>
                    <select
                      id="monitor-ai-report-provider"
                      aria-label="Report stage provider"
                      value={aiRouting.stages?.report?.primary ?? ""}
                      onChange={(e) => handleAiStageProviderChange("report", e.target.value)}
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-2 py-1 text-xs"
                    >
                      <option value="">{aiRoutingInheritLabel("report")}</option>
                      {STAGE_PROVIDER_OPTIONS.report.map((provider) => (
                        <option key={provider} value={provider}>{provider}</option>
                      ))}
                    </select>
                  </div>
                </div>
                    {selectedAiProviders.length > 0 && (
                      <div className="space-y-3 pt-1">
                        {MODEL_PROVIDER_OPTIONS.filter((provider) => selectedAiProviders.includes(provider)).map((provider) => (
                          <div key={provider} className="grid grid-cols-1 md:grid-cols-3 gap-2">
                        <div className="space-y-1.5">
                          <label htmlFor={`monitor-ai-model-${provider}`} className="text-xs font-medium text-muted-foreground">{`模型 (${provider})`}</label>
                          <input
                            id={`monitor-ai-model-${provider}`}
                            aria-label={`Model for ${provider}`}
                            value={aiRouting.providers?.[provider]?.model ?? ""}
                            onChange={(e) => handleAiProviderConfigChange(provider, "model", e.target.value)}
                            placeholder="gpt-4o-mini"
                            className="h-9 w-full rounded-md border border-input bg-transparent px-2 text-xs"
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label htmlFor={`monitor-ai-timeout-${provider}`} className="text-xs font-medium text-muted-foreground">超时（秒）</label>
                          <input
                            id={`monitor-ai-timeout-${provider}`}
                            aria-label={`Timeout for ${provider}`}
                            type="number"
                            min={1}
                            value={typeof aiRouting.providers?.[provider]?.timeout_sec === "number" ? aiRouting.providers?.[provider]?.timeout_sec : ""}
                            onChange={(e) => handleAiProviderConfigChange(provider, "timeout_sec", e.target.value)}
                            placeholder="30"
                            className="h-9 w-full rounded-md border border-input bg-transparent px-2 text-xs"
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label htmlFor={`monitor-ai-retry-${provider}`} className="text-xs font-medium text-muted-foreground">最大重试次数</label>
                          <input
                            id={`monitor-ai-retry-${provider}`}
                            aria-label={`Max retry for ${provider}`}
                            type="number"
                            min={0}
                            value={typeof aiRouting.providers?.[provider]?.max_retry === "number" ? aiRouting.providers?.[provider]?.max_retry : ""}
                            onChange={(e) => handleAiProviderConfigChange(provider, "max_retry", e.target.value)}
                            placeholder="2"
                            className="h-9 w-full rounded-md border border-input bg-transparent px-2 text-xs"
                          />
                        </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">输出配置（可选）</label>
                <div className="max-h-40 overflow-y-auto border border-border/40 rounded-md p-2 space-y-1">
                  {destinations.filter(d => d.enabled).length === 0 && (
                    <div className="text-xs text-muted-foreground p-2">
                      当前没有任何激活的输出流配置，请前往“输出配置”页配置。
                    </div>
                  )}
                  {destinations.filter(d => d.enabled).map((dest) => (
                    <label key={dest.id} className="flex items-center gap-2 text-sm px-2 py-1.5 rounded hover:bg-muted/40 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedDestinationInstances.includes(dest.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedDestinationInstances((prev) => [...prev, dest.id]);
                          } else {
                            setSelectedDestinationInstances((prev) => prev.filter((id) => id !== dest.id));
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
                <p className="text-[10px] text-muted-foreground">选择将生成的洞察报告发送到何处。此处仅显示处于活动状态的配置。</p>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-border/40 flex items-center justify-end gap-3 shrink-0">
              <button onClick={closeModal} className="px-4 py-2 text-sm font-medium hover:bg-muted rounded-md transition-colors">
                取消
              </button>
              <button
                onClick={() => void handleSubmit()}
                disabled={!name || selectedSources.length === 0 || submitting}
                className="px-4 py-2 text-sm font-medium bg-foreground text-background hover:bg-foreground/90 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors"
              >
                {editingMonitorId ? submitting ? "保存中..." : "保存" : submitting ? "创建中..." : "创建"}
              </button>
            </div>
          </div>
        </div>
      )}

      {isLogsModalOpen && logsMonitor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={closeLogsModal} />
          <div
            data-testid="monitor-logs-modal"
            className="relative bg-card border border-border rounded-xl shadow-lg z-50 flex flex-col w-[96vw] max-w-[1800px] h-[90vh]"
          >
            <div className="px-6 py-4 border-b border-border/40 flex items-center justify-between shrink-0">
              <h2 className="text-xl font-semibold tracking-tight">Run History: {logsMonitor.name}</h2>
              <button
                onClick={closeLogsModal}
                className="text-muted-foreground hover:text-foreground p-1 rounded-md transition-colors"
              >
                ✕
              </button>
            </div>
            <div className="p-6 md:p-8 overflow-y-auto flex-1 min-h-0">
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
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-mono text-muted-foreground break-all">
                                {run.run_id.slice(0, 8)}... {run.articles_count} articles
                              </span>
                              {isActiveRunStatus(run.status) && (
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    void handleTerminateRunFromLogs(logsMonitor.id, run.run_id);
                                  }}
                                  disabled={Boolean(terminatingRunIds[run.run_id]) || run.status === "cancelling"}
                                  className="text-[11px] font-medium px-2 py-1 rounded border border-red-300 text-red-700 bg-red-50 hover:bg-red-100 disabled:opacity-60 disabled:cursor-not-allowed dark:border-red-700 dark:text-red-300 dark:bg-red-900/20 dark:hover:bg-red-900/30"
                                >
                                  {run.status === "cancelling" || terminatingRunIds[run.run_id] ? "Cancelling..." : "Terminate Run"}
                                </button>
                              )}
                            </div>
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
                        </div>

                        {isRunExpanded && (
                          <div className="border-t border-border/30 bg-neutral-950 rounded-b-lg overflow-hidden">
                            {runTrace.length === 0 ? (
                              <div className="px-4 py-3 text-xs text-neutral-500 font-mono">Loading events...</div>
                            ) : (
                              <div className="font-mono text-[12px] leading-relaxed max-h-[68vh] overflow-y-auto">
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
                                        <RunEventPayload payload={event.payload} />
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
