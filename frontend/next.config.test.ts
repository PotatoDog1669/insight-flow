import nextConfig from "./next.config";

describe("next rewrites", () => {
  const originalBackendInternalUrl = process.env.BACKEND_INTERNAL_URL;

  afterEach(() => {
    if (originalBackendInternalUrl === undefined) {
      delete process.env.BACKEND_INTERNAL_URL;
      return;
    }

    process.env.BACKEND_INTERNAL_URL = originalBackendInternalUrl;
  });

  it("defaults api rewrites to localhost backend", async () => {
    delete process.env.BACKEND_INTERNAL_URL;

    await expect(nextConfig.rewrites?.()).resolves.toEqual([
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ]);
  });

  it("prefers BACKEND_INTERNAL_URL when provided", async () => {
    process.env.BACKEND_INTERNAL_URL = "http://backend:9000";

    await expect(nextConfig.rewrites?.()).resolves.toEqual([
      {
        source: "/api/:path*",
        destination: "http://backend:9000/api/:path*",
      },
    ]);
  });
});
