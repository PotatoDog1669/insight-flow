"use client";

import type { Dispatch, SetStateAction } from "react";
import { Plus, Settings2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { Destination, DestinationTestResponse, ObsidianVaultCandidate } from "@/lib/api";

import { DestinationDetailHeader } from "@/app/destinations/destination-detail-header";
import { DestinationFormSections } from "@/app/destinations/destination-form-sections";
import { DestinationOverviewSidebar } from "@/app/destinations/destination-overview-sidebar";

type DestinationDetailPanelProps = {
  activeDestination: Destination | null;
  detectedVaults: ObsidianVaultCandidate[];
  detectingVaultPath: boolean;
  editConfig: Record<string, string>;
  onCreate: () => void;
  onDelete: (destination: Destination) => void;
  onDetectObsidianVaultPath: () => void;
  onEnableToggle: (destination: Destination) => void;
  onSaveConfig: () => void;
  onTestConfig: () => void;
  setEditConfig: Dispatch<SetStateAction<Record<string, string>>>;
  submitting: boolean;
  testError: string | null;
  testResult: DestinationTestResponse | null;
  testingId: string | null;
  vaultDetectMessage: string | null;
};

export function DestinationDetailPanel({
  activeDestination,
  detectedVaults,
  detectingVaultPath,
  editConfig,
  onCreate,
  onDelete,
  onDetectObsidianVaultPath,
  onEnableToggle,
  onSaveConfig,
  onTestConfig,
  setEditConfig,
  submitting,
  testError,
  testResult,
  testingId,
  vaultDetectMessage,
}: DestinationDetailPanelProps) {
  if (!activeDestination) {
    return (
      <Card className="overflow-hidden border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.92))]">
        <CardContent className="flex min-h-[520px] items-center justify-center p-10">
          <div className="max-w-md text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-[24px] border border-dashed border-border/70 bg-muted/20 text-muted-foreground">
              <Settings2 className="h-6 w-6" />
            </div>
            <h2 className="text-xl font-semibold tracking-tight">还没有可编辑的落盘点</h2>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              新建一个实例后，就可以分别配置不同的 Notion 数据库、Obsidian 文件夹或 RSS 线路。
            </p>
            <Button type="button" className="mt-6 rounded-2xl" onClick={onCreate}>
              <Plus className="mr-2 h-4 w-4" />
              新增落盘点
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.92))]">
      <DestinationDetailHeader
        activeDestination={activeDestination}
        onDelete={onDelete}
        onEnableToggle={onEnableToggle}
        onSaveConfig={onSaveConfig}
        onTestConfig={onTestConfig}
        submitting={submitting}
        testingId={testingId}
      />

      <CardContent className="space-y-6 p-6">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
          <div className="space-y-6">
            <DestinationFormSections
              activeDestination={activeDestination}
              detectedVaults={detectedVaults}
              detectingVaultPath={detectingVaultPath}
              editConfig={editConfig}
              onDetectObsidianVaultPath={onDetectObsidianVaultPath}
              setEditConfig={setEditConfig}
              testError={testError}
              testResult={testResult}
              vaultDetectMessage={vaultDetectMessage}
            />
          </div>

          <DestinationOverviewSidebar activeDestination={activeDestination} editConfig={editConfig} />
        </div>
      </CardContent>
    </Card>
  );
}
