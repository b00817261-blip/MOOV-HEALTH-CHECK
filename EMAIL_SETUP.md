# Emailing sign-in codes

By default the app **shows the sign-in code on screen** (and prints it to the
log). That's handy for a demo, but to email codes to people instead, give the
app an SMTP provider through five environment variables. No code changes and no
extra dependencies — it uses Python's built-in `smtplib`.

Set these in your host's environment (on Render: your service → **Environment**
→ Add environment variable), then redeploy:

| Variable | What it is | Example |
|---|---|---|
| `MOOV_SMTP_HOST` | SMTP server hostname (**required** — its presence turns email on) | `smtp.resend.com` |
| `MOOV_SMTP_PORT` | Port. `465` = implicit SSL, anything else = STARTTLS | `587` |
| `MOOV_SMTP_USER` | SMTP username | `resend` |
| `MOOV_SMTP_PASS` | SMTP password / API key | *your key* |
| `MOOV_SMTP_FROM` | The "from" address | `onboarding@resend.dev` |
| `MOOV_SMTP_FROM_NAME` | Friendly from-name (optional) | `MOOV` |

When it's on, the server prints `Email: on — codes sent via <host>` at startup,
and the "here's your code" banner disappears (people get the code by email).

## Provider recipes (all have free tiers)

**Resend** (easiest — https://resend.com):
```
MOOV_SMTP_HOST=smtp.resend.com
MOOV_SMTP_PORT=587
MOOV_SMTP_USER=resend
MOOV_SMTP_PASS=re_xxxxxxxxxxxxxxxxxxxx      # your Resend API key
MOOV_SMTP_FROM=onboarding@resend.dev        # or your verified domain
MOOV_SMTP_FROM_NAME=MOOV
```

**SendGrid** (https://sendgrid.com):
```
MOOV_SMTP_HOST=smtp.sendgrid.net
MOOV_SMTP_PORT=587
MOOV_SMTP_USER=apikey                       # literally the word "apikey"
MOOV_SMTP_PASS=SG.xxxxxxxx                   # your SendGrid API key
MOOV_SMTP_FROM=you@yourdomain.com           # a verified sender
MOOV_SMTP_FROM_NAME=MOOV
```

**Gmail** (needs a Google account with 2FA + an *App Password*):
```
MOOV_SMTP_HOST=smtp.gmail.com
MOOV_SMTP_PORT=587
MOOV_SMTP_USER=you@gmail.com
MOOV_SMTP_PASS=xxxxxxxxxxxxxxxx              # 16-char App Password, not your login
MOOV_SMTP_FROM=you@gmail.com
MOOV_SMTP_FROM_NAME=MOOV
```

## Notes
- If a send fails, the app logs the error and falls back to showing the code, so
  sign-in never breaks.
- Deliverability is best when `MOOV_SMTP_FROM` is on a domain you've verified with
  the provider; the provider's sandbox address (e.g. Resend's `onboarding@resend.dev`)
  works for testing.
- The code is a **permanent** sign-in code, so the email is mostly a convenient
  record — people reuse the same code every time.
