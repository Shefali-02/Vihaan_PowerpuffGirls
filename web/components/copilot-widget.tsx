/* Purpose: Floating financial Q&A panel with original Munshi mascot and cited demo answers. */

"use client";

import { useEffect, useRef, useState } from "react";
import { askMunshi, type MunshiAnswer } from "@/lib/copilot/ask-munshi";


type Message = { id: number; role: "user"; text: string } | { id: number; role: "assistant"; answer: MunshiAnswer };
const suggestions = ["What’s our cash position?", "How much GST is due?", "Any overdue invoices?", "What are our top expenses?"];

function Mascot({ mood = "idle", compact = false }: { mood?: "idle" | "wave" | "thinking" | "celebrate"; compact?: boolean }) {
  return <svg className={`munshi-mascot mood-${mood} ${compact ? "h-14 w-14" : "h-28 w-28"}`} viewBox="0 0 140 140" role="img" aria-label="Munshi, your friendly accountant">
    <ellipse cx="69" cy="128" rx="39" ry="6" fill="#5a3927" opacity=".12" />
    <g className="munshi-body"><path d="M32 119c3-22 13-34 37-34s34 12 38 34v8H32z" fill="#e8743b" stroke="#9e461f" strokeWidth="2"/><path d="M53 91h32l-5 33H59z" fill="#f9efe0"/><path d="M59 99h20M59 105h20M59 111h17" stroke="#bc9e79" strokeWidth="1.6"/>
      <path d="M31 101 20 113l12 9 18-17" fill="#f3c38f" stroke="#9e6541" strokeWidth="2"/><path d="m20 114 11-9 6 5-11 10z" fill="#fff5dd" stroke="#9e6541" strokeWidth="1.5"/><path d="m23 115 7-6m-4 9 7-6" stroke="#ccaa7d" strokeWidth="1"/>
      <g className="munshi-arm"><path d="M101 100c10 4 15 11 14 19l-10 3-9-12" fill="#f3c38f" stroke="#9e6541" strokeWidth="2"/><path d="m112 102 9-19 4 2-8 20" fill="#2b2118"/><path d="m121 83 2-8 3 7" fill="#e8743b"/></g>
    </g>
    <path d="M37 58c0-23 13-39 33-39s33 16 33 39v13c0 21-14 34-33 34S37 92 37 71z" fill="#f4c99d" stroke="#8c5936" strokeWidth="2"/>
    <path d="M33 51c1-23 15-39 37-39 18 0 31 11 36 30-10-7-24-10-39-8-12 2-24 8-34 17z" fill="#f7ead3" stroke="#b69a74" strokeWidth="2"/><path d="M34 45c20-14 48-18 72-7" fill="none" stroke="#d9c7aa" strokeWidth="3" strokeLinecap="round"/>
    <g className="munshi-face"><circle className="munshi-eye" cx="57" cy="64" r="2.6" fill="#2b2118"/><circle className="munshi-eye" cx="84" cy="64" r="2.6" fill="#2b2118"/><path d="M63 78c5 5 11 5 16 0" fill="none" stroke="#8b4f31" strokeWidth="2" strokeLinecap="round"/><circle cx="70" cy="69" r="2" fill="#d69d6a"/></g>
    <g fill="none" stroke="#5e4a38" strokeWidth="2.5"><circle cx="57" cy="65" r="10"/><circle cx="84" cy="65" r="10"/><path d="M67 65h7M47 62l-5-2m52 2 5-2"/></g>
    <path d="M55 29c5-5 12-8 19-8" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" opacity=".8"/>
  </svg>;
}

