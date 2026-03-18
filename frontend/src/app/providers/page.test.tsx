import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import ProvidersPage from "@/app/providers/page";
import { getProviders, testProvider, updateProvider } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getProviders: vi.fn(),
    updateProvider: vi.fn(),
    testProvider: vi.fn(),
  };
});

const mockedGetProviders = vi.mocked(getProviders);
const mockedUpdateProvider = vi.mocked(updateProvider);
const mockedTestProvider = vi.mocked(testProvider);

describe("ProvidersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetProviders.mockResolvedValue([
      {
        id: "llm_codex",
        name: "LLM Codex",
        type: "llm",
        description: "用于 workflow 加工阶段的 Codex LLM 配置，与 OpenAI 共享同一套 prompts 和 workflow。",
        enabled: false,
        config: {
          base_url: "https://api.openai.com/v1",
          model: "gpt-5-codex",
          timeout_sec: 45,
          max_retry: 2,
          max_output_tokens: 2048,
          temperature: 0.3,
          api_key: "",
        },
      },
      {
        id: "llm_openai",
        name: "LLM OpenAI",
        type: "llm",
        description: "用于 workflow 加工阶段的 OpenAI LLM 配置，与 Codex 共享同一套 prompts 和 workflow。",
        enabled: true,
        config: {
          base_url: "https://api.openai.com/v1",
          model: "gpt-4o-mini",
          timeout_sec: 45,
          max_retry: 2,
          max_output_tokens: 2048,
          temperature: 0.3,
          api_key: "",
        },
      },
    ] as never);
    mockedUpdateProvider.mockResolvedValue({
      id: "llm_openai",
      name: "LLM OpenAI",
      type: "llm",
      description: "用于 workflow 加工阶段的 OpenAI LLM 配置，与 Codex 共享同一套 prompts 和 workflow。",
      enabled: true,
      config: {
        base_url: "https://api.openai.com/v1",
        model: "gpt-4o-mini",
        timeout_sec: 45,
        max_retry: 2,
        max_output_tokens: 2048,
        temperature: 0.3,
        api_key: "sk-live",
      },
    } as never);
    mockedTestProvider.mockResolvedValue({
      success: true,
      message: "Connection successful",
      latency_ms: 321,
      model: "gpt-4o-mini",
    } as never);
  });

  it("tests provider connectivity with the current edit config", async () => {
    render(<ProvidersPage />);

    await screen.findByRole("heading", { name: "模型配置" });
    expect(
      screen.getByText(/统一管理工作流使用的 LLM provider。OpenAI 与 Codex 复用同一套 prompts 和 workflow/)
    ).toBeInTheDocument();
    expect(screen.getByText("LLM Codex")).toBeInTheDocument();
    expect(screen.getByText("LLM OpenAI")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "配置" })[1]);
    fireEvent.change(screen.getByPlaceholderText("sk-..."), {
      target: { value: "sk-live" },
    });
    fireEvent.click(screen.getByRole("button", { name: "测试连接" }));

    await waitFor(() => {
      expect(mockedTestProvider).toHaveBeenCalledWith("llm_openai", {
        config: expect.objectContaining({
          base_url: "https://api.openai.com/v1",
          model: "gpt-4o-mini",
          api_key: "sk-live",
        }),
      });
    });

    expect(await screen.findByText("Connection successful")).toBeInTheDocument();
    expect(screen.getByText(/321 ms/i)).toBeInTheDocument();
  });

  it("toggles provider api key visibility while editing", async () => {
    render(<ProvidersPage />);

    await screen.findByRole("heading", { name: "模型配置" });

    fireEvent.click(screen.getAllByRole("button", { name: "配置" })[0]);

    const apiKeyInput = screen.getByPlaceholderText("sk-...");
    expect(apiKeyInput).toHaveAttribute("type", "password");

    fireEvent.click(screen.getByRole("button", { name: "显示 API Key" }));
    expect(apiKeyInput).toHaveAttribute("type", "text");

    fireEvent.click(screen.getByRole("button", { name: "隐藏 API Key" }));
    expect(apiKeyInput).toHaveAttribute("type", "password");
  });
});
