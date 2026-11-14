/* Purpose: Query and mutation hooks for each API endpoint and the read-only demo snapshot. */

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, useMock } from "@/lib/api/client";
import type { ApproveInput, CompanySnapshot, DraftJournalInput } from "@/lib/api/types";


export const useCompanySnapshot = () => useQuery({ queryKey: ["company-snapshot"], queryFn: api.getCompanySnapshot });
export const usePnlReport = () => useQuery({ queryKey: ["reports", "pnl"], queryFn: api.getPnl });
export const useVerify = (hash: string, enabled: boolean) => useQuery({ queryKey: ["verify", hash], queryFn: () => api.verify(hash), enabled, retry: false });

export function useCreateDocument() {
  const cache = useQueryClient();
  return useMutation({ mutationFn: api.createDocument, onSuccess: (invoice) => {
    if (useMock) void cache.invalidateQueries({ queryKey: ["company-snapshot"] });
    else cache.setQueryData<CompanySnapshot>(["company-snapshot"], (current) => current ? { ...current, invoices: [invoice, ...current.invoices] } : current);
  } });
}
export function useDraftJournal() {
  const cache = useQueryClient();
  return useMutation({ mutationFn: (input: DraftJournalInput) => api.draftJournal(input), onSuccess: (journal) => {
    if (useMock) void cache.invalidateQueries({ queryKey: ["company-snapshot"] });
    else cache.setQueryData<CompanySnapshot>(["company-snapshot"], (current) => current ? { ...current, journals: [journal, ...current.journals] } : current);
  } });
}
export function usePostJournal() {
  const cache = useQueryClient();
  return useMutation({ mutationFn: api.postJournal, onSuccess: (journal) => {
    if (useMock) void cache.invalidateQueries({ queryKey: ["company-snapshot"] });
    else cache.setQueryData<CompanySnapshot>(["company-snapshot"], (current) => current ? { ...current, journals: current.journals.map((item) => item.id === journal.id ? journal : item), invoices: current.invoices.map((item) => item.id === journal.invoiceId ? { ...item, status: journal.status } : item) } : current);
  } });
}
export function useApproveJournal() {
  const cache = useQueryClient();
  return useMutation({ mutationFn: ({ id, input }: { id: string; input: ApproveInput }) => api.approveJournal(id, input), onSuccess: (result) => {
    if (useMock) void cache.invalidateQueries({ queryKey: ["company-snapshot"] });
    else cache.setQueryData<CompanySnapshot>(["company-snapshot"], (current) => current ? { ...current, journals: current.journals.map((item) => item.id === result.journal.id ? result.journal : item), invoices: current.invoices.map((item) => item.id === result.journal.invoiceId ? { ...item, status: result.trustState } : item) } : current);
  } });
}
export function useCreatePack() {
  const cache = useQueryClient();
  return useMutation({ mutationFn: api.createPack, onSuccess: (pack) => { cache.setQueryData(["investor-pack"], pack); cache.invalidateQueries({ queryKey: ["verify"] }); } });
}
