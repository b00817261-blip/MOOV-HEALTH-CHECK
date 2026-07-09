# MOOV — Daily Operations (web)

A standalone website for the daily loop between a manager, group leaders, and
employees. It's a **front-end prototype**: all data lives in the browser
(`localStorage`), so there's no server, database, or login to run. Use the
**role switcher** in the top bar to see all three sides.

## What's in it

| View | Who | What it shows |
|------|-----|---------------|
| **Daily sheet** | Manager | A simple list of *what got done today, grouped by group*, each line with the little **source badge** on the side — where it was submitted (Smart MOOV / Email / WhatsApp / Phone) — and the time. Below it, **overdue by group**. |
| **Daily status** | Manager / boss | The end-of-day check. Overdue tasks at the bottom, each with an **"Ask why it hasn't been done"** button that sends the question to that group's leader. Their reason appears here once they reply. |
| **Group leader** | Leaders | Notifications — *"Derek asks why this hasn't been done"* — answered with a **multiple-choice reason and/or your own words**. Also lists your group's overdue tasks. |
| **Employee** | Employees | *My tasks*, with due dates in plain language — **"Tomorrow · Jul 10"**, **"Overdue · Jul 7"** — and a one-tap **Mark done**. |
| **Groups** | Manager | Add a group by naming it and picking a **lead** (and members) from a scroll-and-click list of registered people. New groups show up on the daily sheet. |

## Run locally

```bash
cd web
npm install
npm run dev      # http://localhost:5173
```

Other scripts: `npm run build` (production build to `dist/`), `npm run preview`
(serve the build), `npm run typecheck`.

## Deploy to Vercel

This is a standard Vite app — Vercel detects it automatically.

**From the dashboard:** New Project → import the repo → set **Root Directory**
to `web` → Deploy. (Framework preset: *Vite*, build `npm run build`, output
`dist` — all auto-filled.)

**From the CLI:**

```bash
npm i -g vercel
cd web
vercel            # follow the prompts, accept the Vite defaults
vercel --prod     # promote to production
```

`vercel.json` is included so client-side routing and the SPA fallback work out
of the box.

## Notes

- **Reset demo** (top-right) restores the seed data at any time.
- Seed due dates are relative to *today*, so the app always looks live.
- To connect a real backend, replace `src/data.ts` (seed) and the `actions` in
  `src/store.ts` with API calls — the views don't need to change.
