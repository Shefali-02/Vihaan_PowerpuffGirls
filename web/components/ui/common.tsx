/* Purpose: Shared page headings, badges, alerts, loading, and empty states. */
import type { TrustState } from "@/lib/api/types";

export function PageHeading({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description: string; action?: React.ReactNode }) {
  return <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div>{eyebrow && <p className="page-eyebrow mb-1.5 text-[10px] font-extrabold uppercase">{eyebrow}</p>}<h1 className="page-title text-3xl font-bold tracking-tight sm:text-[2.1rem]">{title}</h1><p className="page-description mt-2 text-sm text-[#6c5d4c]">{description}</p></div>{action}</div>;
}

const badgeStyle: Record<TrustState, string> = {
  "DRAFT BY AI": "border-[#f1d6b1] bg-[#fff4de] text-[#714314]",
  REVIEWED: "border-[#d8d4a8] bg-[#f4f3df] text-[#625c1e]",
  APPROVED: "border-[#c8dfce] bg-[#edf5ef] text-[#176b45]",
  ANCHORED: "border-[#cbd8eb] bg-[#eff4fb] text-[#345781]",
};
export function StateBadge({ state, className = "" }: { state: TrustState; className?: string }) {
  return <span className={`trust-pill inline-flex items-center rounded-full border px-2.5 py-1 text-[9px] font-extrabold tracking-[.12em] ${badgeStyle[state]} ${className}`}>{state}</span>;
}

export function LoadingState({ label = "Loading your books" }: { label?: string }) {
  return <div className="card space-y-4 p-6" role="status" aria-label={label}><span className="sr-only">{label}…</span><div className="skeleton h-5 w-44" /><div className="skeleton h-4 w-full max-w-lg" /><div className="grid gap-3 sm:grid-cols-3"><div className="skeleton h-20" /><div className="skeleton h-20" /><div className="skeleton h-20" /></div></div>;
}
export function ErrorState({ message = "We couldn’t load these records. Try again in a moment.", onRetry }: { message?: string; onRetry?: () => void }) {
  return <div className="rounded-2xl border border-[#e8c9c3] bg-[#fff6f4] p-5" role="alert"><p className="font-bold text-[#7e2d28]">This page didn’t load</p><p className="mt-1 text-sm text-[#6c5d4c]">{message}</p>{onRetry && <button type="button" onClick={onRetry} className="mt-3 rounded-lg border border-[#b84d1b] px-3 py-2 text-xs font-bold text-[#8d3914]">Try again</button>}</div>;
}
export function EmptyState({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return <div className="rounded-2xl border border-dashed border-[#d9c9b3] bg-[#fffcf5] p-8 text-center"><div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-[#f8efe3] text-lg text-[#8a4d28]">◇</div><h3 className="font-bold">{title}</h3><p className="mx-auto mt-1 max-w-md text-sm text-[#6c5d4c]">{description}</p>{action && <div className="mt-4">{action}</div>}</div>;
}

export function ActionButton({ children, onClick, disabled = false, variant = "primary", type = "button" }: { children: React.ReactNode; onClick?: () => void; disabled?: boolean; variant?: "primary" | "secondary" | "danger"; type?: "button" | "submit" }) {
  const variantStyle = variant === "primary" ? "bg-[#b84d1b] text-white hover:bg-[#963e14]" : variant === "danger" ? "bg-[#a8312e] text-white hover:bg-[#852522]" : "border border-[#dfd0bd] bg-white text-[#493a2a] hover:bg-[#fbf5eb]";
  return <button type={type} onClick={onClick} disabled={disabled} className={`action-button inline-flex min-h-10 items-center justify-center rounded-xl px-4 py-2 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-45 ${variantStyle}`}>{children}</button>;
}

export function ConfirmDialog({ title, description, onClose, children }: { title: string; description: string; onClose: () => void; children: React.ReactNode }) {
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#241b13]/45 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section role="dialog" aria-modal="true" aria-labelledby="dialog-title" aria-describedby="dialog-description" className="w-full max-w-lg rounded-2xl border border-[#eadfce] bg-[#fffdfa] p-5 shadow-2xl sm:p-6" onKeyDown={(event) => { if (event.key === "Escape") onClose(); }}><div className="mb-5 flex items-start justify-between gap-4"><div><h2 id="dialog-title" className="text-xl font-bold">{title}</h2><p id="dialog-description" className="mt-1 text-sm text-[#6c5d4c]">{description}</p></div><button type="button" onClick={onClose} className="rounded-lg px-2 py-1 text-xl text-[#6c5d4c] hover:bg-[#f5eddf]" aria-label="Close dialog">×</button></div>{children}</section></div>;
}
