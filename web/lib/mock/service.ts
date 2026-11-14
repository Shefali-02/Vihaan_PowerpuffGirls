/* Purpose: In-memory demo implementations of the seven documented API calls. */

import type { ApproveInput, ApproveResponse, DraftJournalInput, Invoice, Journal, PackResponse, VerifyResponse } from "@/lib/api/types";
import { getMockSnapshot, mockInvoices, mockJournals, mockLedger, mockPnl } from "@/lib/mock/data";


let pack: PackResponse | null = null;
const pause = () => new Promise((resolve) => setTimeout(resolve, 180));

export async function listMockData() { await pause(); return getMockSnapshot(); }
export async function getMockPnl() { await pause(); return structuredClone(mockPnl); }

export async function uploadMockDocument(file: File): Promise<Invoice> {
  await pause();
  const invoice: Invoice = {
    id: `doc-${Date.now()}`, number: `INV-${String(2048 + mockInvoices.length).padStart(4, "0")}`,
    supplier: file.name.replace(/\.[^.]+$/, "").replace(/[-_]/g, " ") || "Uploaded supplier",
    date: new Intl.DateTimeFormat("en-GB").format(new Date()), dueDate: "14-12-2026",
    amount: 8500, base: 7203.39, tax: 1296.61, taxRate: 18, category: "General business expense",
    gstin: "27AABCU9603R1ZM", status: "DRAFT BY AI", description: "Newly uploaded invoice. Check supplier and tax values before posting.",
    ruleId: "EXP-DEFAULT-001", confidence: 0.82,
  };
  mockInvoices.unshift(invoice);
  return structuredClone(invoice);
}

export async function draftMockJournal(input: DraftJournalInput): Promise<Journal> {
  await pause();
  const id = `JRN-${1000 + mockJournals.length + 1}`;
  const journal: Journal = {
    id, invoiceId: input.invoiceId, description: input.description, date: input.date,
    preparedBy: "Asha Rao", status: "DRAFT BY AI",
    lines: input.lines.map((line, index) => ({ ...line, id: `${id}-${index + 1}` })),
  };
  mockJournals.push(journal);
  return structuredClone(journal);
}

export async function postMockJournal(id: string): Promise<Journal> {
  await pause();
  const journal = mockJournals.find((item) => item.id === id);
  if (!journal) throw new Error("That draft journal could not be found.");
  journal.status = "REVIEWED";
  const invoice = mockInvoices.find((item) => item.id === journal.invoiceId);
  if (invoice) invoice.status = "REVIEWED";
  return structuredClone(journal);
}

export async function approveMockJournal(id: string, input: ApproveInput): Promise<ApproveResponse> {
  await pause();
  const journal = mockJournals.find((item) => item.id === id);
  if (!journal) throw new Error("That approval could not be found.");
  if (journal.preparedBy === input.signer) throw new Error("A preparer cannot approve their own journal.");
  journal.status = "ANCHORED";
  const invoice = mockInvoices.find((item) => item.id === journal.invoiceId);
  if (invoice) invoice.status = "ANCHORED";
  return { journal: structuredClone(journal), trustState: "ANCHORED", signedBy: input.signer, anchorTx: `0x${journal.id.slice(-4).toLowerCase()}c91b6e` };
}

async function sha256(value: string) {
  if (globalThis.crypto?.subtle) {
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  return "8c1f0aa37cbb12a18a6645f34c00abfda540834ef0f59b3bdf04d371ac6092a0";
}

export async function createMockPack(): Promise<PackResponse> {
  await pause();
  const reportCopy = structuredClone(mockPnl);
  const hash = await sha256(JSON.stringify(reportCopy));
  pack = {
    id: `PACK-${Date.now()}`, generatedAt: new Date().toISOString(), hash,
    anchorTx: `0x${hash.slice(0, 24)}`, signoffs: [{ name: "Meera Iyer", role: "Chartered Accountant", date: "14-11-2026" }], report: reportCopy,
  };
  return structuredClone(pack);
}

export async function verifyMockHash(hash: string): Promise<VerifyResponse> {
  await pause();
  const normalized = hash.trim().replace(/^0x/i, "").toLowerCase();
  const candidate = pack?.hash ?? await sha256(JSON.stringify(mockPnl));
  const match = normalized === candidate.replace(/^0x/i, "").toLowerCase();
  return match
    ? { match: true, hash: candidate, anchorTx: pack?.anchorTx ?? `0x${candidate.slice(0, 24)}`, signoffs: pack?.signoffs ?? [{ name: "Meera Iyer", role: "Chartered Accountant", date: "14-11-2026" }], packName: "Acme Pvt Ltd · FY 2026–27", message: "This report matches the signed demo pack." }
    : { match: false, hash, message: "No signed report in this demo matches that hash." };
}

export async function getMockLedger() { await pause(); return structuredClone(mockLedger); }
