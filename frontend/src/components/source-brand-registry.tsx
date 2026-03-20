"use client";

import { type ReactElement, useMemo } from "react";
import { AppWindow, Building2, Code2, Cpu, Globe } from "lucide-react";
import {
  SiAnthropic,
  SiArxiv,
  SiBytedance,
  SiGithub,
  SiNotion,
  SiObsidian,
  SiOpenai,
  SiReddit,
  SiX,
  SiXiaohongshu,
} from "react-icons/si";

import type { Source } from "@/lib/api";
import { cn } from "@/lib/utils";

import { BilibiliIcon, DockerIcon, HuggingFaceIcon, MicrosoftIcon, ZhihuIcon } from "@/components/BrandIcons";

type BrandRule = {
  domain: string;
  exactNames?: string[];
  patterns?: string[];
  logoPath?: string;
  wide?: boolean;
  icon?: (name: string) => ReactElement;
};

const BRAND_RULES: BrandRule[] = [
  { domain: "openai.com", patterns: ["openai", "chatgpt"], logoPath: "/logos/openai.svg" },
  { domain: "deepmind.google", patterns: ["google deepmind", "deepmind"], logoPath: "/logos/google-deepmind.png" },
  { domain: "anthropic.com", patterns: ["anthropic", "claude"], logoPath: "/logos/anthropic.png" },
  { domain: "x.ai", patterns: ["xai", "x.ai"], logoPath: "/logos/xai.ico" },
  { domain: "ai.meta.com", patterns: ["meta ai", "meta"], logoPath: "/logos/meta-ai.ico" },
  { domain: "microsoft.com", patterns: ["microsoft"], logoPath: "/logos/microsoft.svg" },
  { domain: "nvidia.com", patterns: ["nvidia"], logoPath: "/logos/nvidia.ico" },
  { domain: "apple.com", patterns: ["apple"], logoPath: "/logos/apple.ico" },
  { domain: "amazon.science", patterns: ["amazon"], logoPath: "/logos/amazon-science.png" },
  { domain: "mistral.ai", patterns: ["mistral"], logoPath: "/logos/mistral-ai.ico" },
  { domain: "cohere.com", patterns: ["cohere"], logoPath: "/logos/cohere.png" },
  { domain: "ai21.com", patterns: ["ai21"], logoPath: "/logos/ai21.webp" },
  { domain: "stability.ai", patterns: ["stability"], logoPath: "/logos/stability-ai.webp" },
  { domain: "qwen.ai", patterns: ["qwen"], logoPath: "/logos/alibaba-qwen.png" },
  { domain: "tencent.com", patterns: ["hunyuan", "腾讯"], logoPath: "/logos/tencent.png" },
  {
    domain: "bytedance.com",
    patterns: ["bytedance", "字节"],
    icon: (name) => <SiBytedance role="img" aria-label={`${name} logo`} className="h-5 w-5 text-[#1B6DFF]" />,
  },
  { domain: "meituan.com", patterns: ["美团", "longcat"], logoPath: "/logos/meituan.ico" },
  { domain: "kuaishou.com", patterns: ["kuaikat", "快手", "kwai"], logoPath: "/logos/kuaishou.ico" },
  { domain: "mi.com", patterns: ["xiaomi", "小米"], logoPath: "/logos/xiaomi.ico" },
  {
    domain: "xiaohongshu.com",
    patterns: ["小红书", "xiaohongshu"],
    icon: (name) => <SiXiaohongshu role="img" aria-label={`${name} logo`} className="h-5 w-5 text-[#FF2442]" />,
  },
  { domain: "baidu.com", patterns: ["baidu", "ernie", "百度"], logoPath: "/logos/baidu.png" },
  { domain: "huawei.com", patterns: ["huawei", "华为", "盘古"], logoPath: "/logos/huawei.png" },
  { domain: "sensetime.com", patterns: ["sensenova", "sensetime", "商汤"], logoPath: "/logos/sensetime.ico" },
  { domain: "xfyun.cn", patterns: ["讯飞", "xfyun", "星火"], logoPath: "/logos/xfyun.ico" },
  { domain: "deepseek.com", patterns: ["deepseek"], logoPath: "/logos/deepseek.ico" },
  { domain: "z.ai", patterns: ["z.ai", "zhipu", "智谱"], logoPath: "/logos/z-ai.svg" },
  { domain: "moonshot.cn", patterns: ["moonshot", "kimi"], logoPath: "/logos/moonshot.ico" },
  { domain: "minimax.io", patterns: ["minimax"], logoPath: "/logos/minimax.ico" },
  { domain: "stepfun.com", patterns: ["stepfun", "阶跃"], logoPath: "/logos/stepfun.png" },
  { domain: "baichuan-ai.com", patterns: ["baichuan", "百川"], logoPath: "/logos/baichuan-ai.png" },
  { domain: "01.ai", patterns: ["01.ai", "零一万物", "lingyi"], logoPath: "/logos/01-ai.png" },
  { domain: "modelbest.cn", patterns: ["minicpm", "openbmb", "面壁"], logoPath: "/logos/modelbest.png" },
  { domain: "perplexity.ai", patterns: ["perplexity"], logoPath: "/logos/perplexity.svg" },
  { domain: "nousresearch.com", patterns: ["nous"], logoPath: "/logos/nousresearch.png" },
  { domain: "cursor.com", patterns: ["cursor"], logoPath: "/logos/cursor.png" },
  { domain: "cognition.ai", patterns: ["cognition", "devin"], logoPath: "/logos/cognition.png" },
  { domain: "huggingface.co", patterns: ["huggingface", "hugging face"], logoPath: "/logos/huggingface.svg" },
  { domain: "together.ai", patterns: ["together"], logoPath: "/logos/together-ai.png" },
  { domain: "fireworks.ai", patterns: ["fireworks"], logoPath: "/logos/fireworks-ai.ico" },
  { domain: "groq.com", patterns: ["groq"], logoPath: "/logos/groq.ico" },
  { domain: "arxiv.org", patterns: ["arxiv"], logoPath: "/logos/arxiv.svg" },
  { domain: "europepmc.org", patterns: ["europe pmc", "europepmc"], logoPath: "/logos/europe-pmc-logo.png", wide: true },
  { domain: "pubmed.ncbi.nlm.nih.gov", patterns: ["pubmed"], logoPath: "/logos/pubmed-logo.svg", wide: true },
  { domain: "openalex.org", patterns: ["openalex"], logoPath: "/logos/openalex.svg", wide: true },
  { domain: "x.com", exactNames: ["x"], patterns: ["twitter"], logoPath: "/logos/x.svg" },
  { domain: "reddit.com", patterns: ["reddit"], logoPath: "/logos/reddit.svg" },
];

