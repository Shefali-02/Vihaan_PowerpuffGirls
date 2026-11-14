/* Purpose: Accessible six-month cash trend chart used on Today. */

"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";


const fallbackData = [
  { month: "May", amount: 36.2 }, { month: "Jun", amount: 39.8 }, { month: "Jul", amount: 37.4 },
  { month: "Aug", amount: 44.1 }, { month: "Sep", amount: 46.8 }, { month: "Oct", amount: 52.6 },
];
const inr = (value: number) => `₹${value.toFixed(1)}L`;

export function CashChart({ data = fallbackData }: { data?: { month: string; amount: number }[] }) {
  return <div className="h-[260px] w-full" role="img" aria-label="Closing cash increased from 36 lakh in May to 52.6 lakh in October">
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 14, right: 8, left: -18, bottom: 0 }}>
        <defs><linearGradient id="cashFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#e8743b" stopOpacity={0.3} /><stop offset="92%" stopColor="#f4b63f" stopOpacity={0.015} /></linearGradient></defs>
        <CartesianGrid stroke="#eee5d8" strokeDasharray="3 5" vertical={false} />
        <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: "#756653", fontSize: 12 }} dy={10} />
        <YAxis tickFormatter={inr} axisLine={false} tickLine={false} tick={{ fill: "#756653", fontSize: 11 }} />
        <Tooltip formatter={(value) => [inr(Number(value)), "Closing cash"]} contentStyle={{ borderRadius: 12, borderColor: "#eadfce", fontSize: 12 }} />
        <Area type="monotone" dataKey="amount" stroke="#c45b27" strokeWidth={3} fill="url(#cashFill)" activeDot={{ r: 5, fill: "#b84d1b", stroke: "#fff" }} />
      </AreaChart>
    </ResponsiveContainer>
  </div>;
}
