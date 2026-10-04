import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server for the Cloud Run container (see Dockerfile).
  output: "standalone",
  poweredByHeader: false,
};

export default nextConfig;
