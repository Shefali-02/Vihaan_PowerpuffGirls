/*
 * Purpose: One typed boundary for exactly the versioned endpoints used by this frontend.
 *
 * Live mode (NEXT_PUBLIC_USE_MOCK=false):
 *   - All calls go to NEXT_PUBLIC_API_BASE_URL (default http://localhost:8000).
 *   - On the first real request the client auto-logs in as the demo accountant and
 *     caches the JWT in sessionStorage under "munshi_token".  Any page can call
 *     auth.logout() to clear it and force re-login on the next request.
 *   - getCompanySnapshot() assembles the CompanySnapshot from three parallel calls:
 *       GET /v1/auth/me  →  company header
 *       GET /v1/proposals (status=DRAFT_AI, NEEDS_REVIEW, DUPLICATE, MANUAL_ENTRY_REQUIRED)
 *       GET /v1/reports/pnl
 *
 * Mock mode (NEXT_PUBLIC_USE_MOCK=true or unset):
 *   - All calls are handled by the in-memory service in @/lib/mock/service.
 */
import type {
  ApproveInput,
  ApproveResponse,
  CompanySnapshot,
  DraftJournalInput,
  Invoice,
  Journal,
  PackResponse,
  PnlReport,
  VerifyResponse,
} from "@/lib/api/types";
import * as mock from "@/lib/mock/service";

export const useMock = process.env.NEXT_PUBLIC_USE_MOCK !== "false";

const baseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

// ---------------------------------------------------------------------------
// Token management
// ---------------------------------------------------------------------------

const TOKEN_KEY = "munshi_token";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TOKEN_KEY);
}

function setToken(token: string): void {
  if (typeof window !== "undefined") sessionStorage.setItem(TOKEN_KEY, token);
}

export const auth = {
  logout(): void {
    if (typeof window !== "undefined") sessionStorage.removeItem(TOKEN_KEY);
  },
};

// ---------------------------------------------------------------------------
// Auto-login with the demo accountant credentials (seeded by `python -m seed.seed`).
// Credentials are hardcoded here because this is a local demo — there are no
// production secrets involved.  Change them if you re-seed with different values.
// ---------------------------------------------------------------------------

const DEMO_EMAIL = "accountant@acme.demo";
const DEMO_PASSWORD = "demo1234";

