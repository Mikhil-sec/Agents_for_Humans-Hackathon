import { dirname } from 'path';
import { fileURLToPath } from 'url';
import { FlatCompat } from '@eslint/eslintrc';

const compat = new FlatCompat({ baseDirectory: dirname(fileURLToPath(import.meta.url)) });

const config = [
  ...compat.extends('next/core-web-vitals', 'next/typescript'),
  {
    rules: {
      // Lane rule: no `any` in committed code. Types come from the contracts.
      '@typescript-eslint/no-explicit-any': 'error',
    },
  },
  // `out/**` is the static export for GitHub Pages — minified build output, not
  // source. Without it, `npm run lint` reports hundreds of warnings from bundled
  // vendor code and buries anything real.
  { ignores: ['.next/**', 'out/**', 'node_modules/**', 'next-env.d.ts'] },
];

export default config;
