import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The shared contracts live at ../contracts/typescript and are the single
  // source of truth for every API payload type. Compiling a file from outside
  // the project root needs this flag; without it the import resolves for
  // TypeScript and fails at build.
  experimental: { externalDir: true },
};

export default nextConfig;
