# Five-task matched LLM study and expansion recommendations

Completed study `6372f9258614472f8f8bf2945a998605`: **1,200 scheduled cases, 801 attempted, 399 quota-skipped**. The 400 scheduled OpenRouter cases produced one daily-quota rejection and 399 skips, with no new model-performance evidence. No paid fallback or model substitution was used.

The same twelve model IDs were retained across two rounds, five fixture seeds, B01–B05 and two arms. Arm A supplied documents directly and scored answer fields only; it could never earn a strict baseline pass. Arm B required actual local tool evidence and used the unchanged baseline-v1 scorer. All agent tools were free local read_fixture, bounded calculator and isolated write_artifact operations.

Temperature was zero, output limit 2,048 tokens, maximum ten ReAct iterations, and shared task deadline 180 seconds with a parent termination grace period. Local cases were grouped by model; cloud tasks/models were interleaved in a fixed rotating order. Matched arm order reversed in round two. Conversations/processes were fresh per case; provider caches were uncontrolled.

## Task results

Attempted includes provider rejections and operational failures. A strict failure can reflect evidence, protocol or formatting requirements as well as a wrong fact. Grading limitations below are essential to interpreting B02 and B05.

| Task | A answer successes / attempted | B strict passes / attempted | A quota-skipped | B quota-skipped |
|---|---:|---:|---:|---:|
| B01 | 23/81 | 19/80 | 39 | 40 |
| B02 | 41/80 | 0/80 | 40 | 40 |
| B03 | 30/80 | 11/80 | 40 | 40 |
| B04 | 54/80 | 16/80 | 40 | 40 |
| B05 | 29/80 | 13/80 | 40 | 40 |

## Model comparison

Each round contains 25 cases per arm per model (five tasks × five seeds). Matched B successes count task/seed pairs that strictly passed in both rounds; repeated failures are not evidence of reliability.

| Provider | Model | A round 1 / round 2 | B round 1 / round 2 | Matched B successes out of 25 |
|---|---|---:|---:|---:|
| groq | openai/gpt-oss-120b | 18 / 18 | 10 / 12 | 7 |
| groq | openai/gpt-oss-20b | 24 / 25 | 0 / 0 | 0 |
| groq | qwen/qwen3.8-27b | 11 / 12 | 17 / 20 | 17 |
| groq | allam-2-7b | 0 / 0 | 0 / 0 | 0 |
| openrouter | nvidia/nemotron-3.5-lightning:free | Unavailable (quota) | Unavailable (quota) | Unavailable (quota) |
| openrouter | nvidia/nemotron-3.5-super-vl:free | Unavailable (quota) | Unavailable (quota) | Unavailable (quota) |
| openrouter | dots-studio/dots-3-note-preview:free | Unavailable (quota) | Unavailable (quota) | Unavailable (quota) |
| openrouter | liquid/lfm-3-1.7b:free | Unavailable (quota) | Unavailable (quota) | Unavailable (quota) |
| lm_studio | llama-2-7b-chat | 0 / 0 | 0 / 0 | 0 |
| lm_studio | qwen2.5-coder-7b-instruct | 14 / 15 | 0 / 0 | 0 |
| lm_studio | dolphin3.0-llama3.1-8b-abliterated@q4_k_m | 10 / 10 | 0 / 0 | 0 |
| lm_studio | gemma-2-9b-it-abliterated | 10 / 10 | 0 / 0 | 0 |

## Findings relevant to mathematics and tools

The selected local models had **0/40 direct B01 successes**, compared with **29/40 direct B02 successes**. This supports testing numeric assistance for these configurations. It does not establish a universal mathematical limit: Groq Qwen passed all ten real-tool B01 cases, and GPT-OSS-20B answered all ten direct B01 cases correctly.

Calculator use was observed in 21 attempted B01 cases, with 58 recorded operations and 48 explicit invalid-argument events. Unknown usage from terminated workers remains separate. Optional calculator use is not randomized, and A/B differ in prompts and workflow, so this study cannot estimate the causal benefit of the calculator.

Local Qwen sent valid expressions, including `(37 + 12) - 5` in `r1-m10-s1-B-B01`, but then failed the final response contract. Thus successful intermediate arithmetic did not guarantee a successful agent run. Other models sent invalid calculator arguments. A numerical baseline must distinguish input interpretation, expression formation, calculation and final-result propagation.

The selected local configurations earned 0 strict real-tool passes across 200 local B cases. Direct answers on some non-math tasks were much stronger. GPT-OSS-20B also repeatedly produced correct direct answers while its B calls were rejected with tool_use_failed. Tool/interface compatibility is therefore a separate measurement target.

