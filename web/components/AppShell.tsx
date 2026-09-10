'use client';

/**
 * The frame every screen sits in.
 *
 * Deliberately thin: a nav, a theme toggle, and the two banners that tell the
 * user the screen in front of them cannot be trusted right now. There is no
 * chat box and there is no composer — this is an inbox, not an assistant.
 */

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { getHousehold, isMajorMismatch, serverContractVersion } from '@/lib/api';
import { useOnline, useResource } from '@/lib/useResource';
import { HouseholdContext } from './HouseholdContext';

const NAV = [
  { href: '/', label: 'Today' },
  { href: '/activity', label: 'Activity' },
  { href: '/policies', label: 'Rules' },
  { href: '/insights', label: 'Insights' },
];

function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => setDark(document.documentElement.classList.contains('dark')), []);

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle('dark', next);
    try {
      localStorage.setItem('qh-theme', next ? 'dark' : 'light');
    } catch {
      // Private browsing. The theme still applies for this session.
    }
  }

  return (
    <button
      onClick={toggle}
      aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      className="rounded-lg p-2 text-muted transition-colors hover:bg-raised hover:text-ink"
    >
      {dark ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
          <circle cx="12" cy="12" r="4.2" stroke="currentColor" strokeWidth="1.7" />
          <path
            d="M12 2.6v2.2M12 19.2v2.2M2.6 12h2.2M19.2 12h2.2M5.4 5.4l1.6 1.6M17 17l1.6 1.6M18.6 5.4L17 7M7 17l-1.6 1.6"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
          />
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path
            d="M20 14.3A8.5 8.5 0 1 1 9.7 4a6.8 6.8 0 0 0 10.3 10.3Z"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </button>
  );
}

/**
 * The stale-deploy banner.
 *
 * The web app carries a compiled-in `CONTRACT_VERSION` and compares it to what
 * the API answers with. **Do not remove this check.** This product's success
 * state is a quiet, empty screen, so a deploy serving shapes this build does not
 * understand looks exactly like a good day.
 */
function ContractBanner() {
  const [server, setServer] = useState<string | null>(null);
  useEffect(() => {
    const timer = setInterval(() => setServer(serverContractVersion()), 1000);
    return () => clearInterval(timer);
  }, []);

  if (!isMajorMismatch(server)) return null;

  return (
    <div className="border-b border-line bg-accent-wash px-5 py-2.5 text-sm text-ink">
      <span className="font-medium">This page is out of date.</span> The server is on contract{' '}
      {server} and this build expects a different major version. Reload; if it persists, the deploy
      is stale.
    </div>
  );
}

function OfflineBanner() {
  const online = useOnline();
  if (online) return null;
  return (
    <div className="border-b border-line bg-raised px-5 py-2.5 text-sm text-ink-soft">
      You are offline. Quiet Hours keeps working without you — this page will catch up when you are
      back.
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const household = useResource(getHousehold, []);

  return (
    <HouseholdContext.Provider value={household.data}>
      <div className="min-h-dvh">
        <ContractBanner />
        <OfflineBanner />

        <header className="sticky top-0 z-10 border-b border-line bg-canvas/85 backdrop-blur-md">
          <div className="mx-auto flex h-14 max-w-3xl items-center gap-1 px-5">
            <Link href="/" className="mr-auto flex items-center gap-2.5">
              <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden>
                <circle
                  cx="8"
                  cy="8"
                  r="6.4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  className="text-ink"
                />
                <path
                  d="M8 4.4V8l2.4 1.5"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  className="text-ink"
                />
              </svg>
              <span className="text-[15px] font-semibold tracking-tight">Quiet Hours</span>
            </Link>

            <nav className="flex items-center gap-0.5">
              {NAV.map((item) => {
                const active =
                  item.href === '/' ? pathname === '/' : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? 'page' : undefined}
                    className={`rounded-lg px-2.5 py-1.5 text-sm transition-colors ${
                      active ? 'bg-raised font-medium text-ink' : 'text-muted hover:text-ink'
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
              <ThemeToggle />
            </nav>
          </div>
        </header>

        <main className="mx-auto max-w-3xl px-5 pb-24 pt-8">{children}</main>

        <footer className="mx-auto max-w-3xl px-5 pb-10 text-xs leading-relaxed text-muted">
          Quiet Hours never sends a message or moves money on your behalf without asking. In live
          mode it creates drafts and scheduled payment requests, never sends and transfers.
          {household.data ? (
            <span className="mt-1 block">{household.data.display_name}</span>
          ) : null}
        </footer>
      </div>
    </HouseholdContext.Provider>
  );
}
