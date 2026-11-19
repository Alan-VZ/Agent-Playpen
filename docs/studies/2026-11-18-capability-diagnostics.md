# Capability diagnostics and protocol follow-ups — November 18, 2026

All original attempts and scores are preserved. These are focused capability diagnostics, not B01–B05 qualification or repeated reliability estimates. One case per diagnostic/model was run. All tool operations were local; provider quota still applied.

## Matched four-model study

Run `6ddea7641b97487b96e1f4a8214f292f`, commit `6a9eb4cd175f0ab0c017d6a1f84eed73c8cee58d`. Temperature 0, Auto tools, 10 iterations, 2048 maximum output tokens and 400 seconds per case. Configuration-first execution.

| Model | D01 JSON | D02 Read | D03 Calculate | D04 Word equation | D05 Evidence | D06 Recovery | Passed |
|---|---|---|---|---|---|---|---|
| Groq Qwen3.8 27B | QUOTA | QUOTA | PASS | QUOTA | QUOTA | PASS | 2/6 |
| Local Qwen3.5 9B Q6_K | PASS | PASS | repeated_action | PASS | repeated_action | PASS | 4/6 |
| Local Qwen2.5 Coder 7B | PASS | final_report_validation | final_report_validation | final_report_validation | final_report_validation | final_report_validation | 1/6 |
| Local TinyLlama 1.1B | final_report_validation | final_report_validation | final_report_validation | final_report_validation | final_report_validation | final_report_validation | 0/6 |

Matched result: **7/24 passes**; four cases were provider quota rejections, not evidence of model inability. No case timed out. Groq reported a 1000-output-token/minute account limit and rejected several requests under the 2048-token configuration.

## Evidence-led protocol correction

Initial Qwen2.5 responses included complete JSON tool envelopes such as `{"name":"calculator","arguments":{"expression":"7 * 9"}}` in ordinary assistant text. The earlier adapter treated these as final-answer candidates, so tools did not execute. A narrowly scoped Auto-mode JSON-call adapter now recognizes exactly one advertised tool envelope and routes it through existing required-argument and gateway validation. It does not extract calls from prose or execute multiple/unknown tools.

Follow-up run `d0a32f54f79b420799b031aa2a031dde`, commit `80db37fe6bbb4f35771e99e833373325f009ff5b`, retained the same six tasks, temperature, limits and model. Results:

| Diagnostic | Before | JSON-call follow-up |
|---|---|---|
| D01 | PASS | PASS |
| D02 | final_report_validation | final_report_validation |
| D03 | final_report_validation | PASS |
| D04 | final_report_validation | final_report_validation |
| D05 | final_report_validation | repeated_action |
| D06 | final_report_validation | PASS |

Qwen2.5 changed from **1/6 to 3/6** in these single-case observations. Calculator dispatch and controlled recovery improved. Source naming/grounding and repeated reads remain problems. This is a separately versioned follow-up, not a retroactive score change or general reliability claim.

## Approved quota-adapted Groq follow-up

Run `60b8246b0c4940728e9fb26723df7465`, commit `3f2c1d212bda4f6f547b33dd7c6043eb8764d3db`. Same Groq model and diagnostics, temperature 0, Auto, 10 iterations, 400 seconds, but **512 output tokens and 60-second pacing between requests and cases**. Results:

| Diagnostic | Result | Case seconds, including in-case pacing |
|---|---|---|
| D01 | PASS | 4.79 |
| D02 | PASS | 121.113 |
| D03 | PASS | 61.274 |
| D04 | PASS | 121.185 |
| D05 | PASS | 241.664 |
| D06 | PASS | 121.592 |

Groq quota-adapted result: **6/6**. This is not numerically matched to the 2048-token study. Do not compare its paced case times directly with unpaced local cases. Provider latency can be measured separately from recorded request/response timestamps.

## What the artifacts establish

- Actual HTTP request bodies confirm the intended model, temperature and maximum tokens. Authentication headers were not recorded; known credentials are redacted. No wire body in these saved cases exceeded the recording cap.
- Native assistant/tool histories show actual observations delivered with their call IDs. Qwen3.5 D04 received the invoice and calculator result 37, then returned the correct report.
- Qwen3.5 can complete several tool workflows but still loops in others. In D03 it obtained 63, then sent a JSON result object as a calculator expression; in D05 it repeatedly reread both sources despite having them.
- TinyLlama produced unrelated explanations/code instead of the requested reports and made no useful tool progress in this study. Its shorter failure time is not successful task completion.
- Fixture caching, repeat guards and report validation bound failures without fabricating an answer. No timeout occurred in the matched study; this does not mean all models became reliable.
- Configuration grouping reduced repeated preparation: Qwen3.5 first-case preparation was about 82.4 seconds; subsequent case preparation was about 2.5–3.0 seconds. These timings support keeping local-model cases grouped.
- Each attempt retains raw bounded/redacted transport bodies, normalized/parsed actions, tool records, rejected candidates, usage and stop reasons. Current-version offline replay is parser/normalizer-only and never executes tools.
- Recorded API messages do not expose LM Studio’s final rendered chat template or prove which model weights/server templates caused a behavior. Those remain separate layers to investigate if required.

## Boundaries and next work

B01–B05, expected answers, rubric and historical runs were not changed or rerun here. No broad baseline improvement is claimed. The next useful work is controlled handling of exact source identifiers and reliable finalization after observations, followed by matched baseline reruns. Qualification still requires repeated cases rather than this one-case diagnostic ladder.

Implementation checks: 548 Python tests passed, 9 skipped; browser checks covered model configuration, task subsets, launch/progress/results, diagnostics evidence/replay, and price sorting remained separately verified.

See [workflow and limits](../diagnostics.md) and [machine-readable cases/replay](2026-11-18-capability-diagnostics.json). Full original local records remain in diagnostic-results/<run-id>/.

## Serial native-call request probe

Groq D05 in the paced run passed after two rejections of multiple native calls. Its first response requested both archive and notice, while Playpen's loop only accepts one action. The request omitted parallel_tool_calls, whose [documented Groq default is true](https://console.groq.com/docs/api-reference). This is a request-policy mismatch, not malformed provider JSON. Groq native requests now explicitly send false.

Probe `23b5d7dd1c1f4d0e83f3a52edb7c2a18`, commit `d07cc2a`, copied the recorded first D05 request and changed **only parallel_tool_calls to false**. It retained temperature 0, 512 output tokens and a 60-second cooldown. The response contained **one native call**, compared with **two** in the reference. No tools were dispatched. This verifies the first-turn constraint in one live request; it is not a complete D05 retest or a provider-wide guarantee. Raw evidence is in the local probe.json, and the machine-readable report includes the audited counts.

Probe provenance reported a dirty tree because the new analysis MD/JSON reports were untracked during its cooldown. A subsequent git diff verified that tracked backend/benchmark/core/planner runtime code matched the recorded d07cc2a commit. The three diagnostic studies were recorded separately with their original provenance and results.

For Qwen2.5 D03 and D06, the first outgoing request and first model text were byte-for-byte identical in the original and protocol follow-up. The different initial dispatch is directly attributable to the JSON-call adapter: the old path accepted the text as a final-report candidate; the new path performed validated tool execution. Later behavior still depends on the model and observations.

A fixture-name enum is now advertised by baseline fixture tools and targeted wrong-name tests cover executable denial. This is a baseline contract improvement, not retroactive evidence that historical model failures came only from that interface. A bare-provider JSON control would also help separate TinyLlama's model/template behavior from the production Agent prompt. Neither explanation is established as the sole cause by this study.
