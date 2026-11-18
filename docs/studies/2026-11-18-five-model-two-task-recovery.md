# Five local models, B01/B02, recovery-v1 — November 18

Run `6ec7f70828b648568b85133fdba48faa` completed all 10 scheduled attempts. Recorded commit `4dd3736bbf39031743b64cefb1abbfce6aa429e4`, clean working tree, recovery_policy `report-recovery-v1`, Python 3.13.5. LM Studio, Auto tools, temperature 0, 10 iterations, 2048 output tokens, 400-second task deadline, one repetition/seed 1. Reviewed original experiment and all ten attempt JSON files. No original files or scores were changed; no new generations were launched during review.

Strict pass rate: **0/10**. No recorded completed response had finish_reason=length. This is not another output-truncation result.

| Model | B01 | B02 |
|---|---|---|
| qwen3.5-9b-uncensored-hauhaucs-aggressive@q6_k | Timeout 410.056 s, including supervision allowance. Nine successful tool calls; repeatedly calculated correct totals/subtotals instead of finishing. | Incomplete 271.182 s. Read all three sources, then repeated calculator expression 10 + 0 six times; exhausted iterations. One multiple-native-call rejection. |
| tinyllama-1.1b-chat-v1.0 | Incomplete 19.726 s. No tool calls. Two rejected final reports repeating task instructions rather than JSON. | Incomplete 25.677 s. No tool calls. Rephrased instructions; two invalid final reports. |
| neuraldaredevil-8b-abliterated@q8_0 | Incomplete 214.465 s. One successful fixture read, invalid JSON/action formatting, then three consecutive format rejections. | Incomplete 262.817 s. Read archive and notice but not catalog. Repeated format violations, no final report. |
| mradermacherqwen3-vl-8b-instruct-abliterated-v2.0 | Incomplete 251.704 s. Successful fixture read, then three consecutive action-format rejections. | Completed report 237.751 s; strict fail, 66.67%. Read notice only (plus a cached repeat). Correct opening/closed claims, loan_days null and missing loan citation; catalog never read. |
| qwen2.5-coder-7b-instruct | Incomplete 73.017 s. One actual fixture read, cached repetition and no-execution recovery feedback; repeated malformed actions. | Completed report 28.074 s; strict fail, 66.67%. Read notice only. Claimed loan_days 7 with a fabricated catalog quote; actual fixture says 21 and catalog was never read. |

The two 66.67% reports are partial evidence of task performance, not passes. Execution completed means a report was returned, not that its facts passed grading. The earlier B02 Sunday/Sundays limitation did not decide these two failures: both passed the closed-day check and failed loan evidence/read coverage.

## What this establishes

- The last recovery version was active, not a stale server. Rejected final reports and cached reads appear in its trace.
- TinyLlama was faster to stop than the larger models, but produced neither tool calls nor usable final reports. Smaller did not improve task completion here.
- Qwen3.5's observed responses used native tool_calls; the other models' completed responses used finish_reason=stop and textual actions/finals. Auto advertises tools but does not prove a model generated native calls. No successful executed tool-result record in this run reported an execution error.
- The deterministic tool layer executed recorded calls successfully. Autonomous selection, termination, protocol adherence and evidence coverage remained unreliable.
- Existing fixture-read caching does not guard repeated calculator calls. Current final validation catches JSON shape/required fields and B01 internal totals consistency, but does not require all B02 source reads or validate quotations against observed documents before allowing execution completion. The separate scorer catches those evidence failures.
- Safe parser rejection prevents executing invented/multiple text actions. Nonterminal rejected raw responses are not preserved in these attempt traces, so exact malformed text and possible false-positive parsing cannot be audited from these files alone. Do not assert the models alone are at fault or loosen parsing to execute text blindly.

## Prioritized follow-up

1. Preserve bounded, redacted rejected action responses and actual transport-mode metadata. Audit a single failed interaction before another broad sweep.
2. Revisit conflicting prompt-format/native-tool instructions and duplicated history presentation; validate against captured requests before attributing a specific failure to that design.
3. Add a separate deterministic-operation loop guard for the calculator, without extending caching to writes or live/stateful tools.
4. Add B02 pre-final evidence coverage/quotation checks based on observed sources, with bounded feedback and no expected-answer injection. Keep the original scorer and historical results.
5. Separate capability checks (instruction following, one fixture read, one calculator call, final JSON) from the full autonomous baseline. A guided deterministic workflow should be labeled separately; passing it does not demonstrate autonomous agent competence.
6. Implement the deferred configuration-first scheduling/per-configuration task selections to reduce local model switching; record order and compare common tasks fairly.

Software regression tests passing did not establish live reliability. More timeout/token increases alone are not supported as a solution by these results. No live improvement is claimed.
