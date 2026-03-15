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
        id: "llm_openai",
        name: "LLM OpenAI",
        type: "llm",
        description: "LLM executor for filter / keywords / report stages.",
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
      description: "LLM executor for filter / keywords / report stages.",
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
    expect(screen.getByText("统一管理工作流使用的 LLM 配置。后续 Agent 会走独立通道，不在这里配置。")).toBeInTheDocument();
    expect(screen.getByText("LLM OpenAI")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "配置" }));
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
});
