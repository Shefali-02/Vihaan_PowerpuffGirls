/* Purpose: Realistic single-company seed data for the complete local demo. */

import type { Invoice, Journal, JournalLine, PnlReport } from "@/lib/api/types";


export const mockCompany = { name: "Acme Pvt Ltd", gstin: "27AABCU9603R1ZM", fy: "2026–27", preparer: "Asha Rao", ca: "Meera Iyer" };

export const mockInvoices: Invoice[] = [
  { id: "doc-2045", number: "INV-2045", supplier: "Shree Paper Co.", date: "18-10-2026", dueDate: "05-11-2026", amount: 18400, base: 15593.22, tax: 2806.78, taxRate: 18, category: "Office supplies", gstin: "27AAECS1188Q1Z6", status: "REVIEWED", description: "Printer paper and stationery for the office", ruleId: "EXP-OFFICE-018", confidence: 0.97 },
  { id: "doc-2046", number: "INV-2046", supplier: "Cloudline Software India", date: "02-11-2026", dueDate: "02-12-2026", amount: 5900, base: 5000, tax: 900, taxRate: 18, category: "Software subscriptions", gstin: "29AACCC4421K1Z7", status: "DRAFT BY AI", description: "Monthly accounting and collaboration plan", ruleId: "EXP-SOFTWARE-004", confidence: 0.94 },
  { id: "doc-2047", number: "INV-2047", supplier: "Metro Transport Services", date: "09-11-2026", dueDate: "09-12-2026", amount: 12600, base: 12000, tax: 600, taxRate: 5, category: "Freight and delivery", gstin: "27AAGFM2938P1Z5", status: "DRAFT BY AI", description: "Local delivery of customer orders", ruleId: "EXP-LOGISTICS-011", confidence: 0.91 },
];

const lines = (id: string, invoice: Invoice): JournalLine[] => [
  { id: `${id}-1`, account: invoice.category, debit: invoice.base, credit: 0, source: "Invoice total before tax" },
  { id: `${id}-2`, account: "Input GST credit", debit: invoice.tax, credit: 0, source: "Invoice GST amount" },
  { id: `${id}-3`, account: "Accounts payable", debit: 0, credit: invoice.amount, source: "Supplier amount due" },
];

export const mockJournals: Journal[] = [
  { id: "JRN-1001", invoiceId: "doc-2045", description: "Shree Paper Co. — INV-2045", date: "18-10-2026", preparedBy: "Asha Rao", status: "REVIEWED", lines: lines("JRN-1001", mockInvoices[0]) },
  { id: "JRN-1002", invoiceId: "doc-2046", description: "Cloudline Software India — INV-2046", date: "02-11-2026", preparedBy: "Asha Rao", status: "DRAFT BY AI", lines: lines("JRN-1002", mockInvoices[1]) },
  { id: "JRN-1003", invoiceId: "doc-2047", description: "Metro Transport Services — INV-2047", date: "09-11-2026", preparedBy: "Meera Iyer", status: "REVIEWED", lines: lines("JRN-1003", mockInvoices[2]) },
];

const months = [
  { month: "May 2026", revenue: 1870000, expenses: 1210000, profit: 660000, cash: 3620000 },
  { month: "Jun 2026", revenue: 1960000, expenses: 1230000, profit: 730000, cash: 3980000 },
  { month: "Jul 2026", revenue: 1820000, expenses: 1390000, profit: 430000, cash: 3740000 },
  { month: "Aug 2026", revenue: 2130000, expenses: 1280000, profit: 850000, cash: 4410000 },
  { month: "Sep 2026", revenue: 2220000, expenses: 1340000, profit: 880000, cash: 4680000 },
  { month: "Oct 2026", revenue: 2480000, expenses: 1510000, profit: 970000, cash: 5260000 },
];

export const mockPnl: PnlReport = {
  company: mockCompany.name, fy: mockCompany.fy, months,
  topExpenses: [{ name: "Salaries and benefits", amount: 4260000 }, { name: "Freight and delivery", amount: 1115000 }, { name: "Office rent", amount: 1080000 }, { name: "Software subscriptions", amount: 684000 }, { name: "Office supplies", amount: 522000 }],
  gst: { output: 864000, input: 515800, netDue: 348200 },
};

const ledgerTemplates = [
  { account: "Sales revenue", amount: [1870000, 1960000, 1820000, 2130000, 2220000, 2480000], side: "credit" },
  { account: "Salaries and benefits", amount: [690000, 705000, 712000, 706000, 721000, 726000], side: "debit" },
  { account: "Office rent", amount: [180000, 180000, 180000, 180000, 180000, 180000], side: "debit" },
  { account: "Software subscriptions", amount: [108000, 110000, 112000, 113000, 115000, 126000], side: "debit" },
  { account: "Freight and delivery", amount: [232000, 235000, 386000, 281000, 324000, 478000], side: "debit" },
] as const;
const periodDates = ["31-05-2026", "30-06-2026", "31-07-2026", "31-08-2026", "30-09-2026", "31-10-2026"];

export const mockLedger = months.flatMap((month, monthIndex) => ledgerTemplates.map((template, rowIndex) => ({
  id: `LED-${String(monthIndex * 5 + rowIndex + 1).padStart(3, "0")}`,
  date: periodDates[monthIndex], period: month.month, account: template.account,
  debit: template.side === "debit" ? template.amount[monthIndex] : 0,
  credit: template.side === "credit" ? template.amount[monthIndex] : 0,
  source: `Monthly close · ${month.month}`, status: monthIndex === 5 ? "REVIEWED" : "ANCHORED",
}))) as { id: string; date: string; period: string; account: string; debit: number; credit: number; source: string; status: string }[];

export function getMockSnapshot() {
  return { company: mockCompany, invoices: mockInvoices, journals: mockJournals, ledger: mockLedger, pnl: mockPnl };
}
