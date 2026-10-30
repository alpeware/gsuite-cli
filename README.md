# gsuite-cli

A fast, lightweight CLI and Google Antigravity (`agy`) progressive disclosure skill for Google Workspace and consumer Gmail accounts.

---

## Highlights

* **No MCP Context Bloat:** Uses progressive disclosure via `.agents/skills/gsuite/SKILL.md` (~80 tokens indexed) instead of injecting monolithic MCP server schemas (~4,000+ tokens) on every conversation turn.
* **Unified Multi-Account Support:** Seamlessly orchestrates consumer accounts (`@gmail.com`) and Google Workspace domains without requiring Domain-Wide Delegation.
* **Flexible Targeting with Labels:** Target single accounts (`--account`), label groups (`--label work`, `--label personal`), or fan out across all accounts (`--all`).
* **Headless & Cluster-Ready:** Supports both local browser loopback authentication and headless out-of-band authorization code flows for remote SSH sessions and Android (Termux).
* **Dual Output Modes:** Beautiful terminal tables and syntax-highlighted Markdown for humans, deterministic JSON envelopes (`--json`) for AI agents.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/alpeware/gsuite-cli.git
cd gsuite-cli

# Create and activate virtual environment with uv
uv venv
source .venv/bin/activate

# Install in editable mode
uv pip install -e ".[dev]"
```

---

## Configuration & Authentication

### 1. Interactive OAuth 2.0 (Consumer Gmail & Workspace)

1. Place your Google Cloud OAuth 2.0 Desktop Application credentials at `~/.config/gsuite/client_secret.json`.
2. Add your Google accounts:
   ```bash
   # Desktop / GUI environment
   gsuite auth add user@gmail.com --alias personal --labels personal,primary

   # Headless / SSH / Termux environment
   gsuite auth add work@mycompany.com --alias work --labels work,company --headless
   ```
3. Test connectivity across all configured accounts:
   ```bash
   gsuite auth test --all
   ```

### 2. Service Accounts & Domain-Wide Delegation (Google Workspace)

For headless server nodes, background automations, CI/CD, or managing multiple users across an organization, `gsuite-cli` supports Google Cloud Service Accounts with Domain-Wide Delegation (DWD).

#### Step A: Inspect Service Account Client ID & OAuth Scopes
Inspect your service account JSON key file to extract its unique `Client ID` and required comma-separated scopes:
```bash
gsuite auth dwd-info --key-file /path/to/sa-key.json --scopes standard
```

#### Step B: Authorize in Google Workspace Admin Console
1. Open the [Google Workspace Admin Console](https://admin.google.com).
2. Navigate to **Security > Access and data control > API controls > Domain-wide Delegation**.
3. Click **Add new**.
4. In **Client ID**, enter the `client_id` from Step A.
5. In **OAuth scopes (comma-separated)**, paste the `scopes_csv` from Step A.
6. Click **Authorize**.

#### Step C: Register Delegated Accounts or Wildcard Domains

* **1:1 Delegated Account Registration:**
  Register a specific Workspace user email impersonated via the service account:
  ```bash
  gsuite auth add work@mycompany.com --service-account /path/to/sa-key.json --alias work --labels work
  ```

* **Wildcard Workspace Domain Registration (Recommended for Teams):**
  Register your entire hosted Google Workspace domain once. Any `<user>@mycompany.com` can then be dynamically targeted on the fly via `--account` without registering users individually:
  ```bash
  # Register the wildcard domain
  gsuite auth domain add mycompany.com --service-account /path/to/sa-key.json --scopes standard --tags work

  # Target any domain user dynamically
  gsuite calendar agenda --account alice@mycompany.com --json
  gsuite gmail search "is:unread" --account bob@mycompany.com --json

  # Inspect or manage registered wildcard domains
  gsuite auth domain list --json
  gsuite auth domain info mycompany.com --json
  gsuite auth domain remove mycompany.com --json
  ```

* **Direct Service Account Mode (No Impersonation):**
  Authenticate directly as the raw service account principal for resources shared directly with the service account email (e.g. shared Google Drive folders or calendars):
  ```bash
  gsuite auth add bot@project.iam.gserviceaccount.com --service-account /path/to/sa-key.json --no-impersonate
  ```

---

## Command Reference

### Gmail
* `gsuite gmail search "is:unread" --label work --limit 10`
* `gsuite gmail read <message_id> --format markdown`
* `gsuite gmail draft create --to user@example.com --subject "Hello" --body "Message..."`
* `gsuite gmail send --to user@example.com --subject "Hello" --body "Message..." --confirm`

### Calendar
* `gsuite calendar agenda --today --all`
* `gsuite calendar events --days 7 --query "Planning"`
* `gsuite calendar freebusy --emails "alice@example.com" --start 2026-10-12T09:00:00Z --end 2026-10-12T17:00:00Z`
* `gsuite calendar create --summary "Sync" --start "2026-10-12T15:00:00-05:00" --end "2026-10-12T15:30:00-05:00"`

### Drive, Docs & Sheets
* `gsuite drive search "Annual Report" --limit 5`
* `gsuite docs read <doc_id> --markdown`
* `gsuite sheets read <sheet_id> --range "Q3!A1:D20" --json`
* `gsuite sheets append <sheet_id> --range "Sheet1!A1" --values '["2026-10-11", "test"]'`

---

## License

MIT © Alpeware
