/* Purpose: Reusable navigation, role switcher, trust indicators, and footer. */

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useDemoRole } from "@/contexts/role-context";
import { CopilotWidget } from "@/components/copilot-widget";
import { MockLlmBadge } from "@/components/MockLlmBadge";


const nav = [
  ["/", "Today", "home"], ["/inbox", "Inbox", "inbox"], ["/review", "Review", "journal"],
  ["/approvals", "Approvals", "approve"], ["/reports", "Reports", "reports"], ["/investor-pack", "Investor pack", "pack"],
] as const;

function NavIcon({ name }: { name: string }) {
  const paths: Record<string, React.ReactNode> = {
    home: <><path d="m3 10 9-7 9 7"/><path d="M5 9v11h14V9M9 20v-6h6v6"/></>,
    inbox: <><path d="M12 15V3m0 0L7 8m5-5 5 5"/><path d="M4 14v6h16v-6M4 14h5l1.5 2h3L15 14h5"/></>,
    journal: <><path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5"/><path d="M8 4v16"/></>,
    approve: <><circle cx="12" cy="12" r="9"/><path d="m8 12 2.5 2.5L16.5 9"/></>,
    reports: <><path d="M4 20V10m5 10V4m6 16v-7m5 7H2"/><path d="m4 7 5-3 6 6 5-4"/></>,
    pack: <><path d="M5 4h14v16H5zM8 8h8M8 12h5"/><path d="m15 15 1.5 1.5L20 13"/></>,
    verify: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5M8 10.5l1.7 1.7 3.5-3.5"/></>,
  };
  return <svg aria-hidden="true" viewBox="0 0 24 24" className="h-[19px] w-[19px]" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name] ?? paths.home}</svg>;
}

export function SiteShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { role, setRole } = useDemoRole();
  const mode = process.env.NEXT_PUBLIC_USE_MOCK !== "false" ? "MOCK" : "SANDBOX";
  if (pathname === "/verify") return <>{children}</>;
  return <div className="min-h-screen md:flex">
    <aside className="site-sidebar hidden w-[88px] shrink-0 flex-col items-center border-r py-6 md:sticky md:top-0 md:flex md:h-screen" aria-label="Main navigation">
      <Link href="/" className="brand-mark mb-9 flex h-12 w-12 items-center justify-center rounded-2xl text-xl font-extrabold text-white" aria-label="Munshi home">M</Link>
      <nav className="flex w-full flex-1 flex-col items-center gap-3">
        {nav.map(([href, label, icon]) => <Link key={href} href={href} title={label} aria-label={label} aria-current={pathname === href ? "page" : undefined} className={`side-link flex h-12 w-12 items-center justify-center rounded-2xl text-xl ${pathname === href ? "bg-[#f5e2ca] text-[#8d3914]" : "text-[#756653] hover:bg-[#f8f0e2]"}`}><NavIcon name={icon} /></Link>)}
      </nav>
      <Link href="/verify" title="Public verification" aria-label="Public verification" className="side-footer-link flex h-12 w-12 items-center justify-center rounded-2xl text-xl"><NavIcon name="verify" /></Link>
      <div className="mt-5 flex h-10 w-10 items-center justify-center rounded-full border border-white/20 bg-gradient-to-br from-[#f8d7ae] to-[#e5ae78] text-sm font-bold text-[#67391e] shadow-lg" aria-label="Signed in as Asha Rao">AR</div>
    </aside>
    <div className="min-w-0 flex-1">
      <header className="app-header border-b px-4 py-4 md:px-8">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link href="/" className="brand-mark flex h-9 w-9 items-center justify-center rounded-xl font-bold text-white md:hidden">M</Link>
            <div><div className="text-sm font-bold tracking-wide">MUNSHI <span className="font-normal text-[#7a6a58]">/ Acme Pvt Ltd</span></div><div className="mt-1 text-xs text-[#6c5d4c]">Books that hold up to a closer look</div></div>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <span className="mode-pill rounded-full border px-2.5 py-1.5 text-[9px] font-extrabold tracking-[.14em] text-[#71480d]">{mode}</span>
            <MockLlmBadge mock={mode === "MOCK"} />
            <span className="trust-pill rounded-full border border-[#bcd8c5] bg-[#edf5ef] px-2.5 py-1.5 text-[9px] font-extrabold tracking-[.14em] text-[#176b45]">REVIEWED</span>
            <label className="sr-only" htmlFor="role-switch">Demo role</label><select id="role-switch" value={role} onChange={(event) => setRole(event.target.value as "Accountant" | "CA")} className="role-switch h-9 rounded-xl border px-2.5 text-xs font-semibold text-[#493a2a]"><option>Accountant</option><option>CA</option></select>
            <button type="button" aria-label="Notifications" className="relative flex h-9 w-9 items-center justify-center rounded-xl border border-[#eadfce] bg-white text-[#493a2a]"><svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></svg><span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-[#b84d1b]" /></button>
            <div className="hidden h-9 w-9 items-center justify-center rounded-full bg-[#f3ddc0] text-xs font-bold text-[#67391e] sm:flex">AR</div>
          </div>
        </div>
        <div className="mx-auto mt-4 flex max-w-[1440px] items-center justify-between border-t border-[#eee4d6] pt-3 text-xs text-[#6c5d4c]">
          <div><Link href="/" className="hover:text-[#8d3914]">Acme Pvt Ltd</Link><span className="mx-2">/</span><span className="font-semibold text-[#3a2d20]">{nav.find((item) => item[0] === pathname)?.[1] ?? "Workspace"}</span></div>
          <div className="flex items-center gap-2"><span className="rounded-full bg-[#f7ead6] px-2 py-1 font-bold text-[#704314]">FY 2026–27</span><span className="hidden rounded-full bg-[#edf5ef] px-2 py-1 font-bold text-[#176b45] sm:inline">● Ledger in sync</span></div>
        </div>
      </header>
      <nav className="mobile-nav flex gap-1 overflow-x-auto border-b border-[#eadfce] px-3 py-2 md:hidden" aria-label="Mobile navigation">
        {nav.map(([href, label]) => <Link key={href} href={href} aria-current={pathname === href ? "page" : undefined} className={`shrink-0 rounded-lg px-3 py-2 text-xs font-semibold ${pathname === href ? "bg-[#f5e2ca] text-[#8d3914]" : "text-[#756653]"}`}>{label}</Link>)}
        <Link href="/verify" className="shrink-0 rounded-lg px-3 py-2 text-xs font-semibold text-[#756653]">Verify</Link>
      </nav>
      <main className="screen-enter mx-auto min-h-[calc(100vh-170px)] max-w-[1440px] px-4 py-6 md:px-8 md:py-8">{children}</main>
      <footer className="border-t border-[#eadfce] bg-[#fffaf1]/80 px-4 py-5 text-xs text-[#6c5d4c] md:px-8">
        <div className="mx-auto flex max-w-[1440px] flex-col justify-between gap-3 sm:flex-row"><p>Independent hackathon project. Not affiliated with or endorsed by any government body.</p><div className="flex gap-5"><a href="mailto:help@munshi.example" className="underline underline-offset-2">Help desk</a><a href="#privacy" className="underline underline-offset-2">Privacy</a><a href="#about" className="underline underline-offset-2">About this demo</a></div></div>
      </footer>
    </div>
    <CopilotWidget />
  </div>;
}
