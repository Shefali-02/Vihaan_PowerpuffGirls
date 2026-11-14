/* Purpose: Share the demo Accountant/CA role selection across the app shell and review screens. */

"use client";

import { createContext, useContext, useMemo, useState } from "react";


type DemoRole = "Accountant" | "CA";
const RoleContext = createContext<{ role: DemoRole; setRole: (role: DemoRole) => void } | null>(null);

export function RoleProvider({ children }: { children: React.ReactNode }) {
  const [role, setRole] = useState<DemoRole>("Accountant");
  const value = useMemo(() => ({ role, setRole }), [role]);
  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
}

export function useDemoRole() {
  const value = useContext(RoleContext);
  if (!value) throw new Error("useDemoRole must be used within RoleProvider");
  return value;
}
