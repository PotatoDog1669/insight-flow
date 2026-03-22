import type { Destination } from "@/lib/api";

const NOTION_ID_PATTERN_GLOBAL =
  /([0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})/g;
const NOTION_ID_PATTERN_SINGLE =
  /([0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})/;

export type DestinationFilter = "all" | Destination["type"];

export const FILTER_OPTIONS: Array<{ value: DestinationFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "notion", label: "Notion" },
  { value: "obsidian", label: "Obsidian" },
  { value: "rss", label: "RSS" },
];

export function extractNotionId(value: string): string | null {
  const raw = value.trim();
  if (!raw) {
    return null;
  }

  try {
    const parsed = new URL(raw);
    if (parsed.hostname.toLowerCase().includes("notion.so")) {
      const pathMatches = Array.from(parsed.pathname.matchAll(NOTION_ID_PATTERN_GLOBAL));
      const fromPath = pathMatches[pathMatches.length - 1]?.[1];
      if (fromPath) {
        return fromPath.replaceAll("-", "").toLowerCase();
      }
      for (const key of ["database_id", "page_id", "id", "p", "block_id"]) {
        const candidate = parsed.searchParams.get(key);
        if (!candidate) {
          continue;
        }
        const queryMatch = candidate.match(NOTION_ID_PATTERN_SINGLE);
        if (queryMatch?.[1]) {
          return queryMatch[1].replaceAll("-", "").toLowerCase();
        }
      }
    }
  } catch {
    return raw.match(NOTION_ID_PATTERN_SINGLE)?.[1]?.replaceAll("-", "").toLowerCase() ?? null;
  }

  const match = raw.match(NOTION_ID_PATTERN_SINGLE);
  return match?.[1] ? match[1].replaceAll("-", "").toLowerCase() : null;
}

export function normalizeNotionField(value: string): string {
  return extractNotionId(value) ?? value.trim();
}

export function normalizeNotionConfig(config: Record<string, string>): Record<string, string> {
  return {
    ...config,
    database_id: normalizeNotionField(config.database_id || ""),
    parent_page_id: normalizeNotionField(config.parent_page_id || ""),
  };
}

export function getObsidianMode(config: Record<string, string>): "rest" | "file" {
  const mode = String(config.mode || "").trim().toLowerCase();
  if (mode === "file") {
    return "file";
  }
  if (mode === "rest") {
    return "rest";
  }
  return config.vault_path && !config.api_url ? "file" : "rest";
}

export function normalizeObsidianConfig(config: Record<string, string>): Record<string, string> {
  return {
    ...config,
    mode: getObsidianMode(config),
    api_url: String(config.api_url || "").trim().replace(/\/+$/, ""),
    api_key: String(config.api_key || "").trim(),
    vault_path: String(config.vault_path || "").trim(),
    target_folder: String(config.target_folder || "").trim(),
  };
}

export function normalizeRssConfig(config: Record<string, string>): Record<string, string | number> {
  const maxItems = Number.parseInt(String(config.max_items || "20"), 10);
  return {
    ...config,
    feed_url: String(config.feed_url || "").trim(),
    site_url: String(config.site_url || "").trim(),
    feed_title: String(config.feed_title || "").trim(),
    feed_description: String(config.feed_description || "").trim(),
    max_items: Number.isFinite(maxItems) ? maxItems : 20,
  };
}

export function buildInitialDestinationConfig(type: Destination["type"]): Record<string, unknown> {
  if (type === "notion") {
    return {
      token: "",
      database_id: "",
      parent_page_id: "",
      title_property: "Name",
      summary_property: "TL;DR",
      template_version: "v1",
    };
  }
  if (type === "obsidian") {
    return {
      mode: "rest",
      api_url: "https://127.0.0.1:27124",
      api_key: "",
      vault_path: "",
      target_folder: "AI Daily/",
    };
  }
  return {
    feed_url: "http://localhost:8000/api/v1/feed.xml",
    site_url: "http://localhost:3018",
    feed_title: "LexDeepResearch Reports",
    feed_description: "Latest generated reports from LexDeepResearch.",
    max_items: 20,
  };
}

export function getTypeLabel(type: Destination["type"]): string {
  if (type === "notion") {
    return "Notion";
  }
  if (type === "obsidian") {
    return "Obsidian";
  }
  return "RSS";
}

export function getDestinationDescription(destination: Destination): string {
  if (destination.type === "notion") {
    return "将报告同步到 Notion 数据库或页面，适合结构化归档和协作整理。";
  }
  if (destination.type === "obsidian") {
    return "将报告写入 Obsidian 仓库，或通过本地接口同步。";
  }
  return "生成可订阅的 RSS 输出，方便在阅读器里持续跟踪更新。";
}

export function getDestinationSummaryLabel(destination: Destination): string {
  if (destination.type === "notion") {
    return "写入目标";
  }
  if (destination.type === "obsidian") {
    return "目标位置";
  }
  return "订阅地址";
}

export function getDestinationSummary(destination: Destination): string {
  const config = destination.config as Record<string, unknown>;
  if (destination.type === "notion") {
    return String(config.database_id || config.parent_page_id || "未设置目标");
  }
  if (destination.type === "obsidian") {
    return String(config.target_folder || config.vault_path || config.api_url || "未设置目标目录");
  }
  return String(config.feed_url || "未生成订阅地址");
}

export function configToEditableStrings(config: Record<string, unknown>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(config ?? {}).map(([key, value]) => [key, typeof value === "string" ? value : String(value ?? "")]),
  );
}
