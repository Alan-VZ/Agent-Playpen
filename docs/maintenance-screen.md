# Maintenance screen

Open **Maintenance: connect accounts & manage keys** from the dashboard, or visit
`http://127.0.0.1:8765/maintenance` after starting the local server. It combines
provider portals, onboarding steps, encrypted saving, access checks, review
dates, and a small maintenance history.

## Automation and human steps

| Operation | Support |
| --- | --- |
| Open the correct portal | All configured model/search services |
| Connect OpenRouter | Official browser authorization with S256 PKCE; the app exchanges the code and saves the key |
| Register, verify email, MFA, CAPTCHA, billing approval | Completed by you on the provider's website |
| Create other providers' keys | Guided portal workflow; paste the created key into Maintenance |
| Save the correct credential | Native encrypted OS entry under the provider's existing key name |
| Check account/usage without a search | OpenRouter, Tavily, Firecrawl |
| Search smoke test | Other search providers, after opt-in to possible credit use |
| Check other model-backend inference | Use the Agent workspace; Maintenance issues no model completions |
| Record reviews | Manual checklist, distinct from API access checks |

The screen uses an integrated authorization flow where supported and makes
human steps explicit elsewhere. It does not store portal passwords, automate
identity verification, purchase plans, enter payment details, or silently issue
billable tests. It needs neither provider administrative keys nor generic
browser-control automation.

## Connect OpenRouter

1. Choose OpenRouter in Maintenance. If a key is already saved, select the
   replacement checkbox to permit updating it. The old remote key is not revoked.
2. Click **Connect OpenRouter securely**. If the popup is blocked, use the
   **Continue OpenRouter sign-in** link.
3. Complete portal sign-in/MFA; review the account, workspace, and key limit
   before approving.
4. The provider returns to the local app. The server exchanges the authorization
   code and saves the key directly to the OS vault. The actual key is not
   returned to browser JavaScript or displayed in the page.
5. Return to Maintenance and click **Check account / usage access**. The
   workspace can use the saved key without copying it to another file.

Connections are browser-bound, single-use, and expire in ten minutes. Restarting
the app invalidates pending connections. A key changed during sign-in is not
silently overwritten. If exchange/storage fails after authorization, inspect
the portal: a newly authorized remote key may exist and need revocation.

Use the same local address throughout. If a numeric loopback callback is
rejected, open `http://localhost:8765/maintenance` and start a fresh connection.
The callback must reach the running local app.

This follows [OpenRouter's PKCE flow](https://openrouter.ai/docs/guides/overview/auth/oauth),
with S256 and state. Callback query strings are removed from Uvicorn access
records and cleared from the browser URL before exchange. Other hosting/logging
configurations must also exclude authorization codes; this app is intended for
local loopback use.

## Other provider setup

1. Choose the provider and open its portal.
2. Sign in/register, complete verification, and choose the intended workspace.
3. Review the plan, spending limits, and auto-renewal settings. See the
   [cost guide](keys-costs-maintenance.md) before purchasing.
4. Create an application key, paste it in Maintenance, and press **Save encrypted
   key**. The destination name is displayed; the field clears after an attempt.
5. Google legacy accounts also need a separately saved CSE ID.
6. Run the available account check or opt into one search smoke test.
7. Mark the steps you completed and save a review date. These flags are
   self-reported, not inferred from a key.

Serper and SerpAPI use separate accounts/keys. OpenWeb Ninja needs a direct key,
not RapidAPI. Model and search credentials remain separate.

## What verification means

- **Encrypted OS vault**: the key is saved locally; remote access is not implied.
- **Verified**: the selected authenticated endpoint or opted-in search request
  completed. It does not prove email/identity verification, every project
  permission, available funds, model inference, or source quality.
- **Manual**: no non-billable check is configured. **Missing**: no key resolved.
  **Failed**: the attempted check failed; review key, quota, and account access.

Account checks use [OpenRouter key information](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key),
[Tavily usage](https://docs.tavily.com/documentation/api-reference/endpoint/usage),
and [Firecrawl credit usage](https://docs.firecrawl.dev/api-reference/endpoint/credit-usage).
Only approved finite numeric fields are returned. Labels, key hashes, emails,
account IDs, and raw responses are omitted. Fixed HTTPS destinations and disabled
redirects protect credentials. Search tests request one result with no automatic
retry; billable units still depend on the provider.

Saving/clearing a credential removes its previous recorded access result. After
CLI/external changes, check again: a dated result is not continuous monitoring.
There are no automatic background account checks or billing changes.

## Storage and maintenance history

Keys use Windows Credential Locker, macOS Keychain, or Linux Secret Service
under **Agent Playpen** and the provider's credential name. Keys are not put in
a project file with a nearby decryption key. Existing adapters resolve the vault
entries directly. See [credential protections](credentials-and-openrouter.md).

`traces/maintenance.json` stores approved provider/action/status codes,
timestamps, review dates, and checklist flags, retaining the last 100 events.
It contains no keys, passwords, authorization codes, PKCE verifiers, or raw API
responses. Extra/malformed metadata fields are not exported. The runtime traces
directory is excluded from Git and packages. Deleting traces removes this
ordinary, non-secret history.

Maintenance shares the dashboard's session-token, host/origin, no-cache, and
redaction protections. Native storage must be readable before connecting
OpenRouter; save failures never create a plaintext fallback.

Clearing a local key does not cancel billing or revoke remote credentials.
Complete those actions in the provider portal when retiring a service.

## Tests

Tests use fake credentials and mocked HTTP/authorization responses. Coverage
includes key routing, PKCE replay/expiry/browser binding, explicit replacement,
vault failure, filtered usage, billable-test consent, callback log/URL handling,
and review metadata. They do not sign into live accounts or validate a real
provider portal's current availability.

Optional production-template DOM checks use the jsdom setup in
[testing](testing.md):

```powershell
python tests/render_maintenance_ui.py
node tests/maintenance_ui.cjs
```