Software can improve a model-driven system without modifying model weights: the model interprets the task, while deterministic routines calculate and validate results. [PAL](https://proceedings.mlr.press/v202/gao23f.html) evaluated that division of work using program execution. [Toolformer](https://proceedings.neurips.cc/paper_files/paper/2023/hash/d842425e4bf79ba039352da0f658a906-Abstract-Conference.html) separately studied learning when to call tools, their arguments and result use. These studies motivate a controlled follow-up; they do not prove an improvement for these twelve configurations.

## Repair measurement clarity before enlarging the suite

B02 had 26 valid-JSON cases with correct other answer checks and a semantically equivalent day rejected by the canonical-value check. The scorer accepts Sunday and rejects Sundays. It also requires every supplied source to be read, including the superseded archive, rather than merely requiring every cited source to have been read. The local supplemental CSV separates these conditions.

B05 had 26 otherwise-correct answer cases rejected by a reason-text rule requiring the literal numbers 12 and 10. The prompt asks for an explanation without explicitly requiring both numbers. For example, local Qwen correctly chose B and supplied the right loads, source, unknown warranty and citation, while explaining that A exceeded the 10 A limit; it omitted 12 in the prose.

Official scores have not been changed or silently inflated. A versioned rubric update should explicitly publish canonical enums/accepted aliases, distinguish factual correctness from exhaustive-read evidence, and request structured rejected-load/limit fields if both numbers are mandatory. Add contract-valid alternative-answer tests to the evaluator before relying on a new ranking.

## Recommended additions: three focused baselines

| Priority / ID | Baseline | Why this study supports it | Free implementation and acceptance |
|---|---|---|---|
| 1 / B06 | Tool round-trip and result handoff | Provider tool rejections and valid calculations followed by invalid final responses dominated many configurations. | A frozen lookup returns a fresh per-seed token. Require a real allowed tool call, valid typed arguments, correct result handoff and matching final JSON. Add separate tiny read/calculator/write subchecks; keep the reasoning trivial. Compare ReAct and native-tool transport as separate configurations. |
| 2 / B07 | Calculator-assisted numeracy | Local B01 weakness, invalid calculator arguments and successful intermediate calculations need different diagnoses. | Provide identical inline numeric inputs in no-calculator, optional-calculator and required-calculator variants. Use free Python decimal/csv routines. Include money/rounding and controlled arithmetic; score operand selection, expression, tool result and final value independently. Keep prompts/limits matched as far as the tool policy permits. |
| 3 / B08 | Semantic extraction and canonical output | Non-math direct answers were stronger, but strict wording/serialization rules obscured some factual successes. | Extract facts from paraphrased frozen documents, including negation, dates and unsupported fields. Publish canonical output enums and accepted aliases. Score facts, evidence, unknown handling and JSON/schema compliance separately, then report a strict combined pass. No subjective paid model judge is needed. |

These are recommendations/specifications, not claims that B06–B08 already exist. A small pilot should validate each evaluator with correct alternative answers and deliberate failures before another large model sweep. Use the strongest observed configurations as positive controls, and GPT-OSS-20B/local Qwen as protocol/result-handoff diagnostics. Instruction-injection and longer team workflows remain later coverage candidates; this study did not directly measure them.

## Operational evidence and limits

C: filled while checkpointing after 22 completed cases. Every copied file was verified, the original output was preserved as a workspace backup, and the unchanged plan/source resumed with outputs on D:. Completed cases were not repeated. This storage incident is not an LLM outcome.

Local timing logs showed some generation rates around 4.6–17.6 tokens/second during the Llama group. Timeouts measure the model/server/hardware configuration under the imposed deadline, not inability to solve a problem. B02/B03/B05 repeat frozen source contents across seed labels; B01 and B04 vary data. These small synthetic tasks do not prove general model reliability or live-web search quality.

Validation: 461 Python tests, the controlled-study DOM check, Ruff and package builds passed before freeze. Final evidence has 1,200 unique cases, 801 diagnostic JSONL files, zero A cases counted as strict passes, and confirmed restoration of `qwen3.5-9b-uncensored-hauhaucs-aggressive@q6_k`.

Execution commit: `7990fc75859df41776908fcd465a4a74e1b459c1`. Source fingerprint: `640502caf6e4c77cdd307ac946aa0a7423b9892611d356a165b7bb3dc16e1b90`.

The adjacent [task CSV](2026-11-17-five-task-matched-tasks.csv), [model/task CSV](2026-11-17-five-task-matched-models.csv), [calculator CSV](2026-11-17-five-task-matched-calculator.csv) and [aggregate provenance JSON](2026-11-17-five-task-matched.json) contain the compact evidence. Detailed diagnostics, per-case reasons and supplemental rubric observations remain local under the study ID. [Runner instructions](../controlled-study.md) describe reproduction.
