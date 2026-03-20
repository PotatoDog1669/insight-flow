"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  createDestination,
  deleteDestination,
  discoverObsidianVaults,
  getDestinations,
  testDestination,
  updateDestination,
  type Destination,
  type DestinationTestResponse,
  type ObsidianVaultCandidate,
} from "@/lib/api";

import { DestinationDetailPanel } from "@/app/destinations/destination-detail-panel";
import { DestinationListPanel } from "@/app/destinations/destination-list-panel";
import { CreateDestinationModal, DeleteDestinationModal } from "@/app/destinations/destination-modals";
import {
  buildInitialDestinationConfig,
  configToEditableStrings,
  normalizeNotionConfig,
  normalizeObsidianConfig,
  normalizeRssConfig,
  type DestinationFilter,
} from "@/app/destinations/utils";

export default function DestinationsPage() {
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeDestinationId, setActiveDestinationId] = useState<string | null>(null);
  const [filter, setFilter] = useState<DestinationFilter>("all");
  const [editConfig, setEditConfig] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<DestinationTestResponse | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [detectingVaultPath, setDetectingVaultPath] = useState(false);
  const [detectedVaults, setDetectedVaults] = useState<ObsidianVaultCandidate[]>([]);
  const [vaultDetectMessage, setVaultDetectMessage] = useState<string | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [createType, setCreateType] = useState<Destination["type"]>("notion");
  const [createName, setCreateName] = useState("");
  const [creating, setCreating] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Destination | null>(null);
  const [deleting, setDeleting] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDestinations();
      setDestinations(data || []);
      setActiveDestinationId((current) => current ?? data[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载落盘点失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filteredDestinations = useMemo(() => {
    if (filter === "all") {
      return destinations;
    }
    return destinations.filter((destination) => destination.type === filter);
  }, [destinations, filter]);

  useEffect(() => {
    if (!filteredDestinations.length) {
      setActiveDestinationId(null);
      return;
    }
    if (!activeDestinationId || !filteredDestinations.some((item) => item.id === activeDestinationId)) {
      setActiveDestinationId(filteredDestinations[0].id);
    }
  }, [activeDestinationId, filteredDestinations]);

  const activeDestination = useMemo(
    () => destinations.find((destination) => destination.id === activeDestinationId) ?? null,
    [activeDestinationId, destinations],
  );

  useEffect(() => {
    if (!activeDestination) {
      setEditConfig({});
      return;
    }
    const normalized = configToEditableStrings(activeDestination.config ?? {});
    setEditConfig(activeDestination.type === "obsidian" ? normalizeObsidianConfig(normalized) : normalized);
    setTestResult(null);
    setTestError(null);
    setDetectedVaults([]);
    setVaultDetectMessage(null);
  }, [activeDestination]);

  const handleEnableToggle = async (destination: Destination) => {
    const nextEnabled = !destination.enabled;
    setError(null);
    setDestinations((current) =>
      current.map((item) => (item.id === destination.id ? { ...item, enabled: nextEnabled } : item)),
    );
    try {
      await updateDestination(destination.id, { enabled: nextEnabled });
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新启用状态失败");
      void loadData();
    }
  };

  const handleSaveConfig = async () => {
    if (!activeDestination) {
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const normalizedConfig =
        activeDestination.type === "notion"
          ? normalizeNotionConfig(editConfig)
          : activeDestination.type === "obsidian"
            ? normalizeObsidianConfig(editConfig)
            : normalizeRssConfig(editConfig);
      const updated = await updateDestination(activeDestination.id, {
        config: normalizedConfig,
        enabled: true,
      });
      setDestinations((current) =>
        current.map((item) => (item.id === activeDestination.id ? { ...updated, enabled: true } : item)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存落盘点配置失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleTestConfig = async () => {
    if (!activeDestination) {
      return;
    }
    setTestingId(activeDestination.id);
    setTestResult(null);
    setTestError(null);
    try {
      const configPayload =
        activeDestination.type === "notion"
          ? normalizeNotionConfig(editConfig)
          : activeDestination.type === "obsidian"
            ? normalizeObsidianConfig(editConfig)
            : normalizeRssConfig(editConfig);
      const result = await testDestination(activeDestination.id, { config: configPayload });
      setTestResult(result);
    } catch (err) {
      setTestError(err instanceof Error ? err.message : "测试连接失败");
    } finally {
      setTestingId(null);
    }
  };

  const handleCreateDestination = async () => {
    const normalizedName = createName.trim();
    if (!normalizedName) {
      return;
    }

    setCreating(true);
    setError(null);
    try {
      const created = await createDestination({
        type: createType,
        name: normalizedName,
        enabled: false,
        config: buildInitialDestinationConfig(createType),
      });
      setDestinations((current) => [...current, created]);
      setActiveDestinationId(created.id);
      setFilter("all");
      setCreateName("");
      setCreateType("notion");
      setIsCreateModalOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "新增落盘点失败");
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteDestination = async () => {
    if (!deleteTarget) {
      return;
    }
    setDeleting(true);
    setError(null);
    try {
      await deleteDestination(deleteTarget.id);
      setDestinations((current) => current.filter((item) => item.id !== deleteTarget.id));
      if (activeDestinationId === deleteTarget.id) {
        setActiveDestinationId(null);
      }
      setDeleteTarget(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除落盘点失败");
    } finally {
      setDeleting(false);
    }
  };

  const handleDetectObsidianVaultPath = async () => {
    setDetectingVaultPath(true);
    setVaultDetectMessage(null);
    try {
      const result = await discoverObsidianVaults();
      setDetectedVaults(result.vaults || []);
      setVaultDetectMessage(result.message);
      if (result.detected_path) {
        setEditConfig((current) => ({ ...current, vault_path: result.detected_path || "" }));
      }
    } catch (err) {
      setDetectedVaults([]);
      setVaultDetectMessage(err instanceof Error ? err.message : "自动检测失败，请手动填写路径");
    } finally {
      setDetectingVaultPath(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-3">
          <Badge variant="outline" className="rounded-full border-sky-200 bg-sky-50 px-3 py-1 text-sky-700">
            多实例落盘管理
          </Badge>
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-slate-950">输出配置</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              为不同任务维护不同的 Notion、Obsidian 和 RSS 落盘点。左边选实例，右边直接调整配置与目标目录。
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="rounded-2xl border border-border/70 bg-card/80 px-4 py-3 text-sm text-muted-foreground">
            已配置 <span className="font-semibold text-foreground">{destinations.length}</span> 个落盘点
          </div>
          <Button type="button" className="rounded-2xl px-5" onClick={() => setIsCreateModalOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            新增落盘点
          </Button>
        </div>
      </div>

      {error ? (
        <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">{error}</div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
        <DestinationListPanel
          activeDestinationId={activeDestinationId}
          filter={filter}
          filteredDestinations={filteredDestinations}
          loading={loading}
          onFilterChange={setFilter}
          onSelect={setActiveDestinationId}
        />
        <DestinationDetailPanel
          activeDestination={activeDestination}
          detectedVaults={detectedVaults}
          detectingVaultPath={detectingVaultPath}
          editConfig={editConfig}
          onCreate={() => setIsCreateModalOpen(true)}
          onDelete={setDeleteTarget}
          onDetectObsidianVaultPath={() => void handleDetectObsidianVaultPath()}
          onEnableToggle={(destination) => void handleEnableToggle(destination)}
          onSaveConfig={() => void handleSaveConfig()}
          onTestConfig={() => void handleTestConfig()}
          setEditConfig={setEditConfig}
          submitting={submitting}
          testError={testError}
          testResult={testResult}
          testingId={testingId}
          vaultDetectMessage={vaultDetectMessage}
        />
      </div>

      <CreateDestinationModal
        createName={createName}
        createType={createType}
        creating={creating}
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreate={() => void handleCreateDestination()}
        onNameChange={setCreateName}
        onTypeChange={setCreateType}
      />
      <DeleteDestinationModal
        deleting={deleting}
        destination={deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onDelete={() => void handleDeleteDestination()}
      />
    </div>
  );
}