export function CopilotWidget() {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [thinking, setThinking] = useState(false);
  const [mood, setMood] = useState<"idle" | "wave" | "thinking" | "celebrate">("idle");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages, thinking]);
  useEffect(() => { if (open) inputRef.current?.focus(); }, [open]);

  const send = async (value: string) => {
    const clean = value.trim(); if (!clean || thinking) return;
    setMessages((current) => [...current, { id: Date.now(), role: "user", text: clean }]);
    setQuestion(""); setThinking(true); setMood("thinking");
    try {
      const answer = await askMunshi(clean);
      setMessages((current) => [...current, { id: Date.now() + 1, role: "assistant", answer }]);
      setMood("celebrate"); window.setTimeout(() => setMood("idle"), 1500);
    } catch {
      setMessages((current) => [...current, { id: Date.now() + 2, role: "assistant", answer: { text: "I couldn’t read the demo ledger just now. Please try again.", citations: [], label: "MOCK LLM" } }]);
      setMood("idle");
    } finally { setThinking(false); }
  };

  return <>
    <button type="button" onClick={() => { setOpen(true); setMood("wave"); window.setTimeout(() => setMood((current) => current === "wave" ? "idle" : current), 1200); }} className="munshi-launcher fixed bottom-5 right-5 z-40 flex h-[68px] items-center gap-2 rounded-full border border-[#d9c4a9] bg-[#fffdfa] pl-1.5 pr-4 transition hover:-translate-y-0.5" aria-label="Ask Munshi about your books" aria-expanded={open}><span className="flex h-14 w-14 items-center justify-center overflow-hidden rounded-full bg-[#fff2dc]"><Mascot compact /></span><span className="text-left"><span className="block text-xs font-extrabold">Ask Munshi</span><span className="mt-0.5 block text-[9px] font-bold tracking-widest text-[#8d3914]">MOCK LLM</span></span></button>
    {open && <div className="fixed inset-0 z-50 flex justify-end bg-[#241b13]/30" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}>
      <aside className="munshi-panel flex h-full w-full max-w-[440px] flex-col border-l border-[#e7d7c3] bg-[#fffdf8] shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="munshi-panel-title" onKeyDown={(event) => { if (event.key === "Escape") setOpen(false); }}>
        <header className="flex items-center justify-between border-b border-[#eee5d8] bg-[#fff8ec] px-4 py-3"><div className="flex items-center gap-3"><span className="flex h-12 w-12 items-center justify-center rounded-full bg-[#f8e8d2]"><Mascot mood={mood} compact /></span><div><h2 id="munshi-panel-title" className="text-sm font-extrabold">Munshi</h2><span className="mt-1 inline-flex rounded-full bg-[#fff1d5] px-2 py-0.5 text-[8px] font-extrabold tracking-widest text-[#714314]">MOCK LLM · DEMO DATA</span></div></div><button type="button" onClick={() => setOpen(false)} aria-label="Close Munshi assistant" className="rounded-lg px-2 py-1 text-2xl text-[#6c5d4c] hover:bg-[#f4ead8]">×</button></header>
        <div className="flex-1 space-y-4 overflow-y-auto p-4" aria-live="polite"><div className="flex max-w-[92%] gap-2"><span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-[#e8743b]"/><div className="rounded-2xl rounded-tl-sm border border-[#eee5d8] bg-white p-3 text-xs leading-relaxed text-[#493a2a] shadow-sm">Hi, I’m Munshi. Ask me about Acme’s cash, tax, spending, or review queue. I’ll show the ledger records I used.</div></div>
          {messages.map((message) => message.role === "user" ? <div key={message.id} className="ml-auto max-w-[88%] rounded-2xl rounded-tr-sm bg-[#b84d1b] p-3 text-xs leading-relaxed text-white">{message.text}</div> : <article key={message.id} className="max-w-[96%] rounded-2xl rounded-tl-sm border border-[#eee5d8] bg-white p-3 shadow-sm"><div className="mb-2 flex items-center gap-2"><span className="text-[10px] font-extrabold">Munshi</span><span className="rounded-full bg-[#fff1d5] px-1.5 py-0.5 text-[8px] font-extrabold tracking-wider text-[#714314]">{message.answer.label}</span></div><p className="text-xs leading-relaxed text-[#493a2a]">{message.answer.text}</p><div className="mt-3 border-t border-[#f0e8dc] pt-2"><p className="text-[8px] font-extrabold uppercase tracking-widest text-[#756653]">Ledger records checked</p>{message.answer.citations.length ? <ul className="mt-1 space-y-1">{message.answer.citations.map((citation) => <li key={citation.id} className="flex items-start justify-between gap-2 text-[9px]"><a href="/review" className="min-w-0 truncate font-semibold text-[#395e8a] underline underline-offset-2" title={`${citation.id} · ${citation.label}`}>{citation.id} · {citation.label}</a><span className="shrink-0 text-[#6c5d4c]">{citation.amount}</span></li>)}</ul> : <p className="mt-1 text-[9px] text-[#6c5d4c]">No matching ledger entry.</p>}</div></article>)}
          {thinking && <div className="flex items-center gap-2 rounded-xl bg-[#fff8ec] px-3 py-2 text-[10px] font-semibold text-[#6c5d4c]" role="status"><span className="munshi-writing">✎</span>Munshi is checking the ledger…</div>}<div ref={endRef} />
        </div>
        {messages.length === 0 && <div className="border-t border-[#eee5d8] px-4 pb-3 pt-3"><p className="mb-2 text-[9px] font-extrabold uppercase tracking-widest text-[#756653]">Try asking</p><div className="flex flex-wrap gap-2">{suggestions.map((item) => <button key={item} type="button" onClick={() => void send(item)} className="rounded-full border border-[#e4d5bf] bg-white px-2.5 py-1.5 text-[9px] font-semibold text-[#6b4a2a] hover:bg-[#fff4e2]">{item}</button>)}</div></div>}
        <form onSubmit={(event) => { event.preventDefault(); void send(question); }} className="border-t border-[#eee5d8] p-3"><label htmlFor="munshi-question" className="sr-only">Ask a question about your books</label><div className="flex gap-2"><input id="munshi-question" ref={inputRef} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about your books…" disabled={thinking} className="h-11 min-w-0 flex-1 rounded-xl border border-[#d9c9b3] bg-white px-3 text-xs disabled:opacity-60"/><button type="submit" disabled={!question.trim() || thinking} className="h-11 rounded-xl bg-[#b84d1b] px-4 text-xs font-bold text-white disabled:opacity-45">Ask</button></div><p className="mt-2 px-1 text-[8px] text-[#7a6a58]">Demo answers use only Acme’s local mock records.</p></form>
      </aside>
    </div>}
  </>;
}
