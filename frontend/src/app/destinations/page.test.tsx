import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import DestinationsPage from "@/app/destinations/page";
import {
  createDestination,
  deleteDestination,
  discoverObsidianVaults,
  getDestinations,
  testDestination,
  updateDestination,
} from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    createDestination: vi.fn(),
    deleteDestination: vi.fn(),
    discoverObsidianVaults: vi.fn(),
    getDestinations: vi.fn(),
    testDestination: vi.fn(),
    updateDestination: vi.fn(),
  };
});

const mockedCreateDestination = vi.mocked(createDestination);
const mockedDeleteDestination = vi.mocked(deleteDestination);
const mockedDiscoverObsidianVaults = vi.mocked(discoverObsidianVaults);
const mockedGetDestinations = vi.mocked(getDestinations);
const mockedTestDestination = vi.mocked(testDestination);
const mockedUpdateDestination = vi.mocked(updateDestination);

const destinationFixtures = [
  {
    id: "notion",
    name: "Notion",
    type: "notion",
    description: "同步报告到 Notion 数据库。",
    enabled: true,
    config: {
      token: "secret_notion_token",
      database_id: "db123",
      title_property: "Name",
      summary_property: "TL;DR",
    },
  },
  {
    id: "obsidian",
    name: "Obsidian",
    type: "obsidian",
    description: "同步报告到本地 Obsidian。",
    enabled: false,
    config: {
      mode: "rest",
      api_url: "https://127.0.0.1:27124",
      api_key: "obsidian-secret-key",
      target_folder: "AI-Reports/",
    },
  },
] as const;

async function waitForDestinationButtons() {
  await screen.findByRole("button", { name: "Notion 落盘点" });
  return screen.findByRole("button", { name: "Obsidian 落盘点" });
}

