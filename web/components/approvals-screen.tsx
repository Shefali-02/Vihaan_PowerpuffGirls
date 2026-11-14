/* Purpose: CA queue, source-to-ledger diff, self-approval guard, and signed approval. */

"use client";

import { useState } from "react";
import { useCompanySnapshot, useApproveJournal } from "@/lib/api/hooks";
import { useDemoRole } from "@/contexts/role-context";
import { inr } from "@/lib/format";
import { ActionButton, ConfirmDialog, EmptyState, ErrorState, LoadingState, PageHeading, StateBadge } from "@/components/ui/common";


export function ApprovalsScreen() {
  const query = useCompanySnapshot();
  const approve = useApproveJournal();
  const { role } = useDemoRole();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [success, setSuccess] = useState("");
  const pending = query.data?.journals.filter((journal) => journal.status === "REVIEWED") ?? [];
  const selected = pending.find((journal) => journal.id === selectedId) ?? pending[0];
  const invoice = selected ? query.data?.invoices.find((item) => item.id === selected.invoiceId) : undefined;
  const signer = role === "CA" ? "Meera Iyer" : "Asha Rao";
  const isPreparer = !!selected && selected.preparedBy === signer;
  const canSign = role === "CA" && !isPreparer;
  const totalDebit = selected?.lines.reduce((sum, line) => sum + line.debit, 0) ?? 0;
  if (query.isLoading) return <LoadingState label="Loading approval queue" />;
  if (query.isError || !query.data) return <ErrorState onRetry={() => void query.refetch()} />;
  return <div>
    <PageHeading eyebrow="Independent review · named sign-off" title="CA approvals" description="Compare the supplier source with the posted entry, then sign only the items you reviewed." action={<span className="rounded-full bg-[#edf5ef] px-3 py-2 text-[10px] font-extrabold tracking-widest text-[#176b45]">CA SIGN-OFF REQUIRED</span>} />
    {success && <div className="mb-4 rounded-xl border border-[#c8dfce] bg-[#edf5ef] px-4 py-3 text-sm font-semibold text-[#176b45]" role="status">{success}</div>}
    {approve.isError && <div className="mb-4"><ErrorState message={approve.error.message} /></div>}
    <div className="grid items-start gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
      <aside className="card p-4"><div className="flex items-center justify-between"><h2 className="font-bold">Waiting for sign-off</h2><span className="rounded-full bg-[#f7ead6] px-2 py-1 text-[10px] font-bold text-[#704314]">{pending.length} items</span></div><p className="mb-3 mt-1 text-[11px] text-[#6c5d4c]">The preparer cannot approve their own entry.</p>
        {pending.length ? <ul className="space-y-2">{pending.map((journal) => { const own = journal.preparedBy === (role === "CA" ? "Meera Iyer" : "Asha Rao"); return <li key={journal.id}><button type="button" aria-pressed={selected?.id === journal.id} onClick={() => { setSelectedId(journal.id); setSuccess(""); }} className={`w-full rounded-xl border p-3 text-left ${selected?.id === journal.id ? "border-[#d5a67b] bg-[#fff6e9]" : "border-[#eee5d8] bg-white hover:bg-[#fffcf6]"}`}><span className="flex items-start justify-between gap-2"><span className="text-xs font-bold leading-relaxed">{journal.description}</span><StateBadge state={journal.status} /></span><span className="mt-2 block text-[10px] text-[#6c5d4c]">Prepared by {journal.preparedBy}</span>{own && <span className="mt-2 block text-[10px] font-bold text-[#a8312e]">Your own item · approval disabled</span>}</button></li>; })}</ul> : <EmptyState title="No approvals waiting" description="Posted journals will appear here for independent CA review." />}
      </aside>
      {selected && invoice ? <section className="space-y-5">
        <article className="card overflow-hidden"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#eee5d8] p-5"><div><p className="text-[10px] font-bold uppercase tracking-widest text-[#8a4d28]">Reviewing {selected.id}</p><h2 className="mt-1 text-lg font-bold">{selected.description}</h2><p className="mt-1 text-xs text-[#6c5d4c]">Posted {selected.date} · Prepared by {selected.preparedBy}</p></div><StateBadge state={selected.status} /></div>
          <div className="grid md:grid-cols-2"><section className="border-b border-[#eee5d8] p-5 md:border-b-0 md:border-r"><h3 className="text-xs font-bold uppercase tracking-wider text-[#6c5d4c]">Source document</h3><div className="mt-3 rounded-xl border border-[#eee5d8] bg-[#fffcf6] p-4"><p className="text-sm font-bold">{invoice.supplier}</p><p className="mt-1 text-xs text-[#6c5d4c]">{invoice.number} · {invoice.date}</p><dl className="mt-4 space-y-2 text-xs"><div className="flex justify-between gap-3"><dt className="text-[#6c5d4c]">GSTIN</dt><dd className="font-semibold">{invoice.gstin}</dd></div><div className="flex justify-between gap-3"><dt className="text-[#6c5d4c]">Invoice amount</dt><dd className="font-semibold">{inr(invoice.amount, 2)}</dd></div><div className="flex justify-between gap-3"><dt className="text-[#6c5d4c]">GST at {invoice.taxRate}%</dt><dd className="font-semibold">{inr(invoice.tax, 2)}</dd></div></dl></div></section>
            <section className="p-5"><h3 className="text-xs font-bold uppercase tracking-wider text-[#6c5d4c]">Posted ledger entry</h3><div className="mt-3 overflow-x-auto rounded-xl border border-[#eee5d8]"><table className="w-full min-w-[340px] text-left text-xs"><thead className="bg-[#faf5ec] text-[9px] uppercase tracking-wider text-[#6c5d4c]"><tr><th className="px-3 py-2">Account</th><th className="px-3 py-2 text-right">Debit</th><th className="px-3 py-2 text-right">Credit</th></tr></thead><tbody>{selected.lines.map((line) => <tr key={line.id} className="border-t border-[#f0e8dc]"><td className="px-3 py-2.5 font-medium">{line.account}</td><td className="px-3 py-2.5 text-right">{line.debit ? inr(line.debit, 2) : "—"}</td><td className="px-3 py-2.5 text-right">{line.credit ? inr(line.credit, 2) : "—"}</td></tr>)}</tbody></table></div><div className="mt-3 rounded-lg bg-[#f5f1e9] px-3 py-2 text-[10px] text-[#6c5d4c]">Diff check · source total {inr(invoice.amount, 2)} · ledger debits {inr(totalDebit, 2)} <span className="font-bold text-[#176b45]">{Math.abs(totalDebit - invoice.amount) < 0.01 ? "· MATCH" : "· CHECK"}</span></div></section>
          </div>
          <div className="flex flex-col justify-between gap-3 border-t border-[#eee5d8] bg-[#fffdf8] p-4 sm:flex-row sm:items-center"><p className="max-w-lg text-[11px] leading-relaxed text-[#6c5d4c]">Your approval is attributed to your CA name and anchors the report record for later verification.</p><div className="flex items-center gap-3"><span className="text-xs font-semibold text-[#493a2a]">Signer: {role === "CA" ? "Meera Iyer, CA" : "Accountant role"}</span><ActionButton onClick={() => setConfirm(true)} disabled={!canSign}>Review & sign off</ActionButton></div></div>
        </article>
        {!canSign && <div className="rounded-xl border border-[#edd1c2] bg-[#fff6f1] px-4 py-3 text-xs text-[#78402b]" role="note">{role !== "CA" ? "Switch the top bar role to CA to sign off. Accountants can prepare entries but cannot approve them." : `This entry was prepared by ${selected.preparedBy}; preparers cannot approve their own item.`}</div>}
      </section> : null}
    </div>
    {confirm && selected && <ConfirmDialog title="Sign and anchor this entry?" description="Your name will be attached to the approval record and the item will be marked ANCHORED." onClose={() => setConfirm(false)}><div className="rounded-xl bg-[#f8f2e7] p-4 text-sm"><p className="font-bold">{selected.description}</p><p className="mt-2 text-xs text-[#6c5d4c]">Signing as <span className="font-bold text-[#2b2118]">Meera Iyer, Chartered Accountant</span></p><p className="mt-3 border-t border-[#e7dbc8] pt-3 text-xs text-[#176b45]">✓ Your name and timestamp will be included in the audit record.</p></div><div className="mt-5 flex justify-end gap-2"><ActionButton variant="secondary" onClick={() => setConfirm(false)}>Cancel</ActionButton><ActionButton disabled={approve.isPending || !canSign} onClick={() => approve.mutate({ id: selected.id, input: { signer } }, { onSuccess: (result) => { setConfirm(false); setSuccess(`${result.journal.id} signed by ${result.signedBy} and marked ANCHORED. Anchor: ${result.anchorTx}`); } })}>{approve.isPending ? "Signing…" : "Sign & anchor"}</ActionButton></div></ConfirmDialog>}
  </div>;
}
