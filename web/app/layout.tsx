import type { Metadata, Viewport } from 'next';
import './globals.css';
import { AppShell } from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Quiet Hours',
  description:
    'An agent that handles household admin and interrupts you only when a real decision is needed.',
};

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f5f5f3' },
    { media: '(prefers-color-scheme: dark)', color: '#0a0b0c' },
  ],
};

/**
 * Set the theme before first paint.
 *
 * Runs synchronously in <head>: a flash of the wrong theme on a product whose
 * best screenshot is a nearly empty page is the most visible bug it could have.
 * Wrapped in try/catch because Safari private mode throws on localStorage.
 */
const THEME_SCRIPT = `
try {
  var saved = localStorage.getItem('qh-theme');
  var dark = saved ? saved === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  if (dark) document.documentElement.classList.add('dark');
} catch (e) {}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-dvh">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
