import type { NextConfig } from "next";

const isDesktop = process.env.TAURI_ENV === "1";

const nextConfig: NextConfig = {
  ...(isDesktop && {
    output: "export",
    trailingSlash: true,
  }),
  images: { unoptimized: true },
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
