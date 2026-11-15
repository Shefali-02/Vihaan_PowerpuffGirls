/* Purpose: Share the demo Accountant/CA role selection across the app shell and review screens.
   When role changes, clears the cached JWT so ensureToken() re-authenticates as the new user. */
"use client";

import { createContext, useContext, useMemo, useState } from "react";
import { setActiveRole } from "@/lib/api/client";

type DemoRole = "Accountant" | "CA";

const RoleContext = createContext<{
  role: DemoRole;
  setRole: (role: DemoRole) => void;
} | null>(null);

export function RoleProvider({ children }: { children: React.ReactNode }) {
  const [role, setRoleState] = useState<DemoRole>("Accountant");

  const value = useMemo(() => ({
    role,
    setRole: (next: DemoRole) => {
      if (next !== role) {
        setActiveRole(next); // clears token + sets localStorage so ensureToken re-logins
      }
      setRoleState(next);
    },
  }), [role]);

  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
}

export function useDemoRole() {
  const value = useContext(RoleContext);
  if (!value) throw new Error("useDemoRole must be used within RoleProvider");
  return value;
}
