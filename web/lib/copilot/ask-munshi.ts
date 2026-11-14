/* Purpose: Local intent matcher that answers only from the bundled demo ledger. */

import { mockInvoices, mockJournals, mockLedger, mockPnl } from "@/lib/mock/data";
import { inr, inrLakh } from "@/lib/format";


export type LedgerCitation = { id: string; date: string; label: string; amount: string };
export type MunshiAnswer = { text: string; citations: LedgerCitation[]; label: "MOCK LLM" };

function citationsFor(accounts: string[], limit = 3): LedgerCitation[] {
  const matches = mockLedger.filter((entry) => accounts.some((account) => entry.account.toLowerCase().includes(account.toLowerCase()))).slice(-limit).reverse();
  const sources = matches.length ? matches : mockLedger.slice(-limit).reverse();
  return sources.map((entry) => ({ id: entry.id, date: entry.date, label: entry.account, amount: inr(entry.debit || entry.credit) }));
}

function invoiceDate(value: string) {
  const [day, month, year] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export async function askMunshi(question: string): Promise<MunshiAnswer> {
  await new Promise((resolve) => setTimeout(resolve, 420));
  const query = question.toLowerCase();
  const latest = mockPnl.months.at(-1)!;
  const previous = mockPnl.months.at(-2)!;
  const averageMonthlyExpense = mockPnl.months.reduce((sum, month) => sum + month.expenses, 0) / mockPnl.months.length;
  let text: string;
  let citations: LedgerCitation[];

  if (/runway|how long.*cash|cash.*last/.test(query)) {
    text = `At the October close, Acme had ${inrLakh(latest.cash)} in cash. Average monthly expenses over the six months were ${inrLakh(averageMonthlyExpense)}, giving an estimated runway of ${(latest.cash / averageMonthlyExpense).toFixed(1)} months at that pace.`;
    citations = citationsFor(["Salaries", "Freight", "Software"]);
  } else if (/gst|tax due|gstr/.test(query)) {
    text = `The mock GST summary shows ${inr(mockPnl.gst.netDue)} net GST due for October 2026. It is calculated from ${inr(mockPnl.gst.output)} collected on sales less ${inr(mockPnl.gst.input)} in input credit. The demo calendar lists 20-11-2026 as the filing date.`;
    citations = citationsFor(["Sales revenue", "Software"]);
  } else if (/top expenses|biggest expenses|spend most|largest expense/.test(query)) {
    const top = mockPnl.topExpenses.slice(0, 3);
    text = `The largest six-month expense groups in the mock P&L are ${top.map((item) => `${item.name} (${inr(item.amount)})`).join(", ")}.`;
    citations = citationsFor(top.map((item) => item.name));
  } else if (/month.on.month|compared to last|last month|p&l|profit and loss|profit/.test(query)) {
    const change = latest.profit - previous.profit;
    const direction = change >= 0 ? "increased" : "decreased";
    text = `October net profit was ${inr(latest.profit)}, compared with ${inr(previous.profit)} in September. That ${direction} by ${inr(Math.abs(change))} month on month (${Math.abs(change / previous.profit * 100).toFixed(1)}%).`;
    citations = citationsFor(["Sales revenue", "Salaries"]);
  } else if (/pending|open review|approval|waiting.*review/.test(query)) {
    const drafts = mockJournals.filter((journal) => journal.status === "DRAFT BY AI").length;
    const caQueue = mockJournals.filter((journal) => journal.status === "REVIEWED").length;
    text = `There are ${drafts} journal draft${drafts === 1 ? "" : "s"} to review and ${caQueue} posted entr${caQueue === 1 ? "y" : "ies"} waiting for CA sign-off in this demo.`;
    citations = mockJournals.filter((journal) => journal.status !== "ANCHORED").slice(0, 3).map((journal) => ({ id: journal.id, date: journal.date, label: journal.description, amount: inr(journal.lines.reduce((sum, line) => sum + line.debit, 0)) }));
  } else if (/overdue|past due|late invoice|overdue invoice/.test(query)) {
    const now = new Date(2026, 10, 14);
    const overdue = mockInvoices.filter((invoice) => invoiceDate(invoice.dueDate) < now);
    text = overdue.length ? `${overdue.length} supplier invoice${overdue.length === 1 ? " is" : "s are"} overdue in the mock inbox. ${overdue.map((invoice) => `${invoice.supplier}: ${inr(invoice.amount)}, due ${invoice.dueDate}`).join("; ")}.` : "I don’t see any overdue supplier invoices in the mock inbox.";
    citations = overdue.length ? overdue.map((invoice) => ({ id: invoice.id, date: invoice.dueDate, label: `${invoice.supplier} · ${invoice.number}`, amount: inr(invoice.amount) })) : citationsFor(["Sales revenue"]);
  } else if (/cash|bank balance|money in bank/.test(query)) {
    text = `At the October close, Acme’s cash and bank balance was ${inrLakh(latest.cash)}. The mock series moved from ${inrLakh(mockPnl.months[0].cash)} in May to ${inrLakh(latest.cash)} in October.`;
    citations = citationsFor(["Sales revenue", "Salaries"]);
  } else {
    text = "I can’t answer that from the demo ledger. Try asking about cash, runway, GST due, top expenses, month-on-month profit, pending reviews, or overdue invoices.";
    citations = citationsFor(["Sales revenue", "Salaries"]);
  }
  return { text, citations, label: "MOCK LLM" };
}
