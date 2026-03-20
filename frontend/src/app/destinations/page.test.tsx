import { fireEvent, render, screen, waitFor } from "@testing-library/react";

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

    await screen.findByRole("heading", { name: "输出配置" });

    expect(screen.getByText("落盘点列表")).toBeInTheDocument();
    expect(screen.getByText("连接详情")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Notion 落盘点" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Obsidian 落盘点" })).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));

    expect(screen.getByRole("button", { name: "Obsidian 落盘点" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("heading", { name: "Obsidian" })).toBeInTheDocument();
    expect(screen.getByText("同步报告到本地 Obsidian。")).toBeInTheDocument();
  });

  it("keeps destination secrets hidden by default and reveals them on demand", async () => {
    render(<DestinationsPage />);

    await screen.findByRole("heading", { name: "输出配置" });

    expect(screen.queryByText("secret_notion_token")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "显示 Notion Token" }));
    expect(screen.getByText("secret_notion_token")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "隐藏 Notion Token" }));
    expect(screen.queryByText("secret_notion_token")).not.toBeInTheDocument();

    const notionTokenInput = screen.getByPlaceholderText("secret_...");
    expect(notionTokenInput).toHaveAttribute("type", "password");

    fireEvent.click(screen.getByRole("button", { name: "显示 集成令牌 (Token)" }));
    expect(notionTokenInput).toHaveAttribute("type", "text");

    fireEvent.click(screen.getByRole("button", { name: "隐藏 集成令牌 (Token)" }));
    expect(notionTokenInput).toHaveAttribute("type", "password");

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));

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

    await screen.findByRole("heading", { name: "输出配置" });

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));
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

    await screen.findByRole("heading", { name: "输出配置" });

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));
    fireEvent.click(screen.getByRole("radio", { name: /^本地文件/ }));

    expect(screen.getByRole("radio", { name: /^本地文件/ })).toBeChecked();
    expect(screen.getByPlaceholderText("/Users/leo/Documents/MyVault")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("https://127.0.0.1:27124")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("来自 Obsidian 本地 REST API 设置")).not.toBeInTheDocument();
  });

  it("detects the local obsidian vault path in file mode", async () => {
    render(<DestinationsPage />);

    await screen.findByRole("heading", { name: "输出配置" });

    fireEvent.click(screen.getByRole("button", { name: "Obsidian 落盘点" }));
    fireEvent.click(screen.getByRole("radio", { name: /^本地文件/ }));
    fireEvent.click(screen.getByRole("button", { name: "自动检测路径" }));

    await waitFor(() => {
      expect(mockedDiscoverObsidianVaults).toHaveBeenCalled();
    });

    expect(await screen.findByDisplayValue("/Users/leo/Documents/Obsidian Vault")).toBeInTheDocument();
    expect(screen.getByText("Detected current Obsidian vault.")).toBeInTheDocument();
  });
});
