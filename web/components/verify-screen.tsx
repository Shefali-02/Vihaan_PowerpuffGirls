/* Purpose: Public hash/PDF verification with clear match state and audit evidence. */

"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useVerify } from "@/lib/api/hooks";
import { ActionButton, LoadingState, StateBadge } from "@/components/ui/common";


export function VerifyScreen() {
  const searchParams = useSearchParams();
  const initialHash = searchParams.get("hash") ?? "";
  const inputRef = useRef<HTMLInputElement>(null);
  const [hash, setHash] = useState(initialHash);
  const [submitted, setSubmitted] = useState(initialHash);
  const [fileMessage, setFileMessage] = useState("");
  const result = useVerify(submitted, !!submitted);
  const verify = (event: React.FormEvent) => { event.preventDefault(); const normalized = hash.trim(); if (normalized) { setFileMessage(""); setSubmitted(normalized); } };
  const handleFile = async (file?: File) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) { setFileMessage("Choose a PDF report or enter a report hash."); return; }
    if (file.size > 20 * 1024 * 1024) { setFileMessage("This file is over 20 MB. Choose a smaller PDF."); return; }
    try {
      const bytes = await file.arrayBuffer();
      const content = new TextDecoder("latin1").decode(bytes);
      const embedded = content.match(/\b[a-f0-9]{64}\b/i)?.[0];
      if (embedded) { setHash(embedded); setSubmitted(embedded); setFileMessage(`Report hash found in ${file.name}. Checking it against the signed register…`); }
      else { const digest = await crypto.subtle.digest("SHA-256", bytes); const calculated = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join(""); setHash(calculated); setSubmitted(calculated); setFileMessage(`Calculated SHA-256 from ${file.name}. Checking the signed register…`); }
    } catch { setFileMessage("This file could not be read. Please paste the report hash instead."); }
  };
  const data = result.data;
  return <div className="min-h-screen px-4 py-6 sm:py-10">
    <header className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 border-b border-[#e6d8c5] pb-5"><Link href="/" className="flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#b84d1b] text-lg font-extrabold text-white">M</span><span><span className="block text-sm font-extrabold tracking-widest">MUNSHI</span><span className="mt-0.5 block text-[10px] text-[#6c5d4c]">Public report verification</span></span></Link><div className="flex items-center gap-2"><span className="rounded-full border border-[#e5c38a] bg-[#fff4d9] px-2.5 py-1 text-[9px] font-extrabold tracking-widest text-[#714314]">{process.env.NEXT_PUBLIC_USE_MOCK !== "false" ? "MOCK" : "SANDBOX"}</span><span className="rounded-full border border-[#d2dce9] bg-[#eff4fb] px-2.5 py-1 text-[9px] font-extrabold tracking-widest text-[#345781]">PUBLIC CHECK</span></div></header>
    <main className="mx-auto max-w-5xl py-8 sm:py-12">
      <div className="mx-auto max-w-2xl text-center"><p className="text-[10px] font-extrabold uppercase tracking-[.2em] text-[#8a4d28]">Trust through verification</p><h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">Check a report against its signed record</h1><p className="mt-3 text-sm leading-relaxed text-[#6c5d4c]">Drop the report PDF or enter its SHA-256 hash. We’ll check whether it matches a report signed by a named CA.</p></div>
      <section className="card mx-auto mt-8 max-w-3xl p-5 sm:p-7"><div onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); void handleFile(event.dataTransfer.files[0]); }} className="rounded-2xl border-2 border-dashed border-[#d9c9b3] bg-[#fffcf6] p-6 text-center sm:p-8"><div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#f8efe3] text-2xl text-[#9b4218]">⌕</div><h2 className="mt-3 font-bold">Drop a report PDF to check it</h2><p className="mt-1 text-xs text-[#6c5d4c]">The file is read in your browser for this demo.</p><input ref={inputRef} type="file" accept="application/pdf,.pdf" className="sr-only" aria-label="Choose a PDF report" onChange={(event) => void handleFile(event.target.files?.[0])} /><button type="button" onClick={() => inputRef.current?.click()} className="mt-4 rounded-lg border border-[#dfd0bd] bg-white px-4 py-2 text-xs font-bold text-[#493a2a]">Browse files</button></div>
        <div className="my-5 flex items-center gap-3 text-[10px] font-bold uppercase tracking-widest text-[#8a7a65]"><span className="h-px flex-1 bg-[#eee5d8]" />or enter a report hash<span className="h-px flex-1 bg-[#eee5d8]" /></div>
        <form onSubmit={verify} className="flex flex-col gap-3 sm:flex-row"><div className="flex-1"><label htmlFor="report-hash" className="sr-only">Report SHA-256 hash</label><input id="report-hash" value={hash} onChange={(event) => setHash(event.target.value)} placeholder="Paste 64-character SHA-256 hash" className="h-12 w-full rounded-xl border border-[#d9c9b3] bg-white px-4 font-mono text-xs focus-visible:border-[#9b4218]" autoComplete="off" spellCheck={false} /></div><ActionButton type="submit" disabled={!hash.trim() || result.isFetching}>{result.isFetching ? "Checking…" : "Verify report"}</ActionButton></form>
        {(fileMessage || result.isError) && <p className="mt-3 text-xs text-[#6c5d4c]" role={result.isError ? "alert" : "status"}>{result.isError ? <span className="text-[#a8312e]">{result.error.message}</span> : fileMessage}</p>}
      </section>
      {result.isLoading && submitted && <div className="mx-auto mt-5 max-w-3xl"><LoadingState label="Checking the report signature" /></div>}
      {data && <section className={`mx-auto mt-6 max-w-3xl overflow-hidden rounded-2xl border bg-white shadow-[0_12px_34px_rgba(73,52,29,.07)] ${data.match ? "border-[#b9d8c3]" : "border-[#e8c5c1]"}`} aria-live="polite"><div className={`p-6 text-center sm:p-8 ${data.match ? "bg-[#eaf5ed]" : "bg-[#fff0ed]"}`}><div className={`mx-auto flex h-16 w-16 items-center justify-center rounded-full text-3xl font-extrabold ${data.match ? "bg-[#c9e5d1] text-[#176b45]" : "bg-[#f1d0ca] text-[#a8312e]"}`} aria-hidden="true">{data.match ? "✓" : "×"}</div><div className="mt-4 text-xs font-extrabold tracking-[.22em] text-[#6c5d4c]">REPORT CHECK</div><h2 className={`mt-1 text-4xl font-extrabold tracking-tight ${data.match ? "text-[#176b45]" : "text-[#a8312e]"}`}>{data.match ? "MATCH" : "NO MATCH"}</h2><p className="mt-2 text-sm text-[#493a2a]">{data.message}</p></div><div className="p-5 sm:p-7"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[9px] font-extrabold uppercase tracking-widest text-[#6c5d4c]">Checked hash</p><code className="mt-1 block max-w-2xl break-all text-[10px] text-[#493a2a]">{data.hash}</code></div><StateBadge state={data.match ? "ANCHORED" : "DRAFT BY AI"} /></div>{data.match && <><div className="mt-5 grid gap-4 sm:grid-cols-2"><div className="rounded-xl border border-[#eee5d8] p-4"><p className="text-[9px] font-extrabold uppercase tracking-widest text-[#6c5d4c]">Signed by</p>{data.signoffs?.map((signoff) => <div key={signoff.name} className="mt-2"><p className="text-sm font-bold">{signoff.name}</p><p className="text-xs text-[#6c5d4c]">{signoff.role} · {signoff.date}</p></div>)}</div><div className="rounded-xl border border-[#eee5d8] p-4"><p className="text-[9px] font-extrabold uppercase tracking-widest text-[#6c5d4c]">Anchor transaction</p><a href={`https://etherscan.io/tx/${data.anchorTx}`} target="_blank" rel="noreferrer" className="mt-2 block break-all font-mono text-[10px] font-bold text-[#395e8a] underline underline-offset-2">{data.anchorTx}</a><p className="mt-2 text-[10px] text-[#7a6a58]">This is a simulated transaction ID in MOCK mode.</p></div></div></>}</div></section>}
      <section className="mx-auto mt-8 max-w-3xl rounded-2xl border border-[#e8dece] bg-[#fffaf1]/90 p-5 sm:p-6"><h2 className="text-sm font-bold">How to verify it yourself</h2><ol className="mt-4 grid gap-4 sm:grid-cols-3"><li className="flex gap-3"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#f5e2ca] text-xs font-extrabold text-[#8d3914]">1</span><span className="text-xs leading-relaxed text-[#6c5d4c]">Calculate SHA-256 for the report file or copy the hash printed in its pack.</span></li><li className="flex gap-3"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#f5e2ca] text-xs font-extrabold text-[#8d3914]">2</span><span className="text-xs leading-relaxed text-[#6c5d4c]">Compare the hash to the signed report record shown above.</span></li><li className="flex gap-3"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#f5e2ca] text-xs font-extrabold text-[#8d3914]">3</span><span className="text-xs leading-relaxed text-[#6c5d4c]">Check the named CA sign-off and anchor reference. MOCK anchors are simulated.</span></li></ol></section>
    </main>
    <footer className="mx-auto max-w-5xl border-t border-[#e6d8c5] py-5 text-center text-[10px] text-[#6c5d4c]">Independent hackathon project. Not affiliated with or endorsed by any government body. <span className="mx-2">·</span><Link href="/" className="underline underline-offset-2">Return to Munshi</Link></footer>
  </div>;
}
