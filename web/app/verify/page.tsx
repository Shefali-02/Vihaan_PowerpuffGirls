/* Purpose: Public, standalone report verification route without dashboard navigation. */

import { VerifyScreen } from "@/components/verify-screen";
import { Suspense } from "react";
import { LoadingState } from "@/components/ui/common";


export default function VerifyPage() { return <Suspense fallback={<div className="min-h-screen p-8"><LoadingState label="Preparing the public verifier" /></div>}><VerifyScreen /></Suspense>; }