describe("DestinationsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedCreateDestination.mockResolvedValue({
      id: "rss-main",
      name: "RSS 主线",
      type: "rss",
      description: "同步报告到 RSS 订阅源。",
      enabled: false,
      config: {
        feed_url: "http://localhost:8000/api/v1/feed.xml",
      },
    } as never);
    mockedDeleteDestination.mockResolvedValue(undefined as never);
    mockedDiscoverObsidianVaults.mockResolvedValue({
      success: true,
      message: "Detected current Obsidian vault.",
      detected_path: "/Users/leo/Documents/Obsidian Vault",
      vaults: [
        {
          path: "/Users/leo/Documents/Obsidian Vault",
          name: "Obsidian Vault",
          open: true,
        },
      ],
    } as never);
    mockedGetDestinations.mockResolvedValue([...destinationFixtures] as never);
    mockedTestDestination.mockResolvedValue({
      success: true,
      message: "Obsidian REST API reachable",
      latency_ms: 27,
      mode: "rest",
      checked_target: "https://127.0.0.1:27124",
    } as never);
    mockedUpdateDestination.mockImplementation(async (id, payload) => {
      const destination = destinationFixtures.find((item) => item.id === id);
      if (!destination) {
        throw new Error(`unknown destination ${id}`);
      }

      return {
        ...destination,
        ...payload,
        config: payload.config ?? destination.config,
      } as never;
    });
  });

  it("renders a destination list and a separate detail panel", async () => {
    render(<DestinationsPage />);

    await waitForDestinationButtons();

    expect(screen.getByText("落盘点列表")).toBeInTheDocument();
    expect(screen.getByText("连接详情")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Notion 落盘点" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Obsidian 落盘点" })).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));

    expect(screen.getByRole("button", { name: "Obsidian 落盘点" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("heading", { name: "Obsidian" })).toBeInTheDocument();
    expect(screen.getByText("将报告写入 Obsidian 仓库，或通过本地接口同步。")).toBeInTheDocument();
    expect(screen.queryByText("当前概览")).not.toBeInTheDocument();
    expect(screen.queryByText("使用建议")).not.toBeInTheDocument();
  });

  it("renders localized destination detail copy without english helper text", async () => {
    render(<DestinationsPage />);

    await waitForDestinationButtons();

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));

    expect(screen.getByText("将报告写入 Obsidian 仓库，或通过本地接口同步。")).toBeInTheDocument();
    expect(screen.queryByText("Write markdown to your Obsidian vault or REST bridge.")).not.toBeInTheDocument();
  });

  it("uses a compact action area instead of the old status card", async () => {
    render(<DestinationsPage />);

    await waitForDestinationButtons();

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));

    expect(screen.queryByText("启用状态")).not.toBeInTheDocument();
    expect(screen.queryByText("当前已启用")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "启用落盘点" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "编辑配置" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "删除" })).toBeInTheDocument();
  });

  it("renders target position under the compact action buttons", async () => {
    render(<DestinationsPage />);

    await waitForDestinationButtons();

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));

    const actionArea = screen.getByTestId("destination-actions");
    expect(within(actionArea).getByText("目标位置: AI-Reports/")).toBeInTheDocument();
  });

  it("shows destination details in readonly mode until entering edit mode", async () => {
    render(<DestinationsPage />);

    await waitForDestinationButtons();

    const notionNameInput = screen.getByLabelText("实例名称");
    expect(notionNameInput).toHaveAttribute("readonly");
    expect(screen.getByRole("button", { name: "编辑配置" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "保存并启用" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));
    fireEvent.click(screen.getByRole("button", { name: "编辑配置" }));

    expect(screen.getByRole("button", { name: "取消" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "测试连接" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存并启用" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("实例名称"), {
      target: { value: "Workspace Obsidian" },
    });
    expect(screen.getByLabelText("实例名称")).toHaveValue("Workspace Obsidian");
  });

  it("keeps editable secret inputs hidden by default and reveals them on demand", async () => {
    render(<DestinationsPage />);

    await waitForDestinationButtons();

    fireEvent.click(screen.getByRole("button", { name: "编辑配置" }));

    const notionTokenInput = screen.getByPlaceholderText("secret_...");
    expect(notionTokenInput).toHaveAttribute("type", "password");

    fireEvent.click(screen.getByRole("button", { name: "显示 集成令牌 (Token)" }));
    expect(notionTokenInput).toHaveAttribute("type", "text");

    fireEvent.click(screen.getByRole("button", { name: "隐藏 集成令牌 (Token)" }));
    expect(notionTokenInput).toHaveAttribute("type", "password");

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));
    fireEvent.click(screen.getByRole("button", { name: "编辑配置" }));

    expect(screen.getByRole("radio", { name: /^REST API/ })).toBeChecked();

    const obsidianApiKeyInput = screen.getByPlaceholderText("来自 Obsidian 本地 REST API 设置");
    expect(obsidianApiKeyInput).toHaveAttribute("type", "password");

    fireEvent.click(screen.getByRole("button", { name: "显示 API Key" }));
    expect(obsidianApiKeyInput).toHaveAttribute("type", "text");

    fireEvent.click(screen.getByRole("button", { name: "隐藏 API Key" }));
    expect(obsidianApiKeyInput).toHaveAttribute("type", "password");
  }, 30000);

  it("tests obsidian connectivity with the current edit config", async () => {
    render(<DestinationsPage />);

    await waitForDestinationButtons();

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));
    fireEvent.click(screen.getByRole("button", { name: "编辑配置" }));
    fireEvent.change(screen.getByPlaceholderText("https://127.0.0.1:27124"), {
      target: { value: "https://127.0.0.1:27124/" },
    });
    fireEvent.change(screen.getByPlaceholderText("例如：AI Daily/"), {
      target: { value: "Daily Notes/" },
    });

    fireEvent.click(screen.getByRole("button", { name: "测试连接" }));

    await waitFor(() => {
      expect(mockedTestDestination).toHaveBeenCalledWith("obsidian", {
        config: expect.objectContaining({
          mode: "rest",
          api_url: "https://127.0.0.1:27124",
          api_key: "obsidian-secret-key",
          target_folder: "Daily Notes/",
        }),
      });
    });

    expect(await screen.findByText("Obsidian REST API reachable")).toBeInTheDocument();
    expect(screen.getByText(/27 ms/i)).toBeInTheDocument();
  });

  it("switches obsidian editor to file mode and only shows file fields", async () => {
    render(<DestinationsPage />);

    await waitForDestinationButtons();

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));
    fireEvent.click(screen.getByRole("button", { name: "编辑配置" }));
    fireEvent.click(screen.getByRole("radio", { name: /^本地文件/ }));

    expect(screen.getByRole("radio", { name: /^本地文件/ })).toBeChecked();
    expect(screen.getByPlaceholderText("/Users/leo/Documents/MyVault")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("https://127.0.0.1:27124")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("来自 Obsidian 本地 REST API 设置")).not.toBeInTheDocument();
  });

  it("detects the local obsidian vault path in file mode", async () => {
    render(<DestinationsPage />);

    await waitForDestinationButtons();

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));
    fireEvent.click(screen.getByRole("button", { name: "编辑配置" }));
    fireEvent.click(screen.getByRole("radio", { name: /^本地文件/ }));
    fireEvent.click(screen.getByRole("button", { name: "自动检测路径" }));

    await waitFor(() => {
      expect(mockedDiscoverObsidianVaults).toHaveBeenCalled();
    });

    expect(await screen.findByDisplayValue("/Users/leo/Documents/Obsidian Vault")).toBeInTheDocument();
    expect(screen.getByText("Detected current Obsidian vault.")).toBeInTheDocument();
  });

  it("keeps vault auto-detection available in readonly file mode", async () => {
    mockedGetDestinations.mockResolvedValue([
      destinationFixtures[0],
      {
        ...destinationFixtures[1],
        config: {
          mode: "file",
          vault_path: "/Users/leo/Documents/Obsidian Vault",
          target_folder: "AI Daily",
        },
      },
    ] as never);

    render(<DestinationsPage />);

    await waitForDestinationButtons();

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));

    expect(screen.getByRole("button", { name: "自动检测路径" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "测试连接" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "自动检测路径" }));

    await waitFor(() => {
      expect(mockedDiscoverObsidianVaults).toHaveBeenCalled();
    });

    expect(await screen.findByDisplayValue("/Users/leo/Documents/Obsidian Vault")).toBeInTheDocument();
    expect(screen.getByText("Detected current Obsidian vault.")).toBeInTheDocument();
  });

  it("allows renaming a destination instance and saves the new name", async () => {
    render(<DestinationsPage />);

    await waitForDestinationButtons();

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));
    fireEvent.click(screen.getByRole("button", { name: "编辑配置" }));
    fireEvent.change(screen.getByLabelText("实例名称"), {
      target: { value: "Paper Daily" },
    });

    fireEvent.click(screen.getByRole("button", { name: "保存并启用" }));

    await waitFor(() => {
      expect(mockedUpdateDestination).toHaveBeenCalledWith(
        "obsidian",
        expect.objectContaining({
          name: "Paper Daily",
          enabled: true,
        }),
      );
    });

    expect(await screen.findByRole("heading", { name: "Paper Daily" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Paper Daily 落盘点" })).toBeInTheDocument();
  });

  it("cancels unsaved edits and restores the saved destination state", async () => {
    render(<DestinationsPage />);

    await waitForDestinationButtons();

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));
    fireEvent.click(screen.getByRole("button", { name: "编辑配置" }));
    fireEvent.change(screen.getByLabelText("实例名称"), {
      target: { value: "Paper Daily" },
    });
    fireEvent.change(screen.getByPlaceholderText("https://127.0.0.1:27124"), {
      target: { value: "https://localhost:27124/" },
    });

    fireEvent.click(screen.getByRole("button", { name: "取消" }));

    expect(mockedUpdateDestination).not.toHaveBeenCalled();
    expect(screen.getByLabelText("实例名称")).toHaveValue("Obsidian");
    expect(screen.getByLabelText("实例名称")).toHaveAttribute("readonly");
    expect(screen.queryByRole("button", { name: "保存并启用" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "测试连接" })).not.toBeInTheDocument();
  });

  it("waits for destination instance buttons after async loading", async () => {
    let resolveDestinations: ((value: typeof destinationFixtures) => void) | null = null;
    mockedGetDestinations.mockImplementationOnce(
      () =>
        new Promise<typeof destinationFixtures>((resolve) => {
          resolveDestinations = resolve;
        }) as never,
    );

    render(<DestinationsPage />);

    await screen.findByRole("heading", { name: "输出配置" });
    expect(screen.queryByRole("button", { name: "Obsidian 落盘点" })).not.toBeInTheDocument();

    resolveDestinations?.(destinationFixtures);

    expect(await waitForDestinationButtons()).toBeInTheDocument();
  });
});
