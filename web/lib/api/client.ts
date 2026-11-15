/*
 * Purpose: One typed boundary for exactly the versioned endpoints used by this frontend.
 *
 * Live mode (NEXT_PUBLIC_USE_MOCK=false):
 *   - All calls go to NEXT_PUBLIC_API_BASE_URL (default http://localhost:8000).
 *   - On the first real request the client auto-logs in using the current role's
 *     credentials and caches the JWT in sessionStorage under "munshi_token".
 *     Call auth.logout() or setActiveRole() to clear and re-login.
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

/** Called by RoleProvider when the user switches role. Clears token and stores role. */
export function setActiveRole(role: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("munshi_role", role);
    auth.logout();
  }
}

// ---------------------------------------------------------------------------
// Auto-login — credentials keyed by demo role
// ---------------------------------------------------------------------------

const ROLE_CREDENTIALS: Record<string, { email: string; password: string }> = {
  Accountant: { email: "accountant@acme.demo", password: "demo1234" },
  CA:         { email: "ca@ca-firm.demo",       password: "demo1234" },
  Investor:   { email: "investor@acme.demo",    password: "demo1234" },
};

async function ensureToken(): Promise<string> {
  const existing = getToken();
  if (existing) return existing;

  const role = (typeof window !== "undefined" ? localStorage.getItem("munshi_role") : null) ?? "Accountant";
  const creds = ROLE_CREDENTIALS[role] ?? ROLE_CREDENTIALS["Accountant"];

  const response = await fetch(`${baseUrl}/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: creds.email, password: creds.password }),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    let message = `Login failed (${response.status}). Make sure the backend is running and seeded.`;
    try {
      const prob = JSON.parse(text) as { detail?: string };
      if (typeof prob.detail === "string") message = prob.detail;
    } catch { if (text) message = text; }
    throw new Error(message);
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

  const makeHeaders = (tok: string) => ({
    Authorization: `Bearer ${tok}`,
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...options.headers,
  });

  const fetchOnce = async (tok: string) => fetch(`${baseUrl}/v1${path}`, { ...options, headers: makeHeaders(tok) });

  let response = await fetchOnce(token);

  if (response.status === 401) {
    auth.logout();
    const freshToken = await ensureToken();
    response = await fetchOnce(freshToken);
  }

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    let message = `The request failed (${response.status}).`;
    try {
      const prob = JSON.parse(text) as {
        detail?: string | { msg: string }[];
        reasons?: { message: string }[];
        code?: string;
      };
      if (Array.isArray(prob.reasons) && prob.reasons.length > 0) {
        message = prob.reasons.map((r) => r.message).join("; ");
      } else if (typeof prob.detail === "string") {
        message = prob.detail;
      } else if (Array.isArray(prob.detail)) {
        message = prob.detail.map((d) => d.msg).join("; ");
      }
    } catch { if (text) message = text; }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Generic request helper for public routes (no /v1 prefix, no auth)
// ---------------------------------------------------------------------------

async function requestPublic<T>(path: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`);
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(text || `The request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Shape adapters
// ---------------------------------------------------------------------------

type ProposalRaw = {
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
};

function proposalToInvoice(proposal: ProposalRaw): Invoice {
  const facts = (proposal.facts ?? {}) as Record<string, unknown>;
  const totalPaise = proposal.total_paise ?? 0;

  // InvoiceFacts stores gst_rate_bp in basis points on lines[0]
  const lines = (facts.lines as { gst_rate_bp?: number }[] | undefined) ?? [];
  const gstRateBp = lines[0]?.gst_rate_bp ?? 1800;
  const taxRate = gstRateBp / 100;
  const base = totalPaise > 0 ? Math.round((totalPaise / (1 + taxRate / 100)) / 100) : 0;
  const tax  = totalPaise > 0 ? Math.round(totalPaise / 100) - base : 0;

  const statusMap: Record<string, Invoice["status"]> = {
    DRAFT_AI:              "DRAFT BY AI",
    NEEDS_REVIEW:          "NEEDS REVIEW",
    DUPLICATE:             "DUPLICATE",
    MANUAL_ENTRY_REQUIRED: "MANUAL ENTRY",
    APPROVED:              "APPROVED",
    ANCHORED:              "ANCHORED",
  };

  return {
    id:          proposal.document_id,
    number:      (facts.invoice_no as string | undefined) ?? proposal.document_id.slice(-8).toUpperCase(),
    supplier:    (facts.counterparty_name as string | undefined) ?? "Unknown supplier",
    date:        (facts.invoice_date as string | undefined) ?? (proposal.created_at?.slice(0, 10) ?? ""),
    dueDate:     "",
    amount:      Math.round(totalPaise / 100),
    base,
    tax,
    taxRate,
    category:    (facts.category as string | undefined) ?? proposal.doc_type ?? "General",
    gstin:       (facts.counterparty_gstin as string | undefined) ?? "",
    status:      statusMap[proposal.status] ?? "NEEDS REVIEW",
    description: proposal.reasons.join("; ") || "AI-extracted document",
    ruleId:      proposal.ruleset_version ?? "UNKNOWN",
    confidence:  0.9,
  };
}

type JournalRaw = {
  id: string;
  source_document_id: string | null;
  narration: string;
  entry_date: string;
  created_by: string;
  status: string;
  lines: { line_no: number; account_code: string; debit_paise: number; credit_paise: number; memo: string }[];
};

function journalOutToJournal(j: JournalRaw): Journal {
  const statusMap: Record<string, Journal["status"]> = {
    DRAFT:    "DRAFT BY AI",
    POSTED:   "REVIEWED",
    APPROVED: "APPROVED",
    ANCHORED: "ANCHORED",
  };
  return {
    id:          j.id,
    invoiceId:   j.source_document_id ?? "",
    description: j.narration,
    date:        j.entry_date,
    preparedBy:  j.created_by,
    status:      statusMap[j.status] ?? "DRAFT BY AI",
    lines:       j.lines.map((line) => ({
      id:      `${j.id}-${line.line_no}`,
      account: line.account_code,
      debit:   Math.round(line.debit_paise / 100),
      credit:  Math.round(line.credit_paise / 100),
      source:  line.memo,
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

    const [me, proposalsRaw, pnlRaw, periodsRaw, gstRaw] = await Promise.all([
      request<{
        name: string; email: string;
        workspace: { name: string; gstin: string };
        workspace_id: string; role: string;
      }>("/auth/me"),
      request<{ items: ProposalRaw[] }>("/proposals"),
      request<{
        total_income_paise: number; total_expenses_paise: number; net_profit_paise: number;
        income: { code: string; name: string; amount_paise: number; amount: string }[];
        expenses: { code: string; name: string; amount_paise: number; amount: string }[];
      }>("/reports/pnl"),
      request<{ id: string; name: string; status: string }[]>("/periods"),
      request<{
        output_cgst_paise: number; output_sgst_paise: number; output_igst_paise: number;
        itc_cgst_paise: number; itc_sgst_paise: number; itc_igst_paise: number;
        net_payable_paise: number;
      }>("/tax/gst/summary").catch(() => null),
    ]);

    const invoices = proposalsRaw.items.map(proposalToInvoice);

    // Fetch draft journals from draft_entry_ids
    const draftEntryIds = proposalsRaw.items
      .map((p) => p.draft_entry_id)
      .filter((id): id is string => !!id);
    const journals = (await Promise.all(
      draftEntryIds.map((id) =>
        request<JournalRaw>(`/journals/${encodeURIComponent(id)}`).then(journalOutToJournal).catch(() => null)
      )
    )).filter((j): j is Journal => j !== null);

    const gst = gstRaw
      ? {
          output: Math.round((gstRaw.output_cgst_paise + gstRaw.output_sgst_paise + gstRaw.output_igst_paise) / 100),
          input:  Math.round((gstRaw.itc_cgst_paise + gstRaw.itc_sgst_paise + gstRaw.itc_igst_paise) / 100),
          netDue: Math.round(gstRaw.net_payable_paise / 100),
        }
      : { output: 0, input: 0, netDue: 0 };

    // Build fy string from first period name e.g. "FY2026-27" -> "2026-27"
    const fyRaw = periodsRaw[0]?.name ?? "FY2026-27";
    const fy = fyRaw.replace(/^FY/, "").replace("-", "–");

    const pnl: PnlReport = {
      company: me.workspace.name,
      fy,
      months: [{
        month:    "Current period",
        revenue:  Math.round(pnlRaw.total_income_paise / 100),
        expenses: Math.round(pnlRaw.total_expenses_paise / 100),
        profit:   Math.round(pnlRaw.net_profit_paise / 100),
        cash:     Math.round(pnlRaw.total_income_paise / 100),
      }],
      topExpenses: pnlRaw.expenses
        .sort((a, b) => b.amount_paise - a.amount_paise)
        .slice(0, 5)
        .map((row) => ({ name: row.name, amount: Math.round(row.amount_paise / 100) })),
      gst,
    };

    return {
      company: { name: me.workspace.name, gstin: me.workspace.gstin, fy, preparer: me.name, ca: me.name },
      invoices,
      journals,
      ledger: [],
      pnl,
    };
  },

  // ── Documents ─────────────────────────────────────────────────────────────

  createDocument: async (file: File): Promise<Invoice> => {
    if (useMock) return mock.uploadMockDocument(file);
    const form = new FormData();
    form.append("file", file);
    const result = await request<{ id: string; proposal: ProposalRaw | null }>("/documents", {
      method: "POST",
      body: form,
    });
    if (result.proposal) return proposalToInvoice(result.proposal);
    return {
      id: result.id, number: result.id.slice(-8).toUpperCase(),
      supplier: "Uploaded document", date: new Date().toLocaleDateString("en-GB"), dueDate: "",
      amount: 0, base: 0, tax: 0, taxRate: 18, category: "General", gstin: "",
      status: "MANUAL ENTRY", description: "Document uploaded — no proposal generated yet.",
      ruleId: "UNKNOWN", confidence: 0,
    };
  },

  // ── Journals ──────────────────────────────────────────────────────────────

  draftJournal: async (input: DraftJournalInput): Promise<Journal> => {
    if (useMock) return mock.draftMockJournal(input);

    // Check if pipeline already created a draft for this document
    const proposalsRaw = await request<{ items: { document_id: string; draft_entry_id: string | null }[] }>("/proposals");
    const existing = proposalsRaw.items.find((p) => p.document_id === input.invoiceId);
    if (existing?.draft_entry_id) {
      return request<JournalRaw>(`/journals/${encodeURIComponent(existing.draft_entry_id)}`).then(journalOutToJournal);
    }

    // Manual draft path: reconstruct InvoiceFacts, snapping GST rate to nearest valid slab
    const VALID_SLABS_BP = [0, 500, 1200, 1800, 2800];
    const snap = (bp: number) => VALID_SLABS_BP.reduce((b, s) => (Math.abs(s - bp) < Math.abs(b - bp) ? s : b));

    const totalRupees = input.lines.reduce((sum, l) => sum + l.debit, 0);
    const gstLine     = input.lines.find((l) => l.account.toLowerCase().includes("gst"));
    const taxRupees   = gstLine ? gstLine.debit : 0;
    const baseRupees  = totalRupees - taxRupees;
    const taxablePaise = Math.round(baseRupees * 100);

    if (taxablePaise <= 0) {
      throw new Error(
        "Cannot create a draft: the invoice base amount is zero or missing. " +
        "Go to the Review screen — the pipeline may have already drafted this entry."
      );
    }

    const rawBp     = baseRupees > 0 ? Math.round((taxRupees / baseRupees) * 10000) : 1800;
    const gstRateBp = snap(rawBp);

    let invoiceDateIso = input.date;
    if (/^\d{2}-\d{2}-\d{4}$/.test(input.date)) {
      const [dd, mm, yyyy] = input.date.split("-");
      invoiceDateIso = `${yyyy}-${mm}-${dd}`;
    }

    return request<JournalRaw>("/journals/draft", {
      method: "POST",
      body: JSON.stringify({
        doc_type: "purchase_invoice",
        invoice_no: input.invoiceId,
        invoice_date: invoiceDateIso,
        counterparty_name: input.description.split(" — ")[0] ?? input.description,
        counterparty_gstin: null,
        category: input.lines[0]?.account ?? null,
        lines: [{ description: input.description, taxable_paise: taxablePaise, gst_rate_bp: gstRateBp }],
        declared_total_paise: Math.round(totalRupees * 100),
      }),
    }).then(journalOutToJournal);
  },

  postJournal: (id: string): Promise<Journal> =>
    useMock
      ? mock.postMockJournal(id)
      : request<JournalRaw>(`/journals/${encodeURIComponent(id)}/post`, { method: "POST", body: JSON.stringify({}) })
          .then(journalOutToJournal),

  // ── Approvals ─────────────────────────────────────────────────────────────

  approveJournal: (id: string, input: ApproveInput): Promise<ApproveResponse> =>
    useMock
      ? mock.approveMockJournal(id, input)
      : request<{
          state: string; decided_by: string | null;
          anchor_batch: { tx_hash?: string } | null;
          snapshot: JournalRaw;
        }>(`/approvals/${encodeURIComponent(id)}/approve`, {
            method: "POST",
            body: JSON.stringify({ note: input.note }),
          })
          .then((res) => ({
            journal:    journalOutToJournal(res.snapshot),
            trustState: "ANCHORED" as const,
            signedBy:   res.decided_by ?? input.signer,
            anchorTx:   res.anchor_batch?.tx_hash ?? "",
          })),

  // ── Reports ───────────────────────────────────────────────────────────────

  getPnl: async (): Promise<PnlReport> => {
    if (useMock) return mock.getMockPnl();

    const [pnlRaw, gstRaw, meRaw, periodsRaw] = await Promise.all([
      request<{
        total_income_paise: number; total_expenses_paise: number; net_profit_paise: number;
        expenses: { code: string; name: string; amount_paise: number; amount: string }[];
      }>("/reports/pnl"),
      request<{
        output_cgst_paise: number; output_sgst_paise: number; output_igst_paise: number;
        itc_cgst_paise: number; itc_sgst_paise: number; itc_igst_paise: number;
        net_payable_paise: number;
      }>("/tax/gst/summary").catch(() => null),
      request<{ name: string; workspace: { name: string } }>("/auth/me"),
      request<{ name: string }[]>("/periods"),
    ]);

    const gst = gstRaw
      ? {
          output: Math.round((gstRaw.output_cgst_paise + gstRaw.output_sgst_paise + gstRaw.output_igst_paise) / 100),
          input:  Math.round((gstRaw.itc_cgst_paise + gstRaw.itc_sgst_paise + gstRaw.itc_igst_paise) / 100),
          netDue: Math.round(gstRaw.net_payable_paise / 100),
        }
      : { output: 0, input: 0, netDue: 0 };

    const fyRaw = periodsRaw[0]?.name ?? "FY2026-27";
    const fy = fyRaw.replace(/^FY/, "").replace("-", "–");

    return {
      company: meRaw.workspace.name,
      fy,
      months: [{
        month:    "Current period",
        revenue:  Math.round(pnlRaw.total_income_paise / 100),
        expenses: Math.round(pnlRaw.total_expenses_paise / 100),
        profit:   Math.round(pnlRaw.net_profit_paise / 100),
        cash:     Math.round(pnlRaw.total_income_paise / 100),
      }],
      topExpenses: pnlRaw.expenses
        .sort((a, b) => b.amount_paise - a.amount_paise)
        .slice(0, 5)
        .map((row) => ({ name: row.name, amount: Math.round(row.amount_paise / 100) })),
      gst,
    };
  },

  createPack: async (): Promise<PackResponse> => {
    if (useMock) return mock.createMockPack();

    const periods = await request<{ id: string; name: string; status: string }[]>("/periods");
    const openPeriod = periods.find((p) => p.status === "OPEN") ?? periods[0];
    if (!openPeriod) throw new Error("No accounting period found. Seed the backend first.");

    const raw = await request<{ report_id: string; sha256: string; anchor: { tx_hash?: string | null } | null }>(
      "/reports/pack",
      { method: "POST", body: JSON.stringify({ period_id: openPeriod.id }) }
    );

    // Read real signoffs from the proof
    const proof = await request<{ signoffs?: { name: string; role: string; time: string }[] }>(
      `/reports/${raw.report_id}/proof`
    ).catch(() => null);

    const signoffs = proof?.signoffs?.map((s) => ({ name: s.name, role: s.role, date: s.time.slice(0, 10) }))
      ?? [{ name: "CA Demo", role: "Chartered Accountant", date: new Date().toLocaleDateString("en-GB") }];

    const pnl = await api.getPnl();
    return {
      id:           raw.report_id,
      generatedAt:  new Date().toISOString(),
      hash:         raw.sha256,
      anchorTx:     raw.anchor?.tx_hash ?? "",
      signoffs,
      report:       pnl,
    };
  },

  // ── Verification ──────────────────────────────────────────────────────────

  verify: (hash: string): Promise<VerifyResponse> =>
    useMock
      ? mock.verifyMockHash(hash)
      : requestPublic<{
          verdict: string; hash: string;
          anchor: { tx?: string | null } | null;
          signoffs: { name: string; role: string; time: string }[];
          report: Record<string, unknown> | null;
        }>(`/public/verify?hash=${encodeURIComponent(hash)}`)
          .then((raw) => ({
            match:    raw.verdict === "MATCH",
            hash:     raw.hash,
            anchorTx: raw.anchor?.tx ?? undefined,
            signoffs: raw.signoffs.map((s) => ({ name: s.name, role: s.role, date: s.time.slice(0, 10) })),
            message:  raw.verdict === "MATCH"
              ? "This report matches a signed, anchored record."
              : raw.verdict === "PENDING"
                ? "The report exists but has not been anchored yet."
                : "No signed report matches that hash.",
          })),
};
