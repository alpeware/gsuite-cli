---
name: gsuite
description: >-
  Interact with Google Workspace and consumer Gmail accounts using gsuite-cli.
  Use to search and read emails, inspect threads, draft and send messages, check
  calendar agendas and schedules, query free/busy slots, and read or export Drive,
  Docs, and Sheets across single accounts, labels (e.g. --label work), or --all.
---

# Google Workspace & Gmail Skill (gsuite-cli)

This skill enables Antigravity agents to interact with Google Workspace and Gmail
accounts via the `gsuite` command-line tool.

---

## 1. Guiding Principles for Agents

1. **Always Use `--json`:** When executing read commands (`search`, `read`, `threads`, `agenda`, `events`, `freebusy`, `sheets read`), append `--json` to obtain structured, parseable JSON data on `stdout`.
2. **Account Targeting Discipline:**
   - Use `--account <email|alias>` if the user specifies an explicit email or account context (e.g. "on my personal account" -> `--account personal`).
   - Use `--label <label>` (e.g. `--label work`, `--label personal`, `--label foundation`) when operating across an organization or functional group of accounts.
   - Use `--all` only when searching broadly across all configured accounts.
   - Omit flags to fall back to the user's configured `default_account`.
3. **Safety on Write Operations:**
   - Never send an email (`gsuite gmail send`) or delete/modify events without explicit confirmation or user approval.
   - Prefer creating a draft with `gsuite gmail draft create` so the user can review before dispatching.
   - Use `--dry-run` to preview actions whenever available.

---

## 2. Command Recipes

### Account & Configuration
```bash
# List configured accounts, aliases, labels, and token health
gsuite auth list --json

# Test token validity across all accounts
gsuite auth test --all --json
```

### Gmail Workflows
```bash
# Search unread messages across all work accounts
gsuite gmail search "is:unread" --label work --limit 10 --json

# Search emails from a specific sender
gsuite gmail search "from:stripe.com after:2026/10/01" --json

# Read an email by message ID and decode MIME body as markdown
gsuite gmail read <message_id> --format markdown --json

# Inspect an entire thread
gsuite gmail threads <thread_id> --json

# Create a draft email (recommended over direct send)
gsuite gmail draft create \
  --account <account_or_alias> \
  --to "client@example.com" \
  --subject "Project Specs Review" \
  --body "Hello, here is the updated plan..."

# Send an email with --confirm (after user confirms)
gsuite gmail send \
  --account <account_or_alias> \
  --to "client@example.com" \
  --subject "Project Specs Review" \
  --body "Hello, here is the updated plan..." \
  --confirm

# Mark an email as read and archive it
gsuite gmail modify <message_id> --mark-read --archive --json
```

### Calendar Workflows
```bash
# Check today's agenda across all accounts
gsuite calendar agenda --today --all --json

# View upcoming events for next 3 days
gsuite calendar agenda --days 3 --json

# Query free/busy blocks across attendees before proposing a meeting time
gsuite calendar freebusy \
  --emails "alice@example.com,bob@example.com" \
  --start "2026-10-12T09:00:00Z" \
  --end "2026-10-12T17:00:00Z" \
  --json

# Schedule a new calendar event
gsuite calendar create \
  --account <account_or_alias> \
  --summary "Sprint Review" \
  --start "2026-10-12T14:00:00-05:00" \
  --end "2026-10-12T15:00:00-05:00" \
  --attendees "dev@example.com" \
  --description "Reviewing Q4 deliverables."
```

### Drive, Docs & Sheets Workflows
```bash
# Search Drive files by name
gsuite drive search "Quarterly Planning" --limit 5 --json

# Read a Google Doc directly as clean Markdown
gsuite docs read <file_id> --markdown --json

# Read a spreadsheet range as JSON
gsuite sheets read <spreadsheet_id> --range "Sheet1!A1:D20" --json

# Append a row of data to a spreadsheet
gsuite sheets append <spreadsheet_id> \
  --range "Sheet1!A1" \
  --values '[["2026-10-11T12:00:00Z", "task_completed", "agent_run"]]' \
  --json
```

### Tasks Workflows
```bash
# List all task lists
gsuite tasks lists --json

# List pending tasks in default list
gsuite tasks list --json

# Add a new task with due date
gsuite tasks add "Review budget proposal" --due "2026-10-15T00:00:00Z" --json

# Mark task complete
gsuite tasks done <task_id> --json
```

### Slides Workflows
```bash
# Inspect presentation metadata and slides
gsuite slides info <presentation_id> --json

# Read all slide content and speaker notes
gsuite slides read <presentation_id> --json

# Create a new presentation
gsuite slides create "Q4 Strategy Pitch" --json
```

