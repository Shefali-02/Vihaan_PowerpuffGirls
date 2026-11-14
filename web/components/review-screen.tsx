/* Purpose: Balanced double-entry journal review with a clear post confirmation. */

"use client";

import { useState } from "react";
import { useCompanySnapshot, usePostJournal } from "@/lib/api/hooks";
import { inr } from "@/lib/format";
import { ActionButton, ConfirmDialog, EmptyState, ErrorState, LoadingState, PageHeading, StateBadge } from "@/components/ui/common";


export function ReviewScreen() {
  const query = useCompanySnapshot();
  const post = usePostJournal();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const journals = query.data?.journals.filter((journal) => journal.status === "DRAFT BY AI") ?? [];
  const selected = journals.find((journal) => journal.id === selectedId) ?? journals[0];
  const totals = { debit: selected?.lines.reduce((sum, line) => sum + line.debit, 0) ?? 0, credit: selected?.lines.reduce((sum, line) => sum + line.credit, 0) ?? 0 };
  const balanced = Math.abs(totals.debit - totals.credit) < 0.01;
  if (query.isLoading) return <LoadingState label="Loading draft journals" />;
  if (query.isError || !query.data) return <ErrorState onRetry={() => void query.refetch()} />;
  return <div>
    <PageHeading eyebrow="Ledger · Accountant workspace" title="Review journal drafts" description="Confirm the accounts and amounts balance before adding this entry to the ledger." action={<span className="rounded-full bg-[#fff1d5] px-3 py-2 text-[10px] font-extrabold tracking-widest text-[#714314]">{process.env.NEXT_PUBLIC_USE_MOCK !== "false" ? "MOCK" : "SANDBOX"}</span>} />
    {post.isError && <div className="mb-4"><ErrorState message={post.error.message} /></div>}
    {selected ? <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
      <section className="card min-w-0 overflow-hidden"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#eee5d8] p-5"><div><p className="text-xs text-[#6c5d4c]">Draft {selected.id}</p><h2 className="mt-1 text-base font-bold">{selected.description}</h2><p className="mt-1 text-xs text-[#6c5d4c]">Journal date · {selected.date} · Prepared by {selected.preparedBy}</p></div><StateBadge state={selected.status} /></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[650px] border-collapse text-left text-sm"><thead><tr className="bg-[#faf5ec] text-[10px] uppercase tracking-wider text-[#6c5d4c]"><th className="px-5 py-3 font-bold">Account</th><th className="px-5 py-3 font-bold">Source</th><th className="px-5 py-3 text-right font-bold">Debit</th><th className="px-5 py-3 text-right font-bold">Credit</th></tr></thead><tbody>{selected.lines.map((line) => <tr key={line.id} className="border-t border-[#f0e8dc]"><td className="px-5 py-4 font-semibold">{line.account}</td><td className="px-5 py-4 text-xs text-[#6c5d4c]">{line.source}</td><td className="px-5 py-4 text-right tabular-nums">{line.debit ? inr(line.debit, 2) : "—"}</td><td className="px-5 py-4 text-right tabular-nums">{line.credit ? inr(line.credit, 2) : "—"}</td></tr>)}</tbody><tfoot><tr className="border-t-2 border-[#d9c9b3] bg-[#fcf8f0] font-extrabold"><td colSpan={2} className="px-5 py-4">Journal totals</td><td className="px-5 py-4 text-right tabular-nums">{inr(totals.debit, 2)}</td><td className="px-5 py-4 text-right tabular-nums">{inr(totals.credit, 2)}</td></tr></tfoot></table></div>
        <div className="flex flex-col justify-between gap-3 border-t border-[#eee5d8] p-5 sm:flex-row sm:items-center"><div className={`flex items-center gap-2 text-sm font-bold ${balanced ? "text-[#176b45]" : "text-[#a8312e]"}`}><span aria-hidden="true">{balanced ? "✓" : "!"}</span><span>{balanced ? "Balanced — debits equal credits" : "Out of balance — check the values"}</span></div><ActionButton onClick={() => setConfirm(true)} disabled={!balanced || post.isPending}>{post.isPending ? "Posting…" : "Post to ledger"}</ActionButton></div>
      </section>
      <aside className="space-y-4"><section className="card p-5"><h2 className="text-sm font-bold">Drafts waiting for review</h2><p className="mt-1 text-xs text-[#6c5d4c]">Choose an entry to check before posting.</p><div className="mt-4 space-y-2">{journals.map((journal) => <button key={journal.id} type="button" aria-pressed={selected.id === journal.id} onClick={() => setSelectedId(journal.id)} className={`w-full rounded-xl border p-3 text-left ${journal.id === selected.id ? "border-[#d5a67b] bg-[#fff6e9]" : "border-[#eee5d8] bg-white hover:bg-[#fffcf6]"}`}><span className="block text-xs font-bold">{journal.description}</span><span className="mt-1 block text-[10px] text-[#6c5d4c]">{journal.id} · {journal.date}</span></button>)}</div></section><section className="rounded-2xl border border-[#d8c8b3] bg-[#fff8ec] p-4"><h3 className="text-xs font-bold text-[#614318]">What happens when you post?</h3><p className="mt-2 text-xs leading-relaxed text-[#6c5d4c]">The balanced draft is added to the company ledger and moves to the CA approval queue. It is not marked approved until a named reviewer signs it.</p></section></aside>
    </div> : <EmptyState title="All drafts are posted" description="New invoice proposals will appear here after you review them in the inbox." />}
    {confirm && selected && <ConfirmDialog title="Post this journal?" description="This adds the entry to the Acme Pvt Ltd ledger and queues it for CA sign-off." onClose={() => setConfirm(false)}><div className="rounded-xl border border-[#eee5d8] bg-[#fcf8f0] p-4 text-sm"><p className="font-bold">{selected.description}</p><div className="mt-2 flex justify-between text-xs text-[#6c5d4c]"><span>Total debit</span><span className="font-bold text-[#2b2118]">{inr(totals.debit, 2)}</span></div><div className="mt-1 flex justify-between text-xs text-[#6c5d4c]"><span>Total credit</span><span className="font-bold text-[#2b2118]">{inr(totals.credit, 2)}</span></div><div className="mt-3 border-t border-[#eadfce] pt-3 text-xs text-[#176b45]">✓ Balanced · trust state changes to REVIEWED</div></div><div className="mt-5 flex justify-end gap-2"><ActionButton variant="secondary" onClick={() => setConfirm(false)}>Go back</ActionButton><ActionButton onClick={() => { post.mutate(selected.id, { onSuccess: () => setConfirm(false) }); }}>Post entry</ActionButton></div></ConfirmDialog>}
  </div>;
}
