// Shows "MOCK LLM" whenever AI output came from PruneMock. Not dismissible by design.
// Use <MockLlmBadge mock={resp.mock} /> beside any AI result, and once globally in the app
// header using GET /v1/ai/status -> { mode, badge }.
export function MockLlmBadge({ mock, floating = false }: { mock: boolean; floating?: boolean }) {
  if (!mock) return null;
  return (
    <span
      role="status"
      aria-label="AI output is simulated by a mock model"
      className={
        "inline-flex items-center gap-1.5 rounded border-2 border-amber-600 bg-amber-100 px-2 py-0.5 " +
        "text-xs font-bold tracking-wide text-amber-950 " +
        (floating ? "fixed right-3 top-3 z-50 shadow-md" : "")
      }
    >
      <span aria-hidden className="h-2 w-2 rounded-full bg-amber-600" />
      MOCK LLM
    </span>
  );
}
