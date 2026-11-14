/* Purpose: Key cash, runway, tax, review, attention, and compliance indicators. */

"use client";

import Link from "next/link";
import { CashChart } from "@/components/cash-chart";
import { useCompanySnapshot, usePnlReport } from "@/lib/api/hooks";
import { ErrorState, LoadingState } from "@/components/ui/common";


const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const attention = [
  { icon: "↗", title: "Approve October expense entries", detail: "2 entries · CA review needed", date: "Due today", href: "/approvals", color: "#9b4c18" },
  { icon: "▧", title: "Pay Shree Paper Co. invoice", detail: "₹18,400 · due 05-11-2026", date: "9 days overdue", href: "/inbox", color: "#a8312e" },
  { icon: "◷", title: "File your GST return", detail: "GSTR-3B · October 2026", date: "Due 20-11-2026", href: "/reports", color: "#176b45" },
];
const compliance = [
  { name: "GST", note: "GSTR-3B · 20 Nov", state: "Due soon", color: "amber" },
  { name: "TDS", note: "Q2 return · filed", state: "On track", color: "green" },
  { name: "PF", note: "October · paid", state: "On track", color: "green" },
  { name: "MCA", note: "Annual return · Dec", state: "Upcoming", color: "amber" },
];

export function TodayDashboard() {
  const snapshot = useCompanySnapshot();
  const pnlQuery = usePnlReport();
  if (snapshot.isLoading || pnlQuery.isLoading) return <LoadingState label="Loading your business overview" />;
  if (snapshot.isError || !snapshot.data || pnlQuery.isError || !pnlQuery.data) return <ErrorState onRetry={() => { void snapshot.refetch(); void pnlQuery.refetch(); }} />;
  const { data } = snapshot;
  const pnl = pnlQuery.data;
  if (pnl.months.length === 0) return <div className="card p-8 text-center"><h1 className="text-2xl font-bold">Your business overview is ready to connect</h1><p className="mx-auto mt-2 max-w-lg text-sm text-[#6c5d4c]">The connected API has not returned report periods yet. Once the first report is available, your cash, runway, and GST summary will appear here.</p></div>;
  const latest = pnl.months.at(-1);
  const previous = pnl.months.at(-2);
  const avgExpenses = pnl.months.length ? pnl.months.reduce((sum, month) => sum + month.expenses, 0) / pnl.months.length : 0;
  const openReviews = data.journals.filter((journal) => journal.status !== "ANCHORED").length;
  const cashChange = previous?.cash ? ((latest!.cash - previous.cash) / previous.cash) * 100 : 0;
  const mockMode = process.env.NEXT_PUBLIC_USE_MOCK !== "false";
  const attentionItems = mockMode ? attention : data.journals.filter((journal) => journal.status !== "ANCHORED").map((journal) => ({ icon: "▤", title: `Review ${journal.description}`, detail: `${journal.id} · ${journal.preparedBy}`, date: "Needs review", href: "/review", color: "#9b4c18" }));
  const kpis = [
    { title: "Cash in bank", value: money.format(latest?.cash ?? 0), helper: "Across 3 active accounts", trend: `${cashChange >= 0 ? "+" : ""}${cashChange.toFixed(1)}%`, tone: "orange", icon: "₹" },
    { title: "Runway", value: `${avgExpenses ? ((latest?.cash ?? 0) / avgExpenses).toFixed(1) : "—"} months`, helper: "At your recent spending pace", trend: "Healthy", tone: "amber", icon: "◷" },
    { title: "GST you owe this month", value: money.format(pnl.gst.netDue), helper: "Due by 20-11-2026", trend: "12 days left", tone: "red", icon: "▤" },
    { title: "Open reviews", value: `${openReviews} items`, helper: "Waiting for your attention", trend: "2 urgent", tone: "green", icon: "✓" },
  ];
  return <div className="space-y-6">
    <section className="dashboard-hero flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div><div className="mb-2 flex items-center gap-2"><span className="rounded-full bg-[#edf5ef] px-2.5 py-1 text-[10px] font-extrabold tracking-widest text-[#176b45]">● REVIEWED BOOKS</span><span className="rounded-full bg-[#fff1d5] px-2.5 py-1 text-[10px] font-extrabold tracking-widest text-[#704314]">{mockMode ? "MOCK DATA" : "SANDBOX REPORT"}</span></div><h1 className="welcome-title text-3xl font-bold sm:text-4xl">Good morning, Asha</h1><p className="mt-2 text-sm text-[#6c5d4c]">Here is how Acme is doing today. <span className="hidden sm:inline">Last updated 14-11-2026 at 09:42 IST.</span></p></div>
      <Link href="/inbox" className="inline-flex h-11 items-center justify-center gap-2 self-start rounded-xl bg-[#b84d1b] px-4 text-sm font-bold text-white shadow-md transition hover:bg-[#963e14] sm:self-auto"><span className="text-lg">＋</span> Add an invoice</Link>
    </section>

    <section aria-label="Business metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {kpis.map((item) => <article key={item.title} className={`card kpi-card kpi-${item.tone} p-5`}>
        <div className="flex items-start justify-between"><p className="text-sm font-medium text-[#6c5d4c]">{item.title}</p><span className={`flex h-9 w-9 items-center justify-center rounded-xl text-sm font-bold ${item.tone === "orange" ? "bg-[#fbe9dc] text-[#9a4219]" : item.tone === "amber" ? "bg-[#fff2d0] text-[#785005]" : item.tone === "red" ? "bg-[#fae9e6] text-[#922d29]" : "bg-[#e8f3ec] text-[#176b45]"}`}>{item.icon}</span></div>
        <div className="mt-3 flex items-baseline gap-2"><p className="text-[25px] font-bold tracking-tight text-[#2b2118]">{item.value}</p></div>
        <div className="mt-2 flex items-center justify-between gap-2"><p className="text-xs text-[#6c5d4c]">{item.helper}</p><span className={`whitespace-nowrap text-[11px] font-bold ${item.tone === "red" ? "text-[#a8312e]" : item.tone === "green" ? "text-[#176b45]" : "text-[#8a5316]"}`}>{item.trend}</span></div>
      </article>)}
    </section>

    <section className="grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(340px,1fr)]">
      <article className="card min-w-0 p-5 sm:p-6">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-bold">Cash over time</h2><p className="mt-1 text-xs text-[#6c5d4c]">Month-end cash balance · {pnl.months.length} reporting months</p></div><div className="text-right"><p className="text-xl font-bold">{money.format(latest?.cash ?? 0)}</p><p className="mt-1 text-xs font-semibold text-[#176b45]">{cashChange >= 0 ? "↑" : "↓"} {Math.abs(cashChange).toFixed(1)}% from last month</p></div></div>
        <CashChart data={pnl.months.map((month) => ({ month: month.month.slice(0, 3), amount: month.cash / 100_000 }))} />
        <div className="mt-2 flex items-center justify-between border-t border-[#f0e8dc] pt-3 text-[11px] text-[#6c5d4c]"><span>Figures shown in Indian rupees</span><span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[#c45b27]" /> Closing cash</span></div>
      </article>
      <article className="card p-5 sm:p-6">
        <div className="mb-2 flex items-center justify-between"><div><h2 className="text-lg font-bold">Needs your attention</h2><p className="mt-1 text-xs text-[#6c5d4c]">A few things to keep the books moving.</p></div><Link href="/inbox" className="text-xs font-bold text-[#9b4218] underline underline-offset-4">View all</Link></div>
        {attentionItems.length ? <ul className="divide-y divide-[#f0e8dc]">{attentionItems.map((item) => <li key={item.title}><Link href={item.href} className="group flex gap-3 py-4 focus-visible:outline"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#f8efe3] text-base font-bold" style={{ color: item.color }}>{item.icon}</span><span className="min-w-0 flex-1"><span className="block truncate text-sm font-bold group-hover:text-[#9b4218]">{item.title}</span><span className="mt-1 block text-xs text-[#6c5d4c]">{item.detail}</span></span><span className="whitespace-nowrap pt-1 text-[10px] font-bold text-[#6c5d4c]">{item.date}</span></Link></li>)}</ul> : <p className="my-6 rounded-xl border border-dashed border-[#d9c9b3] p-4 text-center text-xs text-[#6c5d4c]">No review items have been returned by the connected API yet.</p>}
        {mockMode && <div className="mt-3 rounded-xl bg-[#fff7e9] p-3"><p className="text-xs font-bold text-[#60431c]">Your records are up to date</p><p className="mt-1 text-[11px] leading-relaxed text-[#6c5d4c]">Latest ledger sync completed today. 3 invoices are ready for review.</p></div>}
      </article>
    </section>

    <section className="card p-5 sm:p-6" aria-labelledby="compliance-title">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-2"><div><h2 id="compliance-title" className="text-lg font-bold">Compliance calendar</h2><p className="mt-1 text-xs text-[#6c5d4c]">Key filing dates for Acme Pvt Ltd · FY 2026–27 {mockMode ? "" : "· example dates"}</p></div><Link href="/reports" className="text-xs font-bold text-[#9b4218] underline underline-offset-4">See reports</Link></div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{compliance.map((item) => <div key={item.name} className="flex items-center gap-3 rounded-xl border border-[#eee5d8] bg-[#fffdf9] p-3.5"><span className={`h-3 w-3 shrink-0 rounded-full ${item.color === "green" ? "bg-[#26815a] shadow-[0_0_0_4px_#eaf4ed]" : "bg-[#d99522] shadow-[0_0_0_4px_#fff3dc]"}`} aria-label={item.state} /><div className="min-w-0 flex-1"><p className="text-sm font-bold">{item.name}</p><p className="mt-0.5 truncate text-[11px] text-[#6c5d4c]">{item.note}</p></div><span className={`rounded-full px-2 py-1 text-[10px] font-bold ${item.color === "green" ? "bg-[#eaf4ed] text-[#176b45]" : "bg-[#fff3dc] text-[#704314]"}`}>{item.state}</span></div>)}</div>
    </section>
    <div className="text-right text-[10px] text-[#796953]">Indicative mock information · amounts in Indian rupees · dates DD-MM-YYYY</div>
  </div>;
}