function asObject(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function findBrandRuleByName(name: string): BrandRule | null {
  const normalized = name.trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  for (const rule of BRAND_RULES) {
    if (rule.exactNames?.includes(normalized)) {
      return rule;
    }
    if (rule.patterns?.some((pattern) => normalized.includes(pattern))) {
      return rule;
    }
  }
  return null;
}

function parseHostname(rawUrl: string): string | null {
  const normalized = rawUrl.startsWith("http://") || rawUrl.startsWith("https://") ? rawUrl : `https://${rawUrl}`;
  try {
    const { hostname } = new URL(normalized);
    return hostname ? hostname.replace(/^www\./, "").toLowerCase() : null;
  } catch {
    return null;
  }
}

function getConfigUrlCandidates(source: Source): string[] {
  const config = asObject(source.config) ?? {};
  const candidates: string[] = [];
  const push = (value: unknown): void => {
    const raw = asString(value);
    if (raw) {
      candidates.push(raw);
    }
  };
  const pushArray = (value: unknown): void => {
    if (!Array.isArray(value)) {
      return;
    }
    for (const item of value) {
      push(item);
    }
  };

  push(config.feed_url);
  push(config.url);
  pushArray(config.urls);
  pushArray(config.start_urls);
  pushArray(config.github_repo_urls);

  const profile = asObject(config.profile);
  if (profile) {
    pushArray(profile.start_urls);
  }

  if (source.collect_method === "twitter_snaplytics") {
    push("https://x.com");
  }
  if (source.collect_method === "huggingface") {
    push("https://huggingface.co");
  }
  if (source.collect_method === "github_trending") {
    push("https://github.com");
  }

  return candidates;
}

function resolveBrandRule(source: Source): BrandRule | null {
  const nameMatch = findBrandRuleByName(source.name);
  if (nameMatch) {
    return nameMatch;
  }
  for (const candidate of getConfigUrlCandidates(source)) {
    const hostname = parseHostname(candidate);
    if (!hostname) {
      continue;
    }
    for (const rule of BRAND_RULES) {
      if (hostname === rule.domain || hostname.endsWith(`.${rule.domain}`)) {
        return rule;
      }
    }
  }
  return null;
}

function getSourceIconFallback(name: string, category: string) {
  const normalized = name.toLowerCase();

  if (normalized.includes("openai") || normalized.includes("chatgpt")) {
    return <SiOpenai className="h-5 w-5 text-foreground" />;
  }
  if (normalized.includes("anthropic") || normalized.includes("claude")) {
    return <SiAnthropic className="h-5 w-5 text-orange-600 dark:text-orange-400" />;
  }
  if (normalized.includes("github")) {
    return <SiGithub className="h-5 w-5 text-foreground" />;
  }
  if (normalized.includes("huggingface") || normalized.includes("hugging")) {
    return <HuggingFaceIcon className="h-5 w-5 flex-shrink-0" />;
  }
  if (normalized === "x" || normalized.includes("twitter") || normalized.includes("x ") || normalized.includes("xai")) {
    return <SiX className="h-4 w-4 text-foreground" />;
  }
  if (normalized.includes("reddit")) {
    return <SiReddit className="h-5 w-5 text-[#FF4500]" />;
  }
  if (normalized.includes("arxiv")) {
    return <SiArxiv className="h-5 w-5 text-red-600 dark:text-red-400" />;
  }
  if (normalized.includes("bilibili") || normalized.includes("b站")) {
    return <BilibiliIcon className="h-5 w-5 text-[#00AEEC]" />;
  }
  if (normalized.includes("notion")) {
    return <SiNotion className="h-5 w-5 text-foreground" />;
  }
  if (normalized.includes("obsidian")) {
    return <SiObsidian className="h-5 w-5 text-violet-600 dark:text-violet-400" />;
  }
  if (normalized.includes("zhihu") || normalized.includes("知乎")) {
    return <ZhihuIcon className="h-5 w-5 text-[#0066FF]" />;
  }
  if (normalized.includes("microsoft") || normalized.includes("微软")) {
    return <MicrosoftIcon className="h-5 w-5 text-[#00A4EF]" />;
  }
  if (normalized.includes("docker")) {
    return <DockerIcon className="h-5 w-5 text-[#2496ED]" />;
  }
  if (normalized.includes("google")) {
    return <Globe className="h-5 w-5 text-[#4285F4]" />;
  }
  if (normalized.includes("meta")) {
    return <Globe className="h-5 w-5 text-[#0668E1]" />;
  }
  if (normalized.includes("apple") || normalized.includes("苹果")) {
    return <Globe className="h-5 w-5 text-foreground" />;
  }

  if (category === "open_source") {
    return <Code2 className="h-5 w-5 text-purple-500" />;
  }
  if (category === "academic") {
    return <SiArxiv className="h-5 w-5 text-emerald-500" />;
  }
  if (
    normalized.includes("deepseek") ||
    normalized.includes("零一万物") ||
    normalized.includes("智谱") ||
    normalized.includes("moonshot") ||
    normalized.includes("kimi") ||
    normalized.includes("mistral") ||
    normalized.includes("cohere")
  ) {
    return <Cpu className="h-5 w-5 text-indigo-500" />;
  }
  if (
    normalized.includes("华为") ||
    normalized.includes("腾讯") ||
    normalized.includes("字节") ||
    normalized.includes("阿里") ||
    normalized.includes("小米") ||
    normalized.includes("快手") ||
    normalized.includes("amazon") ||
    normalized.includes("百度") ||
    normalized.includes("美团")
  ) {
    return <Building2 className="h-5 w-5 text-blue-500" />;
  }
  if (
    normalized.includes("cursor") ||
    normalized.includes("langchain") ||
    normalized.includes("vercel") ||
    normalized.includes("cloudflare") ||
    normalized.includes("vllm") ||
    normalized.includes("llamaindex")
  ) {
    return <Code2 className="h-5 w-5 text-orange-500" />;
  }
  if (
    normalized.includes("midjourney") ||
    normalized.includes("runway") ||
    normalized.includes("perplexity") ||
    normalized.includes("cognition") ||
    normalized.includes("devin")
  ) {
    return <AppWindow className="h-5 w-5 text-pink-500" />;
  }

  return <Globe className="h-5 w-5 text-muted-foreground" />;
}

function usesWideBrandLogo(source: Source): boolean {
  return Boolean(resolveBrandRule(source)?.wide);
}

function getLogoImageClassName(source: Source): string {
  return usesWideBrandLogo(source)
    ? "h-5 w-auto max-w-full object-contain"
    : "h-5 w-5 rounded-sm object-contain";
}

export function getLogoFrameClassName(source: Source): string {
  return cn(
    "flex h-8 shrink-0 items-center rounded-lg border border-border/50 bg-background/50 shadow-sm",
    usesWideBrandLogo(source) ? "w-14 justify-start px-1.5" : "w-8 justify-center",
  );
}

export function SourceLogo({ source }: { source: Source }) {
  const brandRule = useMemo(() => resolveBrandRule(source), [source]);
  if (brandRule?.icon) {
    return brandRule.icon(source.name);
  }
  if ((source.category === "blog" || source.category === "academic" || source.category === "social") && brandRule?.logoPath) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={brandRule.logoPath}
        alt={`${source.name} logo`}
        className={getLogoImageClassName(source)}
        loading="lazy"
        decoding="async"
      />
    );
  }
  return getSourceIconFallback(source.name, source.category);
}
