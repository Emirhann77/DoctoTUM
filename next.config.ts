import type { NextConfig } from "next";

// noop: bump to trigger Vercel Git deploy
const nextConfig: NextConfig = {
  async rewrites() {
    return {
      beforeFiles: [{ source: "/", destination: "/index.html" }],
    };
  },
};

export default nextConfig;
