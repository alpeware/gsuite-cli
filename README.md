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
