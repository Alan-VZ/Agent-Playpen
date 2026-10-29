# Live activity and troubleshooting

The dashboard currently runs one agent per task. The Bayesian multi-agent
coordinator remains a proposed design; the existing multi-agent manager can route
tasks, but this page does not launch a consensus group.

## During a run

The Agent Workspace shows an elapsed timer and a Live activity feed. Expand
entries to inspect connection status, model requests/responses, selected actions,
tool names and arguments, tool observations, and the final answer. Model entries
show concise operational summaries rather than an internal reasoning transcript.
Tool output is rendered as text, so a retrieved page cannot inject HTML or script.

Calls appear before the tool starts, allowing you to see which operation is
waiting. The server sends heartbeat records while a call is pending. Model
responses are reported once returned, not token by token. OpenRouter responses
include available finish-reason/output/reasoning-token metadata without exposing
reasoning text. The page prevents duplicate submissions and retains at most 300
live entries; the saved trace retains the recorded run events. Observation
previews are capped at 2,000 characters.

Run outcomes distinguish a final answer (`success`), an exhausted plan or
iteration budget (`incomplete`), a stop request (`cancelled`), and a failure
(`error`). An incomplete run may display the last tool result, clearly labeled;
that is not a completed answer.

## Errors and stopping

Failed runs save their trace as well as successful runs. The page retains the
activity leading up to the failure and shows a session ID and trace path. Errors
report a redacted category/detail, not a raw traceback or provider response body.
Provider authentication, credit, access, and rate-limit failures have specific
messages. Credentials remain protected by the existing local session boundary
and redaction rules.

Stop Run aborts the browser stream and requests that no further model/tool steps
be scheduled. An operation already executing may still complete and incur its
normal cost. Closing the page has the same scheduling effect. Stop is not a hard
termination or a guarantee that an upstream provider request is cancelled.

After updating source code, stop the old server with Ctrl+C, run
`python -m debugging.dashboard.server` again, then hard-refresh the page. The
server does not hot-reload. A refreshed page is required for its new session token
and streaming interface.

## Research tasks

Search results now include source URLs so the agent can fetch and cite the actual
result. All search providers can still fail, return no results, or encounter a
site that blocks retrieval. The observation feed makes that distinction visible.
An OpenRouter key is not a Google/Tavily/SerpAPI search key. Auto search uses any
separately saved search credentials and otherwise tries DuckDuckGo.

An empty model response occurs before a tool can run. It is reported explicitly.
If the finish reason is `length`, the output allowance was exhausted: some models
count reasoning tokens against that allowance. Consider a higher Max tokens
setting or another model. The app does not silently increase budgets or retry
empty responses. See OpenRouter's
[reasoning-token documentation](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

ReAct accepts fenced JSON action arguments. Non-object action arguments become a
recoverable tool error rather than a Pydantic crash. Only the first action object
is executed if a model puts multiple actions in one response; later steps must
use the real tool observations.

## API

`POST /api/run/stream` accepts the same configuration as `POST /api/run` and
requires `X-Playpen-Token`. It returns newline-delimited JSON with content type
`application/x-ndjson`. A `session` record precedes status/model/action/observation
records; a `complete` record carries the terminal status, result or error, and
trace metadata. Heartbeat records are transport activity, not agent output.
Because headers are sent before execution completes, HTTP 200 on a streaming
response is not proof of success: inspect the terminal record. Invalid requests
are rejected before streaming begins. Interrupted connections can lack a terminal
record and should not be treated as successful.

The original synchronous endpoint remains available. It now saves failed traces,
returns redacted diagnostics, and reports incomplete runs explicitly.
