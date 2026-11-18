# Four local model baseline observations — November 18

Saved run: `e40dbdbca42544399d6aa0057b1cc1c4`. Source: the original experiment and attempt JSON in benchmark-results, corroborated by the user-supplied results page. B01 only, seed 1, one attempt per model; separate single-agent configurations. All use LM Studio, auto tool calling, temperature 0, 10 iterations, 2048 output tokens and 330 seconds. Original results and scoring are unchanged.

| Model | Elapsed seconds | Outcome | Evidence |
|---|---:|---|---|
| gemma-4-e4b-it-abliterated-uncensored-philadelphia-class-i1 |169.955|Invalid JSON, score 0|Read fixture successfully. Second response finish_reason=length at 2048 output tokens (1698 reported reasoning tokens). Returned prose saying JSON was ready, not JSON; prose also adds the refund in parts, giving 42 instead of 32.|
| neuraldaredevil-8b-abliterated@q8_0 |74.320|Valid JSON, score 87.5, strict fail|Correct net total 44, count 3, duplicate A and service 12. Parts subtotal 37 instead of 32; omitted the parts refund. Fixture read succeeded; no calculator call.|
| qwen2.5-coder-7b-instruct |46.188|Iteration budget exhausted, score 0|Calculator returned 44 for (37+12)-5. Seven fixture reads, one calculator call, two rejected action-format responses; no final JSON within ten iterations.|
| gemma-2-9b-it-abliterated |340.088|Timeout, score 0|330-second budget plus worker supervision allowance. Two fixture calls succeeded. Two calculator calls attempted SQL-like sums/case expressions unsupported by the arithmetic calculator. Two action-format rejections; waiting for response at step 7 when stopped.|

Expected B01 report: net_total 44, valid_orders 3, duplicate_ids [A], category_totals parts 32 and service 12. Deduplicate A, exclude cancelled D, subtract refund B (5) from its parts category as well as the grand total.

These are distinct failures, not evidence that every model failed to connect or every tool failed. Increasing timeout alone does not address the other three observed failures. Raising the iteration budget without loop handling may repeat Qwen's reads. More output allowance may let Gemma 4 finish but cannot guarantee correct category arithmetic. A 600-second diagnostic budget can distinguish slow completion for Gemma 2, but does not correct unsupported calculator syntax.

Application limitation: a nonempty native-route response without a tool call is normalized as a final answer even when provider metadata says finish_reason=length. Thus execution can say completed while the baseline correctly fails JSON validation. This run does not prove the final-answer handling is adequate; explicit truncation reporting/recovery and clearer schema/calculator guidance merit controlled follow-up. No adapter, prompt, rubric, model settings or historical answers were changed while reviewing this run.

Next measured work should distinguish instruction/format adherence, loop recovery and arithmetic formulation from correct calculator execution. Use numeric expressions supported by the advertised calculator, and verify refunds per category. Structured final-output validation can enforce shape; it cannot make the wrong parts subtotal correct. Repeated matched cases are needed before claiming a provider-wide failure rate or improved reliability.
