const BLOG_GROUPS = [
  "Top AI Labs & Startups",
  "Tech Giants",
  "AI Infra & Tools",
  "AI Applications & Products",
  "Other",
] as const;

export type BlogGroup = (typeof BLOG_GROUPS)[number];

const BLOG_GROUP_RULES: Array<{ group: Exclude<BlogGroup, "Other">; patterns: string[] }> = [
  {
    group: "Top AI Labs & Startups",
    patterns: [
      "openai",
      "deepseek",
      "anthropic",
      "零一万物",
      "01.ai",
      "智谱",
      "z.ai",
      "moonshot",
      "kimi",
      "xai",
      "mistral",
      "cohere",
      "minimax",
      "阶跃",
      "stepfun",
      "百川",
      "面壁",
      "minicpm",
      "nous",
      "科大讯飞",
      "星火",
      "商汤",
      "sensenova",
      "ai21",
      "stability",
    ],
  },
  {
    group: "Tech Giants",
    patterns: [
      "google",
      "meta",
      "microsoft",
      "apple",
      "华为",
      "盘古",
      "腾讯",
      "hunyuan",
      "字节",
      "bytedance",
      "seed",
      "阿里",
      "qwen",
      "alibaba",
      "小米",
      "mimo",
      "快手",
      "kwaikat",
      "amazon",
      "aws",
      "美团",
      "longcat",
      "百度",
      "ernie",
    ],
  },
  {
    group: "AI Infra & Tools",
    patterns: [
      "nvidia",
      "hugging",
      "cursor",
      "langchain",
      "vercel",
      "supabase",
      "cloudflare",
      "docker",
      "github",
      "gitlab",
      "vllm",
      "llamaindex",
      "fireworks",
      "groq",
      "together",
    ],
  },
  {
    group: "AI Applications & Products",
    patterns: ["midjourney", "runway", "perplexity", "notion", "小红书", "bilibili", "知乎", "cognition", "devin"],
  },
];

export { BLOG_GROUPS };

export function getOrganizationCategory(name: string): BlogGroup {
  const normalized = name.toLowerCase();
  const matched = BLOG_GROUP_RULES.find((rule) => rule.patterns.some((pattern) => normalized.includes(pattern)));
  return matched?.group ?? "Other";
}
