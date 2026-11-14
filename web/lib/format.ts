/* Purpose: Indian currency, grouping, and ledger date display helpers. */
export const inr = (value: number, maximumFractionDigits = 0) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits }).format(value);
export const inrLakh = (value: number) => `${new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 }).format(value / 100_000)}L`;
export const shortDate = (value: string) => value;
export const dateDDMMYYYY = (value: string | Date) => {
  const date = typeof value === "string" ? new Date(value) : value;
  return `${String(date.getDate()).padStart(2, "0")}-${String(date.getMonth() + 1).padStart(2, "0")}-${date.getFullYear()}`;
};
