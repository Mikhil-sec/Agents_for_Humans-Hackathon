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
import { STATIC_MODE, getHousehold, isMajorMismatch, serverContractVersion } from '@/lib/api';
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

/**
 * The hosted-demo banner. Only ever rendered by the GitHub Pages build.
 *
 * **This is an honesty requirement, not decoration.** The deployed site runs the
 * real screens against a recorded agent run, with no backend and no model behind
 * it, and a judge is entitled to know that before they draw a conclusion about
 * what they are looking at. Saying it plainly is also the stronger move: the
 * thing being demonstrated — a policy engine that is deterministic code — is
 * exactly the part that loses nothing by running in a browser.
 *
 * It carries the reset because a visitor who has answered the card has spent the
 * demo, and "open a new tab" is a worse answer than a button.
 */
function DemoBanner() {
  if (!STATIC_MODE) return null;

  async function startOver() {
    const { resetStaticState } = await import('@/lib/staticBackend');
    resetStaticState();
    // A full reload rather than a router refresh: every screen reads through
    // hooks that cached their first result, and re-seeding underneath them
    // would leave half the app showing the answered world and half the fresh
    // one. This runs once, on an explicit click.
    window.location.reload();
  }

  return (
    <div className="border-b border-line bg-raised px-5 py-2 text-sm text-ink-soft">
      {/* The button sits in the text flow rather than pushed to the far edge:
          floated right it wrapped onto a third line at this width and made the
          bar taller than the header it sits above. */}
      <p className="mx-auto max-w-3xl">
        <span className="font-medium text-ink">Hosted demo</span> — the real screens, running in
        your browser from a recorded agent run. Answering a card works; it is local to this tab.{' '}
        <button
          onClick={startOver}
          className="underline underline-offset-2 transition-colors hover:text-ink"
        >
          Start over
        </button>
      </p>
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
        <DemoBanner />
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
              {/* The wordmark drops below 640px: four nav items, the theme
                  toggle and "Quiet Hours" do not fit on a 390px header, and the
                  wordmark wrapping to two lines makes the whole bar look
                  broken. The clock mark carries the brand at that width. */}
              <span className="hidden text-[15px] font-semibold tracking-tight sm:inline">
                Quiet Hours
              </span>
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
