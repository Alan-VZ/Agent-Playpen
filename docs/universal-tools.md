# Universal tool gateway and MCP integration

Implemented 2026-11-17. The common execution core belongs to [Universal Agent Control Plane](https://github.com/Alan-VZ/universal-agent-control-plane); Agent Playpen supplies tool implementations, model adapters, the UI and evaluations. The calculator is one tool in this system.

## Architecture and contract

Every selected Playpen tool now goes through UACP ToolGateway, including fixture tools used by baseline agents. The host advertises individual typed tool schemas. The gateway validates the JSON object, required fields, types, enums, bounds and unknown fields before executing. It records queued/running/final status, execution ID, gateway/tool version, redacted arguments, complete bounded output, errors, duration and an output checksum. External schema references are rejected, preventing validator-driven network requests. Output schemas are enforced when a tool supplies one; legacy adapters retain their varied output types inside the common envelope.

The same gateway serves existing tools in-process and over MCP. MCP standardizes discovery/calls/results; it does not make model decisions deterministic. Playpen normalizes native OpenAI-compatible tool calls into one action contract; other backends retain the prompt adapter. Provider rejection is reported rather than silently repeated through another route. OpenAI-compatible auto mode sends real tool schemas, addressing the missing-native-tools mechanism observed with Groq GPT-OSS; success on those historical cases remains to be measured. It accepts one call per step and pairs native assistant tool calls with actual role=tool observations. Native model requests disable SDK automatic retries. It never executes a model-invented observation. Set TOOL_CALLING_MODE=prompt to reproduce the older calling route, auto for native-capable clients, or native to reject unsupported adapters explicitly. The workspace Tool calling dropdown and AgentConfig both select tool_calling_mode.

Agent observations retain the existing length cap for context budgets, while full tool_result trace events and response tool_results preserve verified output separately. The live workspace labels these Verified tool output. A model's final statement remains separately visible; the application does not claim that any free-form answer faithfully reflects a tool merely because execution succeeded.

## Direct console

Open Menu → Universal tools & MCP or http://127.0.0.1:8765/tools. The catalog shows readiness, source and tool contract version. Choose any tool, enter its JSON arguments, and Run tool. You immediately see Running, then the full succeeded/failed/timed_out execution record. An invalid request does not run a handler. Local tools include calculator, scientific_calculator, datetime, web_search, fetch, nimble_extract, read_file and safe text write_file. The direct console confines files to the project root. Agent tools retain the run's Allowed directories setting. File tools continue to block sensitive configuration paths.

Readiness is intentionally local and free: installed/configured is not proof of API access, inference, quota or remaining credits. Scientific readiness checks the executable. Nimble checks saved-key presence. Other network tools report configured_unverified; use Secrets & API inventory for explicit access/operation checks. Scientific calculations require the separate qalc runtime. Search auto can consume configured provider credits; the contract tests use frozen/loopback sources, not paid providers.

The basic calculator now uses Python Decimal at 50 significant digits, parsing decimal literals from their source rather than first rounding them to binary floats. For example, 0.1+0.2 returns 0.3. Integer-valued division is rendered canonically (4/2 returns 2). It remains bounded basic arithmetic, not a substitute for a scientific engine. The benchmark-only BoundedCalculator is unchanged. Use scientific_calculator for high precision, exact fractions, units or scientific calculations. Its JSON strings preserve digits. Graphs are scalar sampled 2D curves; CSV/JSON retain precise samples while SVG coordinates are display-rounded.

## MCP server for other hosts

Install with `python -m pip install -e ".[dashboard,dev]"` from the Playpen root. The shared control-plane dependency is pinned to Git revision `c770b262154c32d7e1d6056f1fe15d1159c9a6de` for reproducibility (Git/network access is needed on first install). Its source can also be installed editable from a sibling checkout for development. Then launch:

```powershell
python -m tools.mcp_server --allowed-dir . --data-dir ./traces/tool-gateway
```

The installed `agent-playpen-tools` command is equivalent. This is a local stdio MCP server, not an HTTP service. It exposes seven tools by default; add --allow-writes to explicitly expose safe text write_file. Use an absolute interpreter and allowed directory in host configuration. No shell or Python-execution tool is exposed by this server. The existing dashboard authentication remains unchanged. UACP's existing guidance/skills server remains a separate entry point; both use the shared package.

Example host configuration (replace paths for your computer):

```json
{"mcpServers":{"playpen-tools":{"command":"C:/path/Agent Playpen/.venv/Scripts/python.exe","args":["-m","tools.mcp_server","--allowed-dir","C:/path/approved-data"],"cwd":"C:/path/Agent Playpen"}}}
```

The MCP result contains structuredContent and a text JSON representation; isError reflects failed execution. Its outputSchema describes the common result envelope. Individual tool input schemas remain discoverable rather than being hidden behind a generic unrestricted execute(payload) call.

## External MCP tools in Playpen

Copy config/mcp_servers.example.json to ignored config/mcp_servers.json. Configure a trusted stdio executable/args/cwd, or a public HTTPS/loopback HTTP MCP URL, and an explicit allowed_tools list. Arbitrary commands, executables or server URLs cannot be submitted through the dashboard API or an LLM request. Command configuration is trusted local administrator input and must not be copied from untrusted tool results.

Click Connect configured MCP servers in the tool console, then reload the workspace. Each allowed tool appears as server__tool. Discovery is explicit and cached for the connection; normal tool calls do not relist catalogs. Connections persist and close on application exit. The CLI can connect declared servers when an explicitly selected namespaced tool is requested. JSON arguments/results use the same gateway as built-in tools. No MCP tool runs solely because a catalog was connected.

secret_env contains credential names, never plaintext values. Stdio children receive selected runtime variables plus only explicitly requested saved credentials. HTTP URL connections currently support public endpoints; authenticated HTTP/OAuth onboarding and disconnect/reconfigure UI are not implemented. Secrets must not be placed in URLs. Changing local server configuration requires restarting the host to replace existing connections. No automatic server installation or package downloading is performed by the gateway itself.

## Limits, replay and records

Input limit 64 KiB; output limit 1 MiB; a handler deadline defaults to 30 seconds (up to 300 seconds by trusted ToolSpec); one concurrent call per tool instance by default and at most 16 active in-process handlers per process. No automatic execution retries are made. Invalid requests can be corrected by the agent within its iteration budget. A repeated invalid/search request is still subject to the existing loop guards.

In-process Python threads cannot be safely killed. A timeout returns timed_out and may_still_be_running; capacity stays reserved until the handler actually exits. Never automatically retry a write after an uncertain timeout. Qalculate separately enforces subprocess termination. MCP remote timeouts likewise do not prove that remote effects stopped. Stronger isolation for arbitrary third-party handlers remains a limitation, not a claimed fix.

Replay is explicit and restricted to ToolSpec.replay_safe. Playpen enables it only for the bounded basic calculator. Writes, live search/fetch, time, mutable files, external tools and graph generation cannot be replayed through the console by default. A replay creates a new execution linked to its original and requires the same contract version and non-redacted arguments. It reruns the operation; it does not serve cached output. Version/source hashes identify adapter contracts; scientific records also carry the actual engine version. Environment, endpoint and external data changes can still affect non-deterministic tools.

Console records persist in PLAYPEN_TOOL_DATA_DIR/tools.sqlite3 (default traces/tool-gateway); memory history is bounded. Agent records persist in their existing redacted trace JSON. These local records can contain user documents/results and should not be published casually. They are ignored by Git. Deleting/archiving old records is currently manual; no retention scheduler is installed.

## Testing and interpretation

Use python -m pytest for the application suite; UACP has its own suite. Set QALCULATE_TEST_BINARY to include real-engine checks. The gateway tests cover validation-before-execution, output contracts, error classification, readiness, timeout capacity, redaction, persistence/replay and official SDK MCP discovery/calls. Provider tests use transport stubs to prove adapter mechanics, not claim new model benchmark results. Controlled fixture and loopback tools avoid paid APIs.

Do not combine historical baseline-v1 scores with new gateway/native-route runs without labeling the runtime/calling mode. B01–B05 fixtures and scorer are unchanged. B02 canonical wording and B05 explanation-number grading remain documented evaluator limitations. This implementation fixes interfaces; it does not retroactively change historical scores or establish universal LLM reliability.

See [all observed issues and dispositions](issues-and-resolutions.md), [scientific calculator](scientific-calculator.md), and [creators and sources](credits-and-sources.md).


## Verified integration snapshot (2026-11-17)

The application suite passed 517 tests with real Qalculate enabled; the shared control-plane suite passed 58 tests including both architecture maps. Ten DOM scripts passed (universal tools, dashboard, calculator, inventory/baselines, task picker, feedback, controlled study, model picker, prices and maintenance). Fresh wheel/source builds and an isolated installation from the pinned Git revision verified in-process/MCP parity without either source checkout on the import path; private runtime configuration was excluded from the wheel.

The running dashboard connected the local UACP guidance server through stdio and exposed registry_validate/resolve/search alongside eight local tools. Live local checks exercised calculator, scientific units, safe file write/read, loopback fetch, datetime(now), invalid-argument rejection, remote registry validation and a checksum-matched replay. No live paid search/extraction request was made.

One real local Qwen3.5-9B native-call smoke attempt reached a 30-second inference timeout before any tool executed. This is an inference-latency observation under that test budget, not a calculator/gateway correctness result or proof of eventual model failure. Model loading was not changed; its loaded state was read once. A single smoke outcome cannot establish model reliability or replace the matched study.

A real Groq Qwen3.8-27B native-call positive control completed the units problem through two actual Qalculate calls and correctly reported 60 km/h. It also made an unnecessary second call, illustrating that planning efficiency remains distinct from interface correctness. See the [smoke observations and synthetic evidence](studies/2026-11-17-universal-tools-smoke.md); these single cases do not establish repeated reliability or resolve the older GPT-OSS case.

The final basic-calculator regression includes exact decimal-literal checks; this changes its source/contract version, so replay refuses records from the older implementation. Historical benchmark-only calculator results remain unchanged.

External MCP structured objects, arrays, booleans and explicit null remain their original JSON types in execution records; legacy text stays text. Validation errors identify missing field names and expected types without echoing rejected values.
