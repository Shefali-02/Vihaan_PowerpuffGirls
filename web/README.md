# Munshi Web

Frontend for Munshi, a demo AI accountant for Indian small businesses. Built with Next.js App Router, TypeScript, Tailwind CSS, shadcn-style accessible components, TanStack Query, Recharts, and `qrcode.react` for the pack QR code. This app does not contain backend code.

## Run locally

```bash
npm install
cp .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). On Windows PowerShell, copy the sample environment with `Copy-Item .env.example .env.local`.

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_USE_MOCK` | `true` | Use the Acme demo company and local mock API. Set to `false` to call the real API for the documented endpoints. |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Backend origin; the client adds the `/v1` prefix. |

The brief defines no list endpoints for invoices or journals. In Sandbox mode those queues start empty and fill from successful actions in the current browser session. Reports, pack creation, document upload, journal post, CA approval, and verification use only the specified API routes.

## Routes

- `/` — Today overview and cash chart.
- `/inbox` — Upload invoice, inspect proposal, and see the explanation.
- `/review` — Check balanced journals and post to the ledger.
- `/approvals` — CA queue, source comparison, and approval signature.
- `/reports` — Profit and loss and GST summary.
- `/investor-pack` — Generate a report pack, QR code, hash, and PDF.
- `/verify` — Public PDF or hash verification without the app sidebar.

## Folder map

- `app/` — App Router pages, root layout, and global design tokens.
- `components/` — Reusable shell, route screens, charts, assistant, and UI states.
- `contexts/` — Shared Accountant/CA demo role.
- `lib/api/` — Typed `/v1` client, request types, and TanStack Query hooks.
- `lib/mock/` — Acme invoices, 30 ledger entries, six reporting months, and mock API behavior.
- `lib/copilot/` — Local intent matcher that answers from mock records and cites its sources.
- `lib/` — Currency/date helpers and the small demo PDF generator.

For the file-by-file explanation and the two-minute walkthrough, see [`docs/FRONTEND.md`](../../docs/FRONTEND.md).
