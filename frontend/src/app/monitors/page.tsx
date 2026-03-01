"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Play, Plus, Trash2, Activity, Clock, Server } from "lucide-react";
import {
  createMonitor,
  deleteMonitor,
  getMonitors,
  getSources,
  runMonitor,
  updateMonitor,
  type Monitor,
  type Source,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export default function MonitorsPage() {
  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [timePeriod, setTimePeriod] = useState<"daily" | "weekly" | "custom">("daily");
  const [depth, setDepth] = useState<"brief" | "deep">("brief");
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const sourceMap = useMemo(() => {
    const map = new Map<string, Source>();
    sources.forEach((source) => map.set(source.id, source));
    return map;
  }, [sources]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [monitorData, sourceData] = await Promise.all([getMonitors(), getSources()]);
      setMonitors(monitorData);
      setSources(sourceData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    if (sources.length > 0 && selectedSources.length === 0) {
      setSelectedSources([sources[0].id]);
    }
  }, [sources, selectedSources.length]);

  const resetForm = () => {
    setName("");
    setTimePeriod("daily");
    setDepth("brief");
    setSelectedSources(sources[0] ? [sources[0].id] : []);
  };

  const handleCreate = async () => {
    if (!name || selectedSources.length === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      await createMonitor({
        name,
        time_period: timePeriod,
        depth,
        source_ids: selectedSources,
        enabled: true,
      });
      setIsModalOpen(false);
      resetForm();
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create monitor failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRunNow = async (monitorId: string) => {
    try {
      await runMonitor(monitorId);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Run failed");
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
    <div className="max-w-5xl">
      <header className="mb-10 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-2">Monitors</h1>
          <p className="text-muted-foreground text-sm max-w-2xl">
            Configure automated research tasks and run them on demand.
          </p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
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
              className={cn(
                "border-border/40 hover:border-border/80 transition-all duration-300 shadow-sm hover:shadow-lg flex flex-col",
                !monitor.enabled && "opacity-70"
              )}
            >
              <CardHeader className="pb-3">
                <CardTitle className="text-lg font-semibold leading-snug">{monitor.name}</CardTitle>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <Badge variant="secondary" className="capitalize bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 border-none">
                    {monitor.time_period}
                  </Badge>
                  <Badge variant="secondary" className="capitalize bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 border-none">
                    {monitor.depth}
                  </Badge>
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

              <CardFooter className="pt-0 justify-between border-t border-border/40 pb-3 pt-3 mt-auto">
                <button
                  onClick={() => void handleToggle(monitor)}
                  className={cn(
                    "text-xs px-3 py-1.5 rounded-md transition-colors",
                    monitor.enabled
                      ? "bg-yellow-50 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300"
                      : "bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300"
                  )}
                >
                  {monitor.enabled ? "Pause" : "Resume"}
                </button>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => void handleRunNow(monitor.id)}
                    disabled={!monitor.enabled}
                    className="text-xs font-medium text-foreground bg-secondary hover:bg-secondary/80 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1.5 rounded-md transition-colors flex items-center"
                  >
                    <Play className="w-3.5 h-3.5 mr-1.5" />
                    Run
                  </button>
                  <button
                    onClick={() => void handleDelete(monitor.id)}
                    className="text-xs font-medium text-red-600 bg-red-50 hover:bg-red-100 dark:bg-red-900/30 dark:hover:bg-red-900/40 dark:text-red-300 px-3 py-1.5 rounded-md transition-colors flex items-center"
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
          <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={() => setIsModalOpen(false)} />
          <div className="relative bg-card border border-border rounded-xl shadow-lg w-full max-w-xl z-50">
            <div className="px-6 py-4 border-b border-border/40">
              <h2 className="text-xl font-semibold tracking-tight">Create Monitor</h2>
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
                  <label className="text-sm font-medium">Frequency</label>
                  <select
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
                  <label className="text-sm font-medium">Depth</label>
                  <select
                    value={depth}
                    onChange={(e) => setDepth(e.target.value as "brief" | "deep")}
                    className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                  >
                    <option value="brief">brief</option>
                    <option value="deep">deep</option>
                  </select>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Sources</label>
                <div className="max-h-40 overflow-y-auto border border-border/40 rounded-md p-2 space-y-1">
                  {sources.map((source) => (
                    <label key={source.id} className="flex items-center gap-2 text-sm px-2 py-1 rounded hover:bg-muted/40">
                      <input
                        type="checkbox"
                        checked={selectedSources.includes(source.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedSources((prev) => [...prev, source.id]);
                          } else {
                            setSelectedSources((prev) => prev.filter((id) => id !== source.id));
                          }
                        }}
                      />
                      <span>{source.name}</span>
                      <span className="text-xs text-muted-foreground">({source.category})</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-border/40 flex items-center justify-end gap-3">
              <button onClick={() => setIsModalOpen(false)} className="px-4 py-2 text-sm font-medium hover:bg-muted rounded-md transition-colors">
                Cancel
              </button>
              <button
                onClick={() => void handleCreate()}
                disabled={!name || selectedSources.length === 0 || submitting}
                className="px-4 py-2 text-sm font-medium bg-foreground text-background hover:bg-foreground/90 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors"
              >
                {submitting ? "Creating..." : "Create"}
              </button>
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
