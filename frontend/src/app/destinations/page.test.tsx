import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import DestinationsPage from "@/app/destinations/page";
import { getDestinations, updateDestination } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getDestinations: vi.fn(),
    updateDestination: vi.fn(),
  };
});

const mockedGetDestinations = vi.mocked(getDestinations);
const mockedUpdateDestination = vi.mocked(updateDestination);

describe("DestinationsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetDestinations.mockResolvedValue([
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
          api_url: "http://127.0.0.1:27123",
          api_key: "obsidian-secret-key",
          target_folder: "AI-Reports/",
        },
      },
    ] as never);
    mockedUpdateDestination.mockResolvedValue({
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
    } as never);
  });

  it("keeps destination secrets hidden by default and reveals them on demand", async () => {
    render(<DestinationsPage />);

    await screen.findByRole("heading", { name: "输出配置" });

    expect(screen.queryByText("secret_notion_token")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "显示 Notion Token" }));
    expect(screen.getByText("secret_notion_token")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "隐藏 Notion Token" }));
    expect(screen.queryByText("secret_notion_token")).not.toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "配置" })[0]);

    const notionTokenInput = screen.getByPlaceholderText("secret_...");
    expect(notionTokenInput).toHaveAttribute("type", "password");

    fireEvent.click(screen.getByRole("button", { name: "显示 集成令牌 (Token)" }));
    expect(notionTokenInput).toHaveAttribute("type", "text");

    fireEvent.click(screen.getByRole("button", { name: "隐藏 集成令牌 (Token)" }));
    expect(notionTokenInput).toHaveAttribute("type", "password");

    fireEvent.click(screen.getByRole("button", { name: "取消" }));

    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "配置" })).toHaveLength(2);
    });

    fireEvent.click(screen.getAllByRole("button", { name: "配置" })[1]);

    const obsidianApiKeyInput = screen.getByPlaceholderText("来自 Obsidian 本地 REST API 设置");
    expect(obsidianApiKeyInput).toHaveAttribute("type", "password");

    fireEvent.click(screen.getByRole("button", { name: "显示 API Key" }));
    expect(obsidianApiKeyInput).toHaveAttribute("type", "text");

    fireEvent.click(screen.getByRole("button", { name: "隐藏 API Key" }));
    expect(obsidianApiKeyInput).toHaveAttribute("type", "password");
  });
});