async function ensureToken(): Promise<string> {
  const existing = getToken();
  if (existing) return existing;

  const response = await fetch(`${baseUrl}/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: DEMO_EMAIL, password: DEMO_PASSWORD }),
  });

  if (!response.ok) {
    const message = await response.text().catch(() => "");
    throw new Error(message || `Login failed (${response.status}). Make sure the backend is running and seeded.`);
  }

  const data = (await response.json()) as { access_token: string };
  setToken(data.access_token);
  return data.access_token;
}

// ---------------------------------------------------------------------------
// Generic request helper (all /v1/* routes)
// ---------------------------------------------------------------------------

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = await ensureToken();

  const isFormData = options.body instanceof FormData;
  const response = await fetch(`${baseUrl}/v1${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  });

  if (response.status === 401) {
    // Token expired mid-session — clear and retry once.
    auth.logout();
    const freshToken = await ensureToken();
    const retry = await fetch(`${baseUrl}/v1${path}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${freshToken}`,
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        ...options.headers,
      },
    });
    if (!retry.ok) {
      const message = await retry.text().catch(() => "");
      throw new Error(message || `The request failed (${retry.status}).`);
    }
    return retry.json() as Promise<T>;
  }

  if (!response.ok) {
    const message = await response.text().catch(() => "");
    throw new Error(message || `The request failed (${response.status}).`);
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Generic request helper for routes without the /v1 prefix (e.g. /public/*)
// ---------------------------------------------------------------------------

async function requestPublic<T>(path: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`);
  if (!response.ok) {
    const message = await response.text().catch(() => "");
    throw new Error(message || `The request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Shape adapters: map backend response shapes to the frontend types
// ---------------------------------------------------------------------------

/**
 * DocumentOut / ProposalOut (backend) → Invoice (frontend)
 *
 * The backend stores monetary values as integer paise; the frontend expects
 * rupees (float).  Confidence is a 0–1 float on the backend.
 */
function proposalToInvoice(proposal: {
  id: string;
  document_id: string;
  status: string;
  facts: Record<string, unknown> | null;
  reasons: string[];
  draft_entry_id: string | null;
  ruleset_version: string | null;
  llm_mode: string;
  doc_type: string | null;
  total_paise: number | null;
  created_at: string | null;
}): Invoice {
  const facts = (proposal.facts ?? {}) as Record<string, unknown>;
  const totalPaise = proposal.total_paise ?? 0;
  const taxRate = (facts.tax_rate as number | undefined) ?? 18;
  const base = Math.round((totalPaise / (1 + taxRate / 100)) / 100); // paise → rupees
  const tax = Math.round(totalPaise / 100) - base;

  // Map backend proposal status to frontend TrustState
  const statusMap: Record<string, Invoice["status"]> = {
    DRAFT_AI: "DRAFT BY AI",
    NEEDS_REVIEW: "REVIEWED",
    DUPLICATE: "REVIEWED",
    MANUAL_ENTRY_REQUIRED: "REVIEWED",
    APPROVED: "APPROVED",
    ANCHORED: "ANCHORED",
  };

  return {
    id: proposal.document_id,
    number: (facts.invoice_number as string | undefined) ?? proposal.document_id.slice(-8).toUpperCase(),
    supplier: (facts.supplier_name as string | undefined) ?? "Unknown supplier",
    date: (facts.invoice_date as string | undefined) ?? (proposal.created_at?.slice(0, 10) ?? ""),
    dueDate: (facts.due_date as string | undefined) ?? "",
    amount: Math.round(totalPaise / 100),
    base,
    tax,
    taxRate,
    category: (facts.category as string | undefined) ?? proposal.doc_type ?? "General",
    gstin: (facts.supplier_gstin as string | undefined) ?? "",
    status: statusMap[proposal.status] ?? "DRAFT BY AI",
    description: proposal.reasons.join("; ") || "AI-extracted document",
    ruleId: proposal.ruleset_version ?? "UNKNOWN",
    confidence: (facts.confidence_min as number | undefined) ?? 0.9,
  };
}

/**
 * JournalOut (backend) → Journal (frontend)
 */
function journalOutToJournal(j: {
  id: string;
  source_document_id: string | null;
  narration: string;
  entry_date: string;
  created_by: string;
  status: string;
  lines: { line_no: number; account_code: string; debit_paise: number; credit_paise: number; memo: string }[];
}): Journal {
  const statusMap: Record<string, Journal["status"]> = {
    DRAFT: "DRAFT BY AI",
    POSTED: "REVIEWED",
    APPROVED: "APPROVED",
    ANCHORED: "ANCHORED",
  };
  return {
    id: j.id,
    invoiceId: j.source_document_id ?? "",
    description: j.narration,
    date: j.entry_date,
    preparedBy: j.created_by,
    status: statusMap[j.status] ?? "DRAFT BY AI",
    lines: j.lines.map((line) => ({
      id: `${j.id}-${line.line_no}`,
      account: line.account_code,
      debit: Math.round(line.debit_paise / 100),
      credit: Math.round(line.credit_paise / 100),
      source: line.memo,
    })),
  };
}

// ---------------------------------------------------------------------------
// API surface
// ---------------------------------------------------------------------------

export const api = {
  // ── Snapshot ──────────────────────────────────────────────────────────────

  getCompanySnapshot: async (): Promise<CompanySnapshot> => {
    if (useMock) return mock.listMockData();

    // Run the three independent calls in parallel.
    const [me, proposalsRaw, pnlRaw] = await Promise.all([
      request<{
        name: string;
        email: string;
        workspace: { name: string; gstin: string };
        workspace_id: string;
        role: string;
      }>("/auth/me"),
      request<{ items: Parameters<typeof proposalToInvoice>[0][] }>("/proposals"),
      request<{
        total_income: string;
        total_expenses: string;
        net_profit: string;
        total_income_paise: number;
        total_expenses_paise: number;
        net_profit_paise: number;
        period_id: string;
        income: { code: string; name: string; amount_paise: number; amount: string }[];
        expenses: { code: string; name: string; amount_paise: number; amount: string }[];
      }>("/reports/pnl"),
    ]);

    const invoices = proposalsRaw.items.map(proposalToInvoice);

    // The backend PnlOut is period-based, not month-based.  Build a minimal
    // PnlReport shape so the existing dashboard charts keep working.
    const pnl: PnlReport = {
      company: me.workspace.name,
      fy: "2026–27",
      months: [
        {
          month: "Current period",
          revenue: Math.round(pnlRaw.total_income_paise / 100),
          expenses: Math.round(pnlRaw.total_expenses_paise / 100),
          profit: Math.round(pnlRaw.net_profit_paise / 100),
          cash: Math.round(pnlRaw.total_income_paise / 100), // best approximation available
        },
      ],
      topExpenses: pnlRaw.expenses
        .sort((a, b) => b.amount_paise - a.amount_paise)
        .slice(0, 5)
        .map((row) => ({ name: row.name, amount: Math.round(row.amount_paise / 100) })),
      gst: { output: 0, input: 0, netDue: 0 }, // GST summary available via /v1/tax/gst-summary
    };

    return {
      company: {
        name: me.workspace.name,
        gstin: me.workspace.gstin,
        fy: "2026–27",
        preparer: me.name,
        ca: "CA Demo",
      },
      invoices,
      journals: [], // journals are not needed by the snapshot; the review screen fetches them separately
      ledger: [],
      pnl,
    };
  },

  // ── Documents ─────────────────────────────────────────────────────────────

  createDocument: async (file: File): Promise<Invoice> => {
    if (useMock) return mock.uploadMockDocument(file);
    const form = new FormData();
    form.append("file", file);
    // Backend returns DocumentOut which contains an optional `proposal` field.
    const result = await request<{
      id: string;
      proposal: Parameters<typeof proposalToInvoice>[0] | null;
    }>("/documents", { method: "POST", body: form });
    if (result.proposal) return proposalToInvoice(result.proposal);
    // Fallback: return a minimal invoice from the document record.
    return {
      id: result.id,
      number: result.id.slice(-8).toUpperCase(),
      supplier: "Uploaded document",
      date: new Date().toLocaleDateString("en-GB"),
      dueDate: "",
      amount: 0, base: 0, tax: 0, taxRate: 18,
      category: "General",
      gstin: "",
      status: "DRAFT BY AI",
      description: "Document uploaded — no proposal generated yet.",
      ruleId: "UNKNOWN",
      confidence: 0,
    };
  },

  // ── Journals ──────────────────────────────────────────────────────────────

  draftJournal: (input: DraftJournalInput): Promise<Journal> => {
    if (useMock) return mock.draftMockJournal(input);

    // The backend `POST /v1/journals/draft` expects InvoiceFacts (the rules engine input),
    // not a pre-built journal line list.  Reconstruct minimal InvoiceFacts from the
    // display-side data the inbox screen passes in.  Amounts are in rupees; convert to paise.
    const totalPaise = Math.round(input.lines.reduce((sum, line) => sum + line.debit, 0) * 100);
    const taxLine = input.lines.find((line) => line.account.toLowerCase().includes("gst"));
    const taxPaise = taxLine ? Math.round(taxLine.debit * 100) : 0;
    const taxablePaise = totalPaise - taxPaise;
    // Derive a rough GST rate in basis points (1800 = 18%).
    const taxRateBp = taxablePaise > 0 ? Math.round((taxPaise / taxablePaise) * 10000) : 1800;

    // Parse date from DD-MM-YYYY or YYYY-MM-DD.
    let invoiceDateIso = input.date;
    if (/^\d{2}-\d{2}-\d{4}$/.test(input.date)) {
      const [dd, mm, yyyy] = input.date.split("-");
      invoiceDateIso = `${yyyy}-${mm}-${dd}`;
    }

    const invoiceFacts = {
      doc_type: "purchase_invoice",
      invoice_no: input.invoiceId,
      invoice_date: invoiceDateIso,
      counterparty_name: input.description.split(" — ")[0] ?? input.description,
      counterparty_gstin: null,
      category: input.lines[0]?.account ?? null,
      lines: [
        {
          description: input.description,
          taxable_paise: taxablePaise,
          gst_rate_bp: taxRateBp,
          category: input.lines[0]?.account ?? null,
        },
      ],
      declared_total_paise: totalPaise,
    };

    return request<Parameters<typeof journalOutToJournal>[0]>("/journals/draft", {
      method: "POST",
      body: JSON.stringify(invoiceFacts),
    }).then(journalOutToJournal);
  },

  postJournal: (id: string): Promise<Journal> =>
    useMock
      ? mock.postMockJournal(id)
      : request<Parameters<typeof journalOutToJournal>[0]>(`/journals/${encodeURIComponent(id)}/post`, {
          method: "POST",
          body: JSON.stringify({}),
        }).then(journalOutToJournal),

  // ── Approvals ─────────────────────────────────────────────────────────────

  approveJournal: (id: string, input: ApproveInput): Promise<ApproveResponse> =>
    useMock
      ? mock.approveMockJournal(id, input)
      : request<{ state: string; decided_by: string | null; anchor_batch: { tx_hash?: string } | null; snapshot: { id: string; status: string; source_document_id: string | null; narration: string; entry_date: string; created_by: string; lines: unknown[] } }>(
          `/approvals/${encodeURIComponent(id)}/approve`,
          { method: "POST", body: JSON.stringify({ note: input.note }) }
        ).then((res) => ({
          journal: journalOutToJournal(res.snapshot as Parameters<typeof journalOutToJournal>[0]),
          trustState: "ANCHORED" as const,
          signedBy: res.decided_by ?? input.signer,
          anchorTx: res.anchor_batch?.tx_hash ?? "",
        })),

  // ── Reports ───────────────────────────────────────────────────────────────

  getPnl: (): Promise<PnlReport> =>
    useMock
      ? mock.getMockPnl()
      : request<{
          total_income_paise: number;
          total_expenses_paise: number;
          net_profit_paise: number;
          expenses: { code: string; name: string; amount_paise: number; amount: string }[];
        }>("/reports/pnl").then((raw) => ({
          company: "Acme Pvt Ltd",
          fy: "2026–27",
          months: [
            {
              month: "Current period",
              revenue: Math.round(raw.total_income_paise / 100),
              expenses: Math.round(raw.total_expenses_paise / 100),
              profit: Math.round(raw.net_profit_paise / 100),
              cash: Math.round(raw.total_income_paise / 100),
            },
          ],
          topExpenses: raw.expenses
            .sort((a, b) => b.amount_paise - a.amount_paise)
            .slice(0, 5)
            .map((row) => ({ name: row.name, amount: Math.round(row.amount_paise / 100) })),
          gst: { output: 0, input: 0, netDue: 0 },
        })),

  /**
   * createPack — the backend expects `period_id`, not `fy`/`company`.
   * We first fetch the current period list and use the most recent open period.
   */
  createPack: async (): Promise<PackResponse> => {
    if (useMock) return mock.createMockPack();

    // Fetch available periods to find the current open one.
    const periods = await request<{ id: string; name: string; status: string }[]>("/periods");
    const openPeriod = periods.find((p) => p.status === "OPEN") ?? periods[0];
    if (!openPeriod) throw new Error("No accounting period found. Seed the backend first.");

    const raw = await request<{
      report_id: string;
      sha256: string;
      filename: string;
      anchor: { tx_hash?: string | null } | null;
    }>("/reports/pack", {
      method: "POST",
      body: JSON.stringify({ period_id: openPeriod.id }),
    });

    // Build a PackResponse from what the backend returns.
    const pnl = await api.getPnl();
    return {
      id: raw.report_id,
      generatedAt: new Date().toISOString(),
      hash: raw.sha256,
      anchorTx: raw.anchor?.tx_hash ?? "",
      signoffs: [{ name: "CA Demo", role: "Chartered Accountant", date: new Date().toLocaleDateString("en-GB") }],
      report: pnl,
    };
  },

  // ── Verification ──────────────────────────────────────────────────────────

  /**
   * verify — the backend exposes this at /public/verify (no /v1 prefix, no auth).
   */
  verify: (hash: string): Promise<VerifyResponse> =>
    useMock
      ? mock.verifyMockHash(hash)
      : requestPublic<{
          verdict: string;
          hash: string;
          anchor: { tx?: string | null } | null;
          signoffs: { name: string; role: string; time: string }[];
          report: { sources?: { filename?: string } } | null;
        }>(`/public/verify?hash=${encodeURIComponent(hash)}`).then((raw) => ({
          match: raw.verdict === "MATCH",
          hash: raw.hash,
          anchorTx: raw.anchor?.tx ?? undefined,
          signoffs: raw.signoffs.map((s) => ({ name: s.name, role: s.role, date: s.time.slice(0, 10) })),
          packName: raw.report?.sources?.filename,
          message:
            raw.verdict === "MATCH"
              ? "This report matches a signed, anchored record."
              : raw.verdict === "PENDING"
                ? "The report exists but has not been anchored yet."
                : "No signed report matches that hash.",
        })),
};
