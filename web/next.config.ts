import type { NextConfig } from 'next';

/**
 * Two builds come out of this file.
 *
 * **The normal one** is what `make demo` and Amplify run: a Next server talking
 * to the FastAPI backend. Nothing below changes it.
 *
 * **The static one** is the GitHub Pages deploy, selected by
 * `NEXT_PUBLIC_STATIC_DEMO=1`. Pages serves files and nothing else, so the app
 * has to be exported as HTML and the API has to come from inside the bundle —
 * see `lib/staticBackend.ts`. The three settings it adds are all forced by the
 * host rather than chosen:
 *
 * * `output: 'export'` — no Node server exists to render on demand. Safe here
 *   because every page is already `'use client'` and there are no dynamic
 *   routes, no `generateStaticParams`, no middleware and no `next/image`.
 * * `basePath` — a project Pages site is served from `/<repo>/`, not from the
 *   domain root. Without it every asset and link resolves one level too high
 *   and the deploy is a blank page with 404s in the console.
 * * `trailingSlash` — exports `/insights/index.html` rather than
 *   `/insights.html`, which is the shape Pages resolves for `/insights`.
 *
 * The base path is read from the environment rather than hardcoded so that a
 * fork, or a move to a user-level Pages site (where the correct value is `''`),
 * is a workflow change and not a code change.
 */
const isStatic = process.env.NEXT_PUBLIC_STATIC_DEMO === '1';
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? '';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The shared contracts live at ../contracts/typescript and are the single
  // source of truth for every API payload type. Compiling a file from outside
  // the project root needs this flag; without it the import resolves for
  // TypeScript and fails at build. The static build leans on the same flag to
  // read the fixture set from ../fixtures.
  experimental: { externalDir: true },
  ...(isStatic
    ? {
        output: 'export' as const,
        trailingSlash: true,
        ...(basePath ? { basePath, assetPrefix: basePath } : {}),
        // `next/image`'s optimiser is a server. Nothing here uses it today; this
        // makes that explicit rather than leaving a future `<Image>` to fail the
        // export with a message about a missing loader.
        images: { unoptimized: true },
      }
    : {}),
};

export default nextConfig;
