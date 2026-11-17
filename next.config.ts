import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return {
      beforeFiles: [
        { source: "/", destination: "/index.html" },
        { source: "/home", destination: "/index.html" },
        { source: "/consult", destination: "/consult.html" },
        { source: "/check", destination: "/check.html" },
        { source: "/pharmacy", destination: "/pharmacy.html" },
        { source: "/profile", destination: "/profile.html" },
        { source: "/sos", destination: "/sos.html" },
        { source: "/plans", destination: "/plans.html" },
      ],
    };
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-XSS-Protection", value: "1; mode=block" },
        ],
      },
    ];
  },
};

export default nextConfig;
