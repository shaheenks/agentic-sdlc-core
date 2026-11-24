import type { NextConfig } from "next";

// `standalone` output: the container runs `node server.js` with only the files it needs.
const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
