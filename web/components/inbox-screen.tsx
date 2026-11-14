/* Purpose: Invoice drop zone, proposal queue, source review, and AI explainability. */

"use client";

import { useRef, useState } from "react";
import { useCompanySnapshot, useCreateDocument, useDraftJournal } from "@/lib/api/hooks";
import { inr } from "@/lib/format";
import { ActionButton, EmptyState, ErrorState, LoadingState, PageHeading, StateBadge } from "@/components/ui/common";


export function InboxScreen() {
  const query = useCompanySnapshot();
  const upload = useCreateDocument();
  const draft = useDraftJournal();
  const fileInput = useRef<HTMLInputElement>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [notice, setNotice] = useState("");
  const data = query.data;
  const selected = data?.invoices.find((invoice) => invoice.id === selectedId) ?? data?.invoices[0];
  const handleFile = async (file?: File) => {
    if (!file) return;
    if (!/\.(pdf|png|jpe?g)$/i.test(file.name)) { setNotice("Choose a PDF, JPG, or PNG invoice."); return; }
    if (file.size > 12 * 1024 * 1024) { setNotice("This file is over 12 MB. Please choose a smaller invoice."); return; }
    setNotice("");
    try {
      const invoice = await upload.mutateAsync(file);
      await draft.mutateAsync({ invoiceId: invoice.id, description: `${invoice.supplier} — ${invoice.number}`, date: invoice.date, lines: [
        { account: invoice.category, debit: invoice.base, credit: 0, source: "Invoice subtotal" },
        { account: "Input GST credit", debit: invoice.tax, credit: 0, source: "Invoice tax amount" },
        { account: "Accounts payable", debit: 0, credit: invoice.amount, source: "Invoice total" },
      ] });
      setSelectedId(invoice.id);
      setNotice(`${invoice.number} was added. Check the extracted values before posting.`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Upload could not be completed. Try again."); }
  };
  if (query.isLoading) return <LoadingState label="Loading invoices" />;
  if (query.isError || !data) return <ErrorState message={query.error instanceof Error ? query.error.message : undefined} onRetry={() => void query.refetch()} />;

  return <div>
    <PageHeading eyebrow="Work queue · 03 invoices" title="Invoice inbox" description="Bring in a bill, check what Munshi read, then review its suggested ledger entry." action={<div className="flex items-center gap-2 rounded-full bg-[#fff1d5] px-3 py-2 text-[10px] font-extrabold tracking-widest text-[#714314]">MOCK LLM <span className="font-normal tracking-normal">suggestions</span></div>} />
    <section className={`upload-zone mb-5 rounded-2xl p-5 sm:p-6 ${dragging ? "is-dragging" : ""}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); void handleFile(event.dataTransfer.files[0]); }}>
      <div className="flex flex-col items-center justify-between gap-4 sm:flex-row"><div className="flex items-center gap-4"><div className="upload-icon flex h-12 w-12 items-center justify-center rounded-2xl text-2xl">⇧</div><div><h2 className="font-bold">Drop a purchase invoice here</h2><p className="mt-1 text-xs text-[#6c5d4c]">PDF, JPG, or PNG · up to 12 MB · local mock extraction</p></div></div><div className="flex items-center gap-3"><input ref={fileInput} aria-label="Choose invoice file" type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" className="sr-only" onChange={(event) => void handleFile(event.target.files?.[0])} /><ActionButton onClick={() => fileInput.current?.click()} disabled={upload.isPending || draft.isPending}>{upload.isPending || draft.isPending ? "Reading invoice…" : "Choose a file"}</ActionButton></div></div>
      {notice && <p className="mt-3 rounded-lg bg-[#fff7e9] px-3 py-2 text-xs text-[#65461b]" role="status">{notice}</p>}
      {(upload.isError || draft.isError) && <p className="mt-3 text-xs font-medium text-[#a8312e]" role="alert">{upload.error?.message ?? draft.error?.message}</p>}
    </section>
    <div className="grid items-start gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
      <aside className="card p-4" aria-label="Invoice proposals"><div className="mb-3 flex items-center justify-between"><h2 className="font-bold">Proposals</h2><span className="rounded-full bg-[#f7ead6] px-2 py-1 text-[10px] font-bold text-[#704314]">{data.invoices.length} bills</span></div>
        {data.invoices.length === 0 ? <EmptyState title="Nothing in the inbox" description="Upload the first supplier invoice to get started." /> : <ul className="space-y-2">{data.invoices.map((invoice) => <li key={invoice.id}><button type="button" onClick={() => setSelectedId(invoice.id)} aria-pressed={selected?.id === invoice.id} className={`proposal-item w-full rounded-xl border p-3 text-left ${selected?.id === invoice.id ? "border-[#d5a67b] bg-[#fff6e9] shadow-sm" : "border-[#eee5d8] bg-white hover:bg-[#fffcf6]"}`}><span className="flex items-start justify-between gap-2"><span className="min-w-0"><span className="block truncate text-sm font-bold">{invoice.supplier}</span><span className="mt-1 block text-[11px] text-[#6c5d4c]">{invoice.number} · {invoice.date}</span></span><span className="shrink-0 text-xs font-bold">{inr(invoice.amount)}</span></span><span className="mt-2 block"><StateBadge state={invoice.status} /></span></button></li>)}</ul>}
      </aside>
      {selected ? <div className="grid min-w-0 gap-5 2xl:grid-cols-2">
        <section className="card overflow-hidden"><div className="flex items-center justify-between border-b border-[#eee5d8] px-4 py-3"><div><h2 className="text-sm font-bold">Source document</h2><p className="mt-0.5 text-[11px] text-[#6c5d4c]">{selected.number} · uploaded invoice</p></div><span className="rounded-full bg-[#f5f0e7] px-2 py-1 text-[9px] font-bold text-[#6c5d4c]">PREVIEW</span></div>
          <div className="preview-stage p-5 sm:p-8"><article className="invoice-paper relative mx-auto min-h-[360px] max-w-[420px] rotate-[-.3deg] border border-[#e7dccb] p-6 sm:p-8"><span className="absolute right-4 top-4 rotate-6 border-2 border-[#c05c30] px-2 py-1 text-[10px] font-extrabold tracking-widest text-[#a14b28]">MOCK COPY</span><div className="border-b-2 border-[#493a2a] pb-4"><div className="text-lg font-extrabold">{selected.supplier}</div><div className="mt-1 text-[10px] text-[#6c5d4c]">GSTIN: {selected.gstin}</div><div className="mt-1 text-[10px] text-[#6c5d4c]">Tax invoice · India</div></div><div className="mt-5 grid grid-cols-2 gap-3 text-xs"><div><p className="text-[10px] uppercase tracking-widest text-[#887962]">Invoice no.</p><p className="mt-1 font-bold">{selected.number}</p></div><div><p className="text-[10px] uppercase tracking-widest text-[#887962]">Invoice date</p><p className="mt-1 font-bold">{selected.date}</p></div></div><div className="mt-7 border-y border-dashed border-[#d8cbb8] py-4"><p className="text-xs font-bold">{selected.description}</p><div className="mt-5 space-y-2 text-xs"><div className="flex justify-between"><span>Subtotal</span><span>{inr(selected.base, 2)}</span></div><div className="flex justify-between"><span>GST ({selected.taxRate}%)</span><span>{inr(selected.tax, 2)}</span></div></div></div><div className="mt-4 flex justify-between text-sm font-extrabold"><span>Total due</span><span>{inr(selected.amount, 2)}</span></div><div className="ledger-dots mt-6 h-10 opacity-60" aria-hidden="true" /></article></div>
        </section>
        <section className="space-y-5"><article className="card p-5"><div className="flex flex-wrap items-start justify-between gap-2"><div><h2 className="text-sm font-bold">Proposed ledger entry</h2><p className="mt-1 text-[11px] text-[#6c5d4c]">Check each field against the source before review.</p></div><StateBadge state={selected.status} /></div><dl className="mt-5 space-y-3 text-sm"><div className="flex justify-between gap-3 border-b border-[#f0e8dc] pb-2"><dt className="text-[#6c5d4c]">Supplier</dt><dd className="text-right font-semibold">{selected.supplier}</dd></div><div className="flex justify-between gap-3 border-b border-[#f0e8dc] pb-2"><dt className="text-[#6c5d4c]">Suggested account</dt><dd className="text-right font-semibold">{selected.category}</dd></div><div className="flex justify-between gap-3 border-b border-[#f0e8dc] pb-2"><dt className="text-[#6c5d4c]">Invoice date</dt><dd className="font-semibold">{selected.date}</dd></div><div className="flex justify-between gap-3 border-b border-[#f0e8dc] pb-2"><dt className="text-[#6c5d4c]">Input GST credit</dt><dd className="font-semibold">{inr(selected.tax, 2)}</dd></div><div className="flex justify-between gap-3"><dt className="font-bold">Total payable</dt><dd className="font-extrabold">{inr(selected.amount, 2)}</dd></div></dl><button type="button" onClick={() => void draft.mutateAsync({ invoiceId: selected.id, description: `${selected.supplier} — ${selected.number}`, date: selected.date, lines: [{ account: selected.category, debit: selected.base, credit: 0, source: "Invoice subtotal" }, { account: "Input GST credit", debit: selected.tax, credit: 0, source: "Invoice tax amount" }, { account: "Accounts payable", debit: 0, credit: selected.amount, source: "Invoice total" }] })} disabled={draft.isPending} className="mt-5 w-full rounded-xl border border-[#d8c6ae] bg-[#fff8ec] px-4 py-3 text-xs font-bold text-[#6d4217] disabled:opacity-50">{draft.isPending ? "Preparing entry…" : "Create another journal draft"}</button></article>
          <article className="analysis-card card border-l-4 border-l-[#e2a14e] p-5"><div className="flex items-center justify-between"><h2 className="text-sm font-bold">Why Munshi suggested this</h2><span className="rounded-full bg-[#fff1d5] px-2 py-1 text-[9px] font-extrabold tracking-wider text-[#714314]">MOCK LLM</span></div><p className="mt-2 text-xs leading-relaxed text-[#6c5d4c]">This looks like a routine supplier bill. Its description matches a common {selected.category.toLowerCase()} expense, and the GST amount is separated as input credit.</p><dl className="mt-4 grid grid-cols-3 gap-2 border-t border-[#f0e8dc] pt-3"><div><dt className="text-[9px] uppercase tracking-wider text-[#84745e]">Source field</dt><dd className="mt-1 text-[11px] font-bold">Invoice total</dd></div><div><dt className="text-[9px] uppercase tracking-wider text-[#84745e]">Rule ID</dt><dd className="mt-1 text-[11px] font-bold">{selected.ruleId}</dd></div><div><dt className="text-[9px] uppercase tracking-wider text-[#84745e]">Confidence</dt><dd className="mt-1 text-[11px] font-bold">{Math.round(selected.confidence * 100)}%</dd></div></dl><p className="mt-3 text-[10px] leading-relaxed text-[#7a6a58]">Confidence helps prioritise your review. It is not proof that the suggestion is correct.</p></article>
        </section>
      </div> : <EmptyState title="Choose an invoice" description="Select a proposal to compare its source and suggested entry." />}
    </div>
  </div>;
}
