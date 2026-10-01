import type { NextConfig } from "next";
const config: NextConfig = {
  agentRules: false,
  async rewrites() {
    const backend = (process.env.VERISYS_BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
    return [
      { source: "/api/analyze", destination: `${backend}/api/analyze` },
      { source: "/api/evaluations/discover", destination: `${backend}/api/evaluations/discover` },
    ];
  },
};
export default config;
