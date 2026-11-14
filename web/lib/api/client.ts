/* Purpose: One typed boundary for exactly the versioned endpoints used by this frontend. */

import type { ApproveInput, ApproveResponse, CompanySnapshot, DocumentResponse, DraftJournalInput, Invoice, Journal, PackResponse, PnlReport, VerifyResponse } from "@/lib/api/types";
import * as mock from "@/lib/mock/service";
import { mockCompany } from "@/lib/mock/data";


export const useMock = process.env.NEXT_PUBLIC_USE_MOCK !== "false";
const baseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${baseUrl}/v1${path}`, { ...options, headers: { ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }), ...options.headers } });
  if (!response.ok) {
    const message = await response.text().catch(() => "");
    throw new Error(message || `The request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getCompanySnapshot: async (): Promise<CompanySnapshot> => useMock ? mock.listMockData() : ({ company: mockCompany, invoices: [], journals: [], ledger: [], pnl: { company: mockCompany.name, fy: mockCompany.fy, months: [], topExpenses: [], gst: { output: 0, input: 0, netDue: 0 } } }),
  createDocument: async (file: File): Promise<Invoice> => {
    if (useMock) return mock.uploadMockDocument(file);
    const form = new FormData(); form.append("file", file);
    const result = await request<DocumentResponse>("/documents", { method: "POST", body: form });
    return result.document;
  },
  draftJournal: (input: DraftJournalInput): Promise<Journal> => useMock ? mock.draftMockJournal(input) : request("/journals/draft", { method: "POST", body: JSON.stringify(input) }),
  postJournal: (id: string): Promise<Journal> => useMock ? mock.postMockJournal(id) : request(`/journals/${encodeURIComponent(id)}/post`, { method: "POST", body: JSON.stringify({}) }),
  approveJournal: (id: string, input: ApproveInput): Promise<ApproveResponse> => useMock ? mock.approveMockJournal(id, input) : request(`/approvals/${encodeURIComponent(id)}/approve`, { method: "POST", body: JSON.stringify(input) }),
  getPnl: (): Promise<PnlReport> => useMock ? mock.getMockPnl() : request("/reports/pnl"),
  createPack: (): Promise<PackResponse> => useMock ? mock.createMockPack() : request("/reports/pack", { method: "POST", body: JSON.stringify({ fy: "2026-27", company: "Acme Pvt Ltd" }) }),
  verify: (hash: string): Promise<VerifyResponse> => useMock ? mock.verifyMockHash(hash) : request(`/verify?hash=${encodeURIComponent(hash)}`),
};
