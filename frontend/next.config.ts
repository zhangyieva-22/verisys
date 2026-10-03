import type { NextConfig } from "next";
const config: NextConfig = {
  agentRules: false,
  async rewrites() {
    const backend = (process.env.VERISYS_BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
    return [
      { source: "/api/evaluations/verify", destination: `${backend}/api/evaluations/verify` },
      { source: "/api/analyze", destination: `${backend}/api/analyze` },
      { source: "/api/evaluations/discover", destination: `${backend}/api/evaluations/discover` },
      { source: "/api/understanding", destination: `${backend}/api/understanding` },
      { source: "/api/diagram/enrich", destination: `${backend}/api/diagram/enrich` },
    ];
  },
};
export default config;
