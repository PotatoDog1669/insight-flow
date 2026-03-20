import {
  buildInitialDestinationConfig,
  normalizeNotionConfig,
  normalizeObsidianConfig,
  normalizeRssConfig,
} from "@/app/destinations/utils";

describe("destinations utils", () => {
  it("normalizes notion ids from urls and trims obsidian/rss config fields", () => {
    expect(
      normalizeNotionConfig({
        database_id: "https://www.notion.so/workspace/My-db-3170dd92-84fc-805c-a19b-fd4a76db602e",
        parent_page_id: "",
      }),
    ).toEqual({
      database_id: "3170dd9284fc805ca19bfd4a76db602e",
      parent_page_id: "",
    });

    expect(
      normalizeObsidianConfig({
        mode: "",
        api_url: " https://127.0.0.1:27124/ ",
        api_key: " secret ",
        vault_path: " /vault ",
        target_folder: " AI Daily/ ",
      }),
    ).toEqual({
      mode: "rest",
      api_url: "https://127.0.0.1:27124",
      api_key: "secret",
      vault_path: "/vault",
      target_folder: "AI Daily/",
    });

    expect(
      normalizeRssConfig({
        feed_url: " http://localhost:8000/api/v1/feed.xml ",
        site_url: " http://localhost:3018 ",
        feed_title: " Reports ",
        feed_description: " Desc ",
        max_items: "oops",
      }),
    ).toEqual({
      feed_url: "http://localhost:8000/api/v1/feed.xml",
      site_url: "http://localhost:3018",
      feed_title: "Reports",
      feed_description: "Desc",
      max_items: 20,
    });
  });

  it("builds initial config per destination type", () => {
    expect(buildInitialDestinationConfig("notion")).toHaveProperty("title_property", "Name");
    expect(buildInitialDestinationConfig("obsidian")).toHaveProperty("mode", "rest");
    expect(buildInitialDestinationConfig("rss")).toHaveProperty("feed_title", "LexDeepResearch Reports");
  });
});
