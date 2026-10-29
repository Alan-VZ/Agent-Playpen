# OpenRouter and encrypted credentials

For key counts, signup URLs, upfront/recurring costs, and the account maintenance
checklist, see [Keys, costs, and maintenance](keys-costs-maintenance.md). A typical
OpenRouter plus one search-service setup needs two keys total.

## OpenRouter setup

OpenRouter is available in the dashboard and through `BackendFactory` as
`openrouter`. It uses `https://openrouter.ai/api/v1` and provider/model IDs from
the OpenRouter catalog. The workspaces/files page is a browser interface, not
the chat API endpoint; this change does not upload or manage workspace files.

1. Start the local dashboard and select **openrouter**.
2. In **Credential manager**, select `OPENROUTER_API_KEY` (or use the selected
   backend default), enter the key in the password field, and press **Save**.
3. The field clears after saving. The status reports whether an encrypted key
   exists, without returning the key or its prefix/suffix.
4. Press **Load** to retrieve the model catalog, or type a model ID. The public
   OpenRouter model catalog does not require sending your saved key.
5. Enter a task and run it. Save credentials separately from general settings.

The cloud endpoint is fixed so a form value or environment override cannot send
the OpenRouter key to an arbitrary host. OpenAI and Anthropic likewise use fixed
official endpoints; Azure endpoints must be HTTPS under `*.openai.azure.com`.
Cloud SDK and model-discovery clients do not follow redirects with credentials.
Local LM Studio/Ollama addresses remain configurable and receive no cloud keys.

CLI setup uses a hidden prompt; never put a secret in a command argument:

```bash
python -m config.credentials set OPENROUTER_API_KEY
python -m config.credentials status OPENROUTER_API_KEY
python -m core.runner --backend openrouter --model openai/gpt-4o-mini --task "Explain a binary search" --tools calculator
python -m config.credentials delete OPENROUTER_API_KEY
```

The model above is an example, not a guarantee of availability. Use the live
catalog and your account's permissions. See the official
[OpenRouter quickstart](https://openrouter.ai/docs/quickstart) and
[authentication guide](https://openrouter.ai/docs/api-reference/authentication).

## Providers and storage

All cloud backends and search credentials share the same manager:

| Provider | Credential name |
| --- | --- |
| OpenRouter | `OPENROUTER_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Azure OpenAI | `AZURE_OPENAI_KEY` |
| Groq | `GROQ_API_KEY` |
| Together AI | `TOGETHER_API_KEY` |
| Tavily | `TAVILY_API_KEY` |
| SerpAPI | `SERPAPI_API_KEY` |
| Serper | `SERPER_API_KEY` |
| Brave Search API | `BRAVE_API_KEY` |
| Exa | `EXA_API_KEY` |
| Firecrawl Search | `FIRECRAWL_API_KEY` |
| OpenWeb Ninja (direct API) | `OPENWEBNINJA_API_KEY` |
| Google search | `GOOGLE_API_KEY`, plus `GOOGLE_CSE_ID` |
| DDGS / Crossref | No API key required; Crossref supplies scholarly metadata |
| LM Studio / Ollama | No API key required by these local adapters |

Select an explicit credential name to manage search keys independently of the
chosen model backend, or choose a search provider and click **Set search API key**.
See [search provider setup](search-providers.md) for account distinctions and
automatic fallback costs. The Google CSE ID has its own Save/Clear controls. The CLI
accepts the same names. There is no application command or endpoint to export
or reveal saved values.

New saves use the `Agent Playpen` service in the operating system's native
credential store: Windows Credential Locker, macOS Keychain, or Linux Secret
Service. The implementation explicitly selects these backends and never falls
back to an unencrypted keyring file. If the native store is missing or locked,
an encrypted save fails with a safe error. On Linux a running, unlocked Secret
Service is required; headless sessions may not provide one. Verify availability
before relying on persistent saves.

Windows credentials are protected by the signed-in user's OS credential service,
outside the project and its OneDrive/Git exports. See
[keyring's native backend documentation](https://keyring.readthedocs.io/en/latest/)
and Microsoft's explanation of
[user-bound Windows data protection](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata).
The application does not keep an encryption master key beside a ciphertext file.

## Existing plaintext keys

Existing environment variables and project `.env` keys remain a legacy input
for compatibility. They are not encrypted. Encrypted storage takes precedence;
an explicit library constructor argument takes precedence over both.

Use **Migrate Legacy Keys** in the dashboard to copy recognized nonempty `.env`
credentials into native storage, verify each new save, and then remove their
entries from `.env`. An already-encrypted value is retained rather than replaced
with an older file value. Duplicate assignments are removed. If a credential
store operation fails, file entries remain available for recovery; some earlier
native saves may already have succeeded, and migration can be retried.

Saving a replacement key or clearing a key in the dashboard also removes its
legacy file entry and current process environment value. The CLI delete command
only deletes the native credential: separately remove legacy file/environment
copies to prevent fallback. The application does not remove parent-shell values,
OS-wide environment settings, backups, OneDrive version history, or old Git
commits. Rotate any key that was previously exposed. Migration does not create a
plaintext backup.

## Application protections and limits

- Credentials are not inserted into new `.env` saves, general JSON exports,
  model-discovery URLs, prompts, or child-process environment variables.
- General configuration saves use an allowlist and omit task text and credential
  fields. Known credential values accidentally echoed in configuration, agent
  results, or traces are redacted. This is defense in depth, not a detector for
  every transformed, encoded, or fragmented secret.
- Key status exposes presence and storage state only. API failures omit raw
  exception tracebacks, and request-validation errors omit input values.
- API requests require the local dashboard session token. Host and origin checks
  defend against cross-site requests and DNS rebinding. Responses disable caching
  and framing; the page uses a restrictive content-security policy.
- The launcher and module server bind to `127.0.0.1`. Do not expose this local
  development dashboard through a public reverse proxy. API callers must obtain
  the token from their locally served page and send `X-Playpen-Token`; do not log
  or export it. Tokens change when the server restarts.
- Agent-facing file tools deny credential paths, `.env` files, and private
  configuration directories, even inside allowed folders. Dashboard writes are limited to `.txt`, `.md`,
  `.csv`, and `.json` artifacts to prevent replacing executable application code.
  The trusted CLI writer retains other formats. These path checks are
  not a general filesystem sandbox.
- Unrestricted `python_repl` is unavailable in the credential-enabled dashboard.
  The trusted CLI/library retains it. Other arbitrary-code extensions require the
  same trust; a substring filter or subprocess does not isolate an OS account.

Encryption at rest cannot protect against malware, a compromised application or
browser, an administrator, or arbitrary code running with your own user's access
to the credential store and process memory. This implementation does not create
an OS sandbox, enforce complete network egress isolation, or stop authorized
provider requests from using a key. Stronger isolation requires a separate
restricted worker account/container and a narrowly scoped credential broker.
Use provider-side spend limits and rotate keys as appropriate. No live key is
needed for the automated suite; its keyring is an in-memory test double.
