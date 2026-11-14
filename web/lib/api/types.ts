/* Purpose: Shared frontend contracts for the versioned accounting API. */
export type TrustState = "DRAFT BY AI" | "REVIEWED" | "APPROVED" | "ANCHORED";
export type DemoRole = "Accountant" | "CA";
export type Invoice = {
  id: string; number: string; supplier: string; date: string; dueDate: string; amount: number;
  base: number; tax: number; taxRate: number; category: string; gstin: string; status: TrustState;
  description: string; ruleId: string; confidence: number;
};
export type JournalLine = { id: string; account: string; debit: number; credit: number; source: string };
export type Journal = { id: string; invoiceId: string; description: string; date: string; preparedBy: string; status: TrustState; lines: JournalLine[] };
export type DocumentResponse = { document: Invoice; journal: Journal };
export type PnlMonth = { month: string; revenue: number; expenses: number; profit: number; cash: number };
export type PnlReport = { company: string; fy: string; months: PnlMonth[]; topExpenses: { name: string; amount: number }[]; gst: { output: number; input: number; netDue: number } };
export type PackResponse = { id: string; generatedAt: string; hash: string; anchorTx: string; signoffs: { name: string; role: string; date: string }[]; report: PnlReport };
export type VerifyResponse = { match: boolean; hash: string; anchorTx?: string; signoffs?: PackResponse["signoffs"]; packName?: string; message: string };
export type DraftJournalInput = { invoiceId: string; description: string; date: string; lines: Omit<JournalLine, "id">[] };
export type ApproveInput = { note?: string; signer: string };
export type VerifyInput = { hash: string };
export type ApproveResponse = { journal: Journal; trustState: TrustState; signedBy: string; anchorTx: string };
export type CompanySnapshot = { company: { name: string; gstin: string; fy: string; preparer: string; ca: string }; invoices: Invoice[]; journals: Journal[]; ledger: { id: string; date: string; period: string; account: string; debit: number; credit: number; source: string; status: string }[]; pnl: PnlReport };
