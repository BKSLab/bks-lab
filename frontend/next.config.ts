import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // Dev proxy: browser calls same-origin /api/*, Next forwards to FastAPI.
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.API_PROXY_URL ?? "http://127.0.0.1:8000"}/api/v1/:path*`,
      },
      {
        source: "/api/admin/:path*",
        destination: `${process.env.API_PROXY_URL ?? "http://127.0.0.1:8000"}/api/admin/:path*`,
      },
      {
        source: "/api/health",
        destination: `${process.env.API_PROXY_URL ?? "http://127.0.0.1:8000"}/api/health`,
      },
    ];
  },
};

export default nextConfig;
