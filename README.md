# Intake Triage Assistant

A desktop tool for small organizations that handle incoming requests
(volunteer inquiries, service requests, general questions) and need
help drafting a first response without losing a human in the decision.

## What it does

1. Staff pastes or types an incoming request into the app.
2. Claude drafts a suggested category and a short response.
3. Staff reviews both in editable fields. Nothing is final yet.
4. Only clicking **Approve & Save** writes a record. The AI's original
   suggestion and the human's final, possibly edited, version are both
   kept, so there's a record of where the AI was right, where it got
   edited, and where it was overridden entirely.

The core design rule: the AI drafts, a person decides. The tool never
sends or finalizes anything on its own.

## Why it's built this way

- **Separate, append-only audit log.** The `audit_log` table is never
  updated or deleted from, only inserted into. If a request record is
  later changed, the audit trail still shows exactly who approved what
  and when, independent of the record itself.
- **Multi-user with roles.** Staff can triage requests; only admins see
  the audit log tab. Real organizations have more than one person
  touching this, and not everyone should see everything.
- **Categories live in a config file, not hardcoded.** Every
  organization's intake categories are different. Deploying this for a
  new org means editing `categories.json`, not editing Python.
- **The AI step fails gracefully.** If the Claude API call fails or
  returns something unusable, the app shows an error and lets staff
  fill in the category and response by hand. A tool that blocks
  someone's work when an API call fails is worse than no AI at all.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env     # then add your real ANTHROPIC_API_KEY to .env
python setup.py          # creates the database and first admin account
python main.py
```

## Honest gaps before this could be used by a real organization

This is a portfolio-stage project, not a production deployment. Specific
gaps, in rough order of what would need solving first:

- **No real deployment story yet.** Packaging as a standalone `.exe`
  or `.app` (via PyInstaller) so non-technical staff can double-click
  it, rather than running it from a terminal, is the first real gap.
- **SQLite is single-file, single-machine.** Fine for one computer at
  one intake desk. Multiple simultaneous users on different machines
  would need a real database server, not SQLite.
- **No password reset flow.** Right now, a lost password means an
  admin manually re-running account creation. A real deployment needs
  at least a basic reset mechanism.
- **API cost is a real constraint.** Every AI suggestion is a paid API
  call. A real org would need to know their request volume before this
  makes financial sense over manual triage.
- **No data retention or deletion policy.** The app doesn't currently
  have a way to purge old requests or honor a deletion request from
  someone whose information is in the database. That has to exist
  before this touches real people's real requests.
- **Password hashing uses salted SHA-256, not bcrypt/argon2.** Adequate
  for a local single-org tool, not what a production system handling
  real sensitive data should use long-term.

## License

MIT, see LICENSE.
