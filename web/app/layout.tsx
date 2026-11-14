/* Purpose: Application metadata and the authenticated dashboard frame. */

import type { Metadata } from "next";
import "./globals.css";
import { SiteShell } from "@/components/site-shell";
import { QueryProvider } from "@/components/query-provider";
import { RoleProvider } from "@/contexts/role-context";


export const metadata: Metadata = {
  title: "Munshi — your books, in order",
  description: "A clear, reviewable ledger for Indian small businesses.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" data-scroll-behavior="smooth"><body><QueryProvider><RoleProvider><SiteShell>{children}</SiteShell></RoleProvider></QueryProvider></body></html>;
}
