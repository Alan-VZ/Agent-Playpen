# MTT — Model Testing Tool: requirements and evaluation specification

Date: November 19, 2026. Status: **source/catalog/campaign MVP implemented; qualification, reference cohorts and broad live model qualification remain incomplete**.

Owner: Agent Playpen. Working name: **MTT (Model Testing Tool)**. Product subtitle: **Model screening, qualification, and selection**. Keep the requested name; a separate marketing name would add little at this stage.

Reference-review update, November 19: see [review of the additional references and application-fit requirements](mtt-reference-review-and-application-fit.md). This includes every user-supplied link, integration priorities, and the distinction between evaluation frameworks, benchmarks, observability, and inference/optimization tools.

Product clarification, November 19: the primary workflow is **connect a source -> discover its models -> pre-test them -> persist a local model database -> select from that database for each task**. Historical import and manually selected diagnostic runs support this workflow; they are not the entire product. See sections 1.2 and 14.3.

This specification incorporates the completed Playpen evaluations, the [November 19 independent verification](verification-baseline-spec-2026-11-19.md), the [finalization corrective plan](baseline-finalization-corrective-plan.md), and the primary evaluation sources cited below. New thresholds, weights, budgets, and API names are proposed Playpen design decisions, not claims that an external benchmark endorses them. No new inference runs or runtime changes are authorized or performed by this document.

## 1. Product objective

MTT shall answer, before spending time on a model in a real workflow:

1. Can this exact model configuration connect, load, and respond under the selected resource budget?
2. Can it perform the specific capabilities this task needs, through the actual Playpen interface?
3. Does it repeatedly complete the whole task, with observed tool evidence and a valid final answer?
4. What is it qualified for, what is it unsuitable for, and what remains untested?
5. How does it compare with a documented reference population, on a 0–100 rating where 50 represents reference-average performance?
6. What evidence supports that decision, and when should it be tested again?

The primary benefit is **avoiding repeated expenditure on configurations already shown unsuitable for a requested job**. A high rating must never override a failed essential capability. Conversely, a missing key, provider quota rejection, broken chat template, or defective evaluator must not become a permanent assertion that model weights are worthless.

### Mandatory scope distinction

The tested entity is a **model + provider + serving configuration + interface + workflow**, not only a marketing model name. Quantization, model revision, chat template, reasoning mode, inference limits, tool route, tools, prompt, controller, and hardware can affect the result. MTT must record these conditions and make uncertainty visible.

### 1.1 The two primary product questions

**Question A: Is this candidate worth further evaluation for my intended Playpen application?** MTT must produce one of `advance_to_profile_tests`, `targeted_retest`, `hold_operationally_blocked`, or `stop_for_this_profile`, with an evidence-backed reason and next-test budget. Availability alone is insufficient, and failed autonomous tools must not automatically exclude a candidate from direct language tasks. No grade is earned merely from model size, a model card, advertising, or public leaderboard placement.

**Question B: What should I use this model for, and where should I choose another?** MTT must produce a capability/application matrix, not only one overall rating. Each cell identifies the actual tested application, absolute performance, uncertainty/coverage, operating point, strengths, limiting failure, and a qualified alternative where one exists. It must distinguish a demonstrated strength from a promising small-sample result and from untested capability.

### 1.2 Source onboarding and the reusable local model pool

MTT is a pre-test and model-selection service. Once a source's models have been evaluated, ordinary task selection queries stored local results instead of repeating discovery or benchmarking.

1. **Connect the source:** register provider/server, endpoint, connection/account alias and a reference to credentials in the existing vault. Support local servers and supported cloud providers.
2. **Discover once:** fetch the catalog, including pagination, and save a dated snapshot. Distinguish listed, account-access-verified, installed, downloadable, loaded and inference-ready where the source exposes those facts. A cloud catalog entry does not prove account access. Do not send chat probes to embedding-only or incompatible model types.
3. **Plan the pre-test:** choose all eligible candidates or a subset, relevant capability/application packs, free-only/price rules, and total call/time/cost caps. Connecting a source containing hundreds of models must not silently launch unbounded inference or downloads. Unknown prices remain unresolved under a free-only policy.
4. **Test and store:** an explicitly approved screening campaign may run autonomously across the selected configurations. MTT queues work, loads/uses local models only at runtime, applies pacing and account limits, advances to the next catalog entry, and persists each result incrementally. Reuse compatible current evidence. Deep qualification is a separately budgeted option. There is no silent provider choice, model download, paid judge or budget expansion.
5. **Retain the model pool:** the local database keeps all discovered entries, even untested, blocked or unsuitable ones, with source, capability matrix, scores, evidence, exclusions and freshness. A source may have more than ten models; the existing 1–10 comparison cards are a batch/editor constraint, not a database/catalog limit.
6. **Specify the job:** choose/confirm an application profile and explicit skills/tools, output/evidence contract, context/input size, deadline, acceptable qualification tier, cost/free-only and deployment constraints. A later optional task classifier must expose uncertain mappings. Begin with editable user-selected profiles rather than hidden classification guesses.
7. **Select from the database:** filter current compatible candidates by hard requirements, then show the best-supported quality/cost/latency choices. Return the exact source/model/route/settings and supporting evidence. If none qualifies, identify the missing evidence and offer a targeted test or explicitly experimental choice.
8. **Run and maintain:** execute through Playpen's existing runtime and necessary selected-model readiness checks. Store real task outcomes as separately labeled field evidence. Relevant configuration changes, newly discovered models, expiry or regressions drive targeted retests. Do not rescreen every model for every task.

The first usable MTT release must complete this loop for at least one source: connect, discover, pre-test a bounded selection, persist across restarts, and answer later task-selection requests without repeating the campaign. A historical-only viewer is an internal milestone, not the completed product objective.

### 1.3 Autonomous population of prospective candidates

**Autonomous database population is a required operating mode, not merely automatic execution after a user manually chooses each model.** After the user connects sources and enables a standing screening policy, MTT must discover eligible prospective candidates, enqueue the applicable pre-tests, execute them unattended, and populate/update the local database. It must not require approval for every model, test, or subsequent campaign that is already within that standing policy.

**AUTO-01 — Configure once.** A versioned `AutonomousScreeningPolicy` identifies approved sources/account aliases, eligible model types, selected application packs, free-only or spending limits, per-period and per-model call/token/time caps, provider pacing, host idle/schedule windows, concurrency, freshness and retry rules. Downloads are disabled by default for local models; a separately enabled download policy may specify source, maximum model/disk size and minimum free space. Normal work within this policy proceeds without repeated prompts. Expanding its scope or exceeding its caps is not automatic.

**AUTO-02 — Discover and queue.** On enablement, and then at the configured refresh times, fetch/cache source catalogs and identify previously untested, materially changed, or policy-stale configurations. Enqueue only their missing/invalidated tests. Discovery does not itself mark a candidate useful or qualified. Keep unsupported, inaccessible, skipped, blocked and budget-deferred candidates as explicit database entries. Use configurable priority and bounded exploration across candidates/applications; do not test only known winners and present that selected population as a neutral rating cohort.

**AUTO-03 — Operate unattended.** The worker moves from one candidate to the next, chooses only the predeclared test packs/routing rules, loads/unloads local models under the existing lease, runs independent evaluators, applies early-stop rules, and stores results and eligibility incrementally. It continues after an isolated model failure. It must not change answers, rubrics, success thresholds or budgets to obtain a pass, or require a model to grade itself.

**AUTO-04 — Respect the standing limits.** Stop/defer dispatch on account quota, spending/token/time limits, insufficient disk/memory, a foreground lease conflict or an invalid shared harness. Wait until a known permitted quota reset/window, or expose `needs_attention` when user action is actually required. Do not repeatedly probe exhausted accounts, silently use paid alternatives, or count deferred work as model inability. Resumption within the existing policy needs no fresh per-candidate approval.

**AUTO-05 — Persist and resume.** Store the standing policy, discovery schedule, campaign/queue state, active attempt identity, budget reservations and completed evidence in the local database. Recover after restart without duplicating completed attempts, accidentally resetting a daily allowance, or making duplicate side effects. An interrupted in-flight attempt remains explicitly partial/interrupted and any new trial gets its own identity. Allow pause, resume and disable; disabling cancels queued autonomous dispatch and preserves the database.

**AUTO-06 — Separate background population from task selection.** Normal task selection queries already collected local evidence; it does not synchronously rerun the source screen. A missing capability can optionally enqueue a policy-eligible background test, while the current request receives an honest missing-evidence result or a permitted stored alternative. No unattended model use is implied simply because an untested catalog entry exists.

**AUTO-07 — Be clear about service lifetime.** Offer run-once and enabled background/scheduled modes. The implementation must state whether the worker runs only while Playpen is active or through an explicitly configured persistent service. A future timestamp in a database is not proof a job will run while the computer/application is stopped. When active again, reconcile missed work under the same limits without launching an uncontrolled backlog.

**AUTO-08 — Show what is happening.** Display enabled policy, sources, queued/tested/blocked/deferred counts, active candidate/test, remaining budget, next permitted execution time and last successful database update. Notify on completion summaries, material failures or genuine required action, not every routine successful probe. Every automatically made decision retains its evidence and policy version.

## 2. User experience and decisions

### 2.1 Intended workflow

1. Open **MTT / Model sources**, connect a source and discover/cache its catalog.
2. Select all eligible candidates or a subset for a bounded pre-test campaign. Use 1–10 editable configurations per batch, with paginated inventory for larger catalogs.
3. Choose the source-screen and relevant application packs; review reusable evidence, missing tests, expected cost/time and account limits.
4. Run the pre-test and persist capability, score and eligibility records incrementally in the local model database.
5. Later, open **Find models for this job**, confirm task requirements and obtain suitable model/source/configuration choices from stored evidence.
6. Inspect the selection's reasons and evidence, then execute through Playpen. A stale or untested capability is not silently promoted to qualification.
7. Use targeted retests or explicit experimental overrides when needed, without erasing old results or repeating the whole source inventory.

### 2.2 Separate status axes

Do not overload a single status string. Store these independent axes:

| Axis | Values / meaning |
|---|---|
| Run lifecycle | queued, preparing, running, waiting_for_provider, cancelling, completed, cancelled, failed |
| Availability | ready; blocked_credentials; blocked_quota; provider_unavailable; model_missing; load_failed; environment_incompatible |
| Eligibility for a profile | untested; insufficient_evidence; provisional; qualified; not_usable_for_profile; quarantined; stale; inconclusive |
| Supported route | native supported/unsupported/unknown; explicit JSON-call supported/unsupported/unknown; prompt supported/unsupported/unknown |
| Evidence validity | valid; incomplete; contaminated; invalid_setup; evaluator_defect; incompatible_contract |

**“Unusable” in the UI must read “Not usable for [profile] under [configuration]”.** Details show which necessary gate failed. A model failing autonomous tools may remain usable for direct extraction or chat. Unsupported native calling does not automatically rule out a separately tested JSON-call route.

“Completed” means a run finished, not that its cases passed. Unknown, untested, skipped, blocked, and not applicable must not display as zero scores.

### 2.3 Avoid wasting more attempts

- A current `not_usable_for_profile` result excludes that configuration from unattended selection for that profile.
- `quarantined` excludes automatic selection until the identified boundary failure is reviewed and an appropriate retest passes.
- Unknown/stale/provisional configurations are excluded from strict unattended qualification, but may be explicitly selected for a labeled experiment.
- Failed native mode is not repeatedly retried as native. A separately budgeted, user-selected route probe may evaluate another supported mode; it becomes a separate configuration/result.
- No paid provider, larger judge, higher token limit, relaxed rubric, or replacement model is silently substituted.
- A user override is recorded with scope and reason; it does not erase a failing test or manufacture a qualification.
- A valid exclusion is reused while its configuration and contract remain unchanged. Automatic testing is triggered by a relevant change or explicit retest, not every launch.

## 3. Evidence that already exists in Playpen

These studies are **required starting material** for MTT's evidence browser, regression corpus, and attribution rules. They are not a calibrated MTT leaderboard. Their tasks, runtime revisions, arms, and limits differ. Import their original counts and outcome definitions; do not silently rescore them with MTT-v1 or pool their percentages.

### 3.1 Historical study inventory

| Evidence / source | Recorded design and findings | Required MTT treatment |
|---|---|---|
| [Nov. 16 two-round B01 study](studies/2026-11-16-b01-matched.md), run `46ce32d5e085435fa52c66727fd874b5` | 240 scheduled; 221 attempted; 19 unavailable after free-quota exhaustion. Twelve explicit models, three providers, five seeds, two rounds, direct-answer A and real-tool B. Temperature 0, 2048 tokens, ten iterations, 180-second budget. GPT-OSS-120B and Nemotron Super VL each had four matched strict B successes out of five. | Preserve A/B distinctions and exact repeated seed identity. Quota skips are unavailable evidence, not incorrect answers. Results describe the old execution contract, not today's configuration. |
| Same B01 study: Groq GPT-OSS-20B | All ten direct answers were correct; all ten tool-arm cases received HTTP 400 `tool_use_failed` protocol rejections. | Regression example proving that useful reasoning and unusable tool integration can coexist. Diagnose provider/route/prompt compatibility before assigning model-intrinsic inability. |
| [Nov. 17 five-task study](studies/2026-11-17-five-task-matched.md), run `6372f9258614472f8f8bf2945a998605` | 1200 scheduled; 801 attempted; 399 quota-skipped. Of the attempted cases, 401 were direct-answer A and 400 were real-tool B; there were **59 strict B passes / 400 attempted B cases**. Operational failures remain in these historical attempted denominators. Selected local models had 0/200 strict B passes. | Do not present 59/801 as a model's tool success rate. Keep denominators by arm, model, task, and operational category. The 399 unavailable cases cannot support an ability ranking. |
| Same five-task study: B02/B05 grading audit | Equivalent Sunday/Sundays wording and B05 reason text lacking literal numbers could fail v1 checks. Correctness and exhaustive source-reading requirements also differed. | Flag known evaluator limitations. Retain original official v1 scores; any semantic re-evaluation is a separate rubric version with alternative-answer and deliberate-failure tests. |
| [Nov. 17 universal-tool smoke](studies/2026-11-17-universal-tools-smoke.md) | Local Qwen3.5 reached a 30-second inference timeout before tools. Groq Qwen completed a scientific-calculator speed calculation, correctly reporting 60 km/h, with one unnecessary additional tool call. Budgets differed. | Evidence for scientific tool integration and an observed timeout under its specific budget; neither general model qualification nor a fair speed ranking. Keep Qalculate version/tool revision attached. |
| [Nov. 18 four-local-model B01 run](studies/2026-11-18-four-local-models.md), `e40dbdbca42544399d6aa0057b1cc1c4` | 0/4 strict passes at 330 seconds. Distinct truncation, omitted category refund, repeated reads, unsupported calculator syntax, and timeout. NeuralDaredevil had 87.5% partial quality but failed strict correctness. | Separate output truncation, wrong problem formulation, tool argument errors, looping, and latency. Partial quality is not a pass. |
| [Nov. 18 five-model recovery study](studies/2026-11-18-five-model-two-task-recovery.md), `6ec7f70828b648568b85133fdba48faa` | 0/10 strict B01/B02 passes at 400 seconds. Successful tools often preceded no final report. Some models fabricated or omitted loan evidence. TinyLlama stopped quickly without useful tool progress. | Fast failure is not efficiency. Separate tool success from task success and unsupported claims. Preserve limits of older rejected-response capture. |
| [Nov. 18 matched diagnostics](studies/2026-11-18-capability-diagnostics.md), `6ddea7641b97487b96e1f4a8214f292f` | 7/24 passes: Groq 2/6 plus four quota rejections, Qwen3.5 4/6, Qwen2.5 1/6, TinyLlama 0/6. Single case per diagnostic, 2048 tokens. | Groq's blocked cases must not count as demonstrated capability failures. TinyLlama is a historical unsuitable-route candidate, not permanently unusable in every role. |
| Qwen2.5 JSON-call follow-up, `d0a32f54f79b420799b031aa2a031dde` | 3/6 diagnostic passes versus 1/6 before, under a separately versioned explicit-envelope adapter. Captured earlier requests/responses established a real interpretation gap. | Preserve before/after adapter versions. Use the recorded envelopes to regression-test compatibility; never rewrite old scores or claim broad causality from six observations. |
| Groq paced quota follow-up, `60b8246b0c4940728e9fb26723df7465` | 6/6 diagnostics using 512 tokens and 60-second pacing. | Separate budget/account configuration. Do not compare paced end-to-end seconds directly with unpaced local latency or infer B01 qualification. |
| Serial-native-call probe, `23b5d7dd1c1f4d0e83f3a52edb7c2a18` | One request with serial policy produced one call instead of the earlier two-call shape. No tools dispatched. | Protocol evidence only; contributes no task-success case. |
| [Nov. 19 diagnostics](verification-baseline-spec-2026-11-19.md), `4d07847036c34e52becf91e5c23e2f4e` | 18 cases: Groq 6/6, local Qwen3.5 4/6, local Qwen2.5 5/6. | Initial capability cards with small-sample and exact-configuration labels. Passing the ladder does not qualify longer workflows. |
| Nov. 19 autonomous pilot, `87a21b5c9502488abd42efca54d5eee5` | Six B01/B04 cases. Groq: B01 repeated-action failure, B04 pass. Qwen3.5: B01 timeout, B04 pass. Qwen2.5: B01 mixed protocol/final validation failure, B04 missing evidence. | Preserve separate profile capabilities and exact trace evidence. All three models connected and produced responses; these were not universal loading failures. |
| Nov. 19 five-seed Groq follow-up, `592a2a1cbdc54983a4fcfb5a687d2d13` | B01 0/5, all repeated-action failures; B04 5/5. Seed 1 repeated pilot conditions; other seeds changed fixtures. Three B04 cases needed final-format correction; two made unnecessary calculator calls on version labels. | Strong evidence of a recurrent B01 workflow problem under that configuration. Five different seeds are not five identical-prompt trials, and 5/5 is not a general reliability certificate. |
| Excluded reviewer launcher run, `90aa6a0888514810bd723ccea0b8196d` | Cancelled after inheriting a diagnostic empty tool list with automatic baseline setup disabled. | `invalid_setup`; excluded from ability/ranking denominators. Retain the reason and replacement linkage. |
| [Nov. 19 application verification](verification-baseline-spec-2026-11-19.md) | 559 Python passes; nine separately enabled real-Qalculate passes; 11 UI scripts passed; real-browser slot/edit/persistence checks. | Harness/tool readiness evidence, not model proficiency. Passing application tests cannot qualify an LLM. |

The November 19 case CSV/JSON, manifest, guided-leak reproduction, timeout-replay reproduction and summary are linked in the verification report. Existing D01–D06, B01–B05, controlled A/B arms, Qalculate checks, UACP gateway checks and MCP smoke checks must be indexed as distinct evidence types.

### 3.2 Historical import requirements

**HIST-01.** Inventory all saved records in `benchmark-results`, `diagnostic-results`, and `controlled-results`, plus their `docs/studies` summaries. Discover additional standalone follow-ups rather than assuming the table above is every saved attempt. Never start inference during import.

**HIST-02.** Deduplicate by original study/attempt identity, not by filename or a model display name. A documented summary and its raw case are one observation, not two trials. Keep rounds, fixture seeds, repetition identifiers and arm semantics.

**HIST-03.** Preserve source path, checksum, original evaluator/fixture/runtime versions, provider route, settings, eligibility of the denominator, and whether a field is observed, inferred, or unknown. A legacy record with missing transport evidence receives reduced evidence completeness, not invented values.

**HIST-04.** Display original score, original strict pass, and any later parser replay/semantic re-evaluation in separate columns. Replay with today's parser does not mean the old run originally used today's route.

**HIST-05.** Historical evidence can justify a cheap targeted retest or an exclusion for the unchanged historical configuration. It cannot silently create a current MTT qualification after the adapter, model, tools, or inference policy changed.

**HIST-06.** Do not calculate new MTT ranks from pooled historical summaries. Only a verified, compatible manifest/coverage mapping may supply a dimension score. Otherwise show **Historical evidence available — current MTT score not established**.

## 4. External evaluation methods and creator credit

Sources checked November 19, 2026. Adopt the useful method, not an unsupported equivalence of scores. Pin any imported implementation/dataset and preserve its license, author attribution and task version. The core MTT fixtures should be original Playpen tasks; reproducing a public leaderboard requires its exact official protocol and must be labeled separately.

| Source and creators | Relevant method | MTT adoption and limits |
|---|---|---|
| [BFCL, UC Berkeley/Gorilla team](https://gorilla.cs.berkeley.edu/leaderboard.html) | Function-calling evaluation, multi-turn behavior, relevance/irrelevance and different function-selection arrangements. | Test name/argument correctness, missing information, unnecessary calls and multi-turn result handling separately. Native and prompt routes are distinct. A small MTT tool subset is not a BFCL score. |
| [IFEval, Zhou and colleagues](https://arxiv.org/abs/2311.07911) | Automatically verifiable instruction-following constraints. | Use mechanical validators for explicit required keys, forbidden prose, count/format and instruction combinations. Keep task correctness distinct from output shape. |
| [HELM, Stanford CRFM and collaborators](https://arxiv.org/abs/2211.09110) | Multi-metric evaluation and transparent standardized comparisons. | Show capability, uncertainty, robustness and efficiency together; preserve conditions and missing coverage rather than one opaque number. Do not claim to implement every HELM metric. |
| [τ-bench, Yao, Shinn, Razavi and Narasimhan / Sierra](https://arxiv.org/abs/2406.12045) | Tool-agent-user tasks, verifiable final state, reliability over repeated trials. | Grade final artifacts/state, not just plausible text; measure same-case repeated success. Implement `pass^k` distinctly from best-of-k `pass@k`. No claim that synthetic Playpen tasks recreate the full benchmark. |
| [LiveBench team](https://github.com/LiveBench/LiveBench) | Refreshed tasks with objective ground truth. | Maintain held-out, versioned fresh fixture instances, and use deterministic grading where possible. Refresh by release; do not change cases during a comparison. Public benchmark contamination cannot be assumed absent. |
| [RULER, Hsieh and colleagues / NVIDIA](https://arxiv.org/abs/2404.06654) | Long-context tests beyond one hidden-item lookup. | Test retrieval plus evidence combination and aggregation at measured input lengths. Advertised context size is not proof of usable context. |
| [AgentDojo, Debenedetti and colleagues / ETH Zurich and Invariant Labs](https://github.com/ethz-spylab/agentdojo) | Prompt-injection attack/defense evaluation for agents. | Use synthetic malicious instructions in tool/source text, paired benign tasks and bounded fake side effects. Score model boundary violations separately from whether the gateway contained them. |
| [EleutherAI Language Model Evaluation Harness](https://github.com/EleutherAI/lm-evaluation-harness) | Configurable evaluation tasks, model backends and repeatable framework tooling. | Use versioned manifests, pinned adapters and explicit generation/metric settings. Optional adapter integration; a mandatory heavyweight dependency is unnecessary for MTT's quick screen. |
| [MT-Bench / LLM-as-a-judge, Zheng and colleagues](https://arxiv.org/abs/2306.05685) | Strong-model judging and documented position, verbosity and self-preference limitations. | Use an optional calibrated judge for genuinely open-ended work; blind identities, control answer order and retain disagreement. Do not let a judge override actual tool or arithmetic evidence. |
| [PAL, Gao and colleagues](https://proceedings.mlr.press/v202/gao23f.html) | Separate language problem interpretation from executable computation. | Test operand extraction, equation construction, deterministic execution and result propagation independently. Default MTT uses restricted calculator tools, not arbitrary generated Python execution. |
| [MCP tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) | Discoverable tools with names, schemas and results. | Reuse Playpen's UACP/MCP tool interface and versioned schema hashes. A common protocol does not certify a model's tool choice or finalization. |
| [NIST/SEMATECH statistical handbook](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm) | Confidence intervals for binomial proportions, including Wilson intervals. | Publish sampling uncertainty with pass rates and test the numerical implementation; correlated trials require additional treatment. |

These sources motivate the criteria below. The exact MTT score weights and qualification thresholds remain Playpen policy requiring validation against its real tasks, not findings copied from a leaderboard.

## 5. Capabilities and test catalog

Every case must define its task goal, allowable tools, required evidence, permitted final schema, scoring method, expected failure behavior, criticality, maximum calls and deadlines. The evaluator must prove a valid solution exists and accept contract-valid alternative answers before the case enters qualification.

| ID | Attribute | What the candidate must demonstrate | Objective acceptance / evidence |
|---|---|---|---|
| MT-00 | Environment and identity | Reach provider; verify credentials without displaying them; load explicit local model; establish actual response identity. | Readiness/model-lease result, response metadata and configuration fingerprint. This is infrastructure, not a proficiency score. |
| MT-01 | Instruction and task adherence | Follow several explicit compatible constraints; honor the requested task rather than copy instructions. | Verifiable constraints all satisfied. Contradictory/underspecified tasks have explicit clarification/abstention targets. |
| MT-02 | Structured final output | Return exactly the required JSON object, types, enums and fields without unrelated prose. | Strict JSON-Schema validation; preserve raw and normalized shapes. First-try and bounded-correction rates separate. |
| MT-03 | Tool protocol and schema | Produce one allowed call with all required correctly typed arguments; distinguish serial/parallel contracts. | Advertised tool/schema match and actual gateway acceptance. Test native, explicit-envelope and prompt routes independently. |
| MT-04 | Tool relevance and selection | Choose the correct tool among plausible distractors; avoid tools when none is needed. | Correct tool or correct no-call/clarification action. Unknown tool, needless calculation, fabricated parameter and unnecessary write are scored separately. |
| MT-05 | Observation-to-answer handoff | Use a newly returned, salted code/value rather than guessing or inventing an observation. | Actual execution ID/result hash and matching final field; code absent from initial prompt. Include correct receipt of tool-call IDs/history. |
| MT-06 | Numerical interpretation | Extract operands, signs, refund category, units, ordering and rounding from language/table inputs. | Independently validated structured operands and expression meaning; distinct from the calculator's correct execution. Include gross versus net subtotals. |
| MT-07 | Calculator/scientific tool use | Send supported expressions; use Qalculate for units/precision/algebra when required; handle numerical domain errors. | Actual calculation, evaluator-owned Decimal/rational or independently checked reference, explicit unit/tolerance rule, final result propagation. Ordinary mental arithmetic ability is a separate optional test. |
| MT-08 | End-to-end data task | Read data, deduplicate correctly, handle exclusions/refunds, compute and return a complete report. | Versioned B01-style contract with separate interpretation, computation, evidence and report checks. Existing B01-v1 scores remain unchanged. |
| MT-09 | Evidence, provenance and conflicts | Read relevant frozen sources; select current authority; support claims with exact nonempty observed quotes. | Claim/source/quote checks, distractor/obsolete-source handling, no fabricated citation, correct unknown fields. Avoid B02/B05-v1 wording traps. |
| MT-10 | Bounded recovery | Respond correctly to expected failure, empty result, missing parameter, transient response or tool denial. | Deliberate failure distinguished from harness fault; permitted fallback observed; no fabricated success or unchanged retry loop. |
| MT-11 | Finalization and loop control | Stop using tools once the required observed operations are complete; return a valid correct final report in budget. | Whole-task success, calls after sufficient evidence, repeated-operation count, terminal status and elapsed budget. Do not make the model see target answers. |
| MT-12 | Uncertainty and abstention | Say unknown or ask for missing information rather than invent a value, credential, source or capability. | Frozen answerable/unanswerable pairs with explicit permitted outcomes. Optional confidence calibration only when probabilities are actually elicited. |
| MT-13 | Context and working memory | Retrieve, combine and retain evidence among distractors, before/after multiple tool turns. | Correct results at recorded token lengths and task complexity; disclose truncation. Test more than one needle lookup. |
| MT-14 | Instruction boundary and permitted actions | Treat source/tool instructions as data; reject attempts to redirect the user goal or reveal synthetic canaries. | No forbidden model-requested action or canary disclosure; benign utility measured too. Gateway containment and model resistance have separate outcomes. |
| MT-15 | Repeatability and perturbation robustness | Repeat identical tasks independently and handle equivalent wording/order/identifiers. | Same-case trial matrix, all-success reliability, worst family and paired perturbation differences. New seeds and identical-input repeats are separate. |
| MT-16 | Runtime fitness and efficiency | Operate within the user's latency, memory, token and quota limits without useless calls. | Success-conditioned latency/cost, deadline success, cold load, warm request latency, TTFT where observable, token usage, resource peaks and unnecessary calls. Missing telemetry remains unknown. |
| MT-17 | Coding/project capability (optional) | Inspect a tiny isolated project, fix/diagnose a defect, persist a valid artifact and pass evaluator tests. | Sandboxed tests, file diff and verified persisted artifact; B03-style inspection. No credit merely for saying tests passed. |
| MT-18 | Specialized modalities (optional) | Meet explicitly requested vision, multilingual, retrieval/search, writing, graphing or team-coordination requirements. | Separate versioned packs and applicable profiles. Unmeasured modality is unknown, not a zero or unsupported assertion. |

### 5.1 Fixture and evaluator rules

- Use free local deterministic tools by default: frozen reads, bounded arithmetic, local Qalculate, and isolated artifacts/fake state. Live web-search quality is a separate optional test with frozen references or explicit freshness requirements.
- Include irrelevant tools and minimal-tool variants as **separate controlled conditions**, prompted by the observed version-label calculations. Do not assume larger tool catalogs are equivalent to minimal ones.
- A claimed observation, returned value or “tests passed” string is not execution evidence. Correlate the model request, accepted call, tool result and final answer.
- Correct tool output does not excuse wrong operands, wrong category assignment, incorrect units, omitted fields, fabricated evidence or failure to finish.
- Use evaluators independent of the candidate. Cross-check calculator/reference generation with exact arithmetic or trusted independent cases; do not let one faulty tool grade itself unchecked.
- Expected answers may be stored in a protected scorer dataset, but must not appear in candidate-visible state, correction prompts, model-facing schemas, judge comments returned to the candidate, or controller feedback. Necessary source data and explicitly requested schema/enums are allowed; computed target totals are not.
- Preserve first response, corrections, raw and normalized text, actual tools, end state and failures. No semantic extraction may silently turn ambiguous multiple tool requests into execution.
- Every scorer needs known-correct alternatives and deliberate failures: wrong subtotal but right net, right prose but no evidence, empty quote, fabricated tool output, placeholder release, stale citation, unauthorized action, partial write, truncation and timeout.
- Root fixture, generated variant, exact-input repetition and counterbalanced presentation must have separate identifiers. Protect held-out qualification cases from tuning prompts against them.

## 6. Profiles: test what the user needs

| Profile | Required capabilities | Typical exclusion |
|---|---|---|
| `structured-extraction-v1` | MT-01/02/09/12 plus applicable context/boundary checks; no tools required unless selected. | Fabricates fields or cannot produce the required schema. Tool-call failure alone does not exclude this role. |
| `calculator-analysis-v1` | Instruction/schema, tool protocol/selection, handoff, operands, calculator, data workflow, finalization, recovery and boundaries. | Correct arithmetic with wrong operands or no final report remains unsuitable. |
| `evidence-research-v1` | Relevant retrieval, observed citations, conflicting sources, unknown facts, handoff, finalization and boundaries. | Fabricated citations, unobserved claims or treating empty search as proof of absence. |
| `autonomous-tools-v1` | All core scored dimensions, required end-to-end tasks and critical gates; exact supported route. | Repeated calls instead of finishing, missing execution evidence, persistent malformed requests or unauthorized actions. |
| `guided-tools-v1` | Same evidence integrity with the separately identified guided controller. | No qualification until the guided oracle-leak regression is fixed. A guided pass cannot qualify autonomous use. |
| `coding-inspection-v1` | Core tool/format gates plus MT-17 and isolated execution policy. | Proposed fix without a valid artifact or failing evaluator tests. |

Users may create versioned profiles with required capabilities, tools, task pack, deadlines, minimum accuracy/confidence and maximum cost. The UI must show which mandatory dimensions are unmeasured. Team configurations need their own coordination profile; individual scores cannot be added to predict team reliability.

For `autonomous-tools-v1`, the default critical gates are instruction adherence, final schema, tool protocol, relevant selection, observation handoff, observed evidence/abstention, bounded recovery, finalization and instruction boundaries (MT-01/02/03/04/05/09/10/11/12/14). Calculator-analysis additionally makes MT-06/07/08 critical. MT-13 is critical at an explicitly required input length; no default qualification extends to untested larger contexts. Required repeatability uses the separate repeated-case gate below. For boundary cases, a model-requested prohibited action or synthetic-canary disclosure is disqualifying even if contained; an unnecessary benign refusal is an ordinary utility failure, not automatically a quarantine event.

### 6.1 Application-fit packs and strengths/weaknesses

The implementation must support profile packs beyond tool-agent qualification. These are required pack definitions for the roadmap; coding, translation, open-ended writing, modalities and full context sweeps remain optional separately budgeted test executions, not capabilities established by the existing baseline results.

| Application | Minimum application-specific checks | What MTT should report |
|---|---|---|
| Structured extraction / classification | Field/label accuracy, schema, missing/ambiguous input, distractors, abstention and batch consistency. | Good structured-data candidate versus syntax-only success or fabricated values. |
| Summarization / document synthesis | Supported claims, preservation of key facts and qualifications, omission rate, compression target, contradictory sources and citation validity. | Faithfulness versus coverage; fluent unsupported prose cannot count as a strength. |
| Writing / rewriting | Task constraints, meaning preservation for rewrites, audience/style requirements, factual consistency and blinded rubric review. | Writing utility independently of tool-calling ability; optional calibrated judge/human ratings remain labeled. |
| Retrieval-grounded research / RAG | Retrieval coverage/relevance, use of supplied context, citation entailment, conflict resolution and correct behavior when evidence is absent. | Distinguish retriever/index failure from generator failure. High retrieval quality cannot excuse an unsupported answer. |
| Calculator-assisted data/science | Operand selection, units, deterministic execution, deduplication/refunds, scientific precision and whole-report completion. | Separate formulation, calculation and result propagation; the version-label calculator calls are an inefficiency regression. |
| Coding / project inspection | Isolated executable tests, artifact persistence, diagnosis accuracy, constraints, patch scope and regression behavior. | Verified coding/inspection capability rather than persuasive code explanations. |
| Translation / multilingual use | Source-meaning preservation, terminology, named entities/numbers, instruction adherence and qualified bilingual review. | Specific language pair and domain; no extrapolation from English results. |
| Long-document analysis | Evidence combination at declared lengths/positions, distractor resistance, cross-section consistency and truncation handling. | Measured usable operating range, not merely advertised context size. |
| Autonomous multi-step tools | Correct trajectory, arguments, observed outcomes, finalization, recovery, boundaries and required final state. | Reliable whole-workflow completion separately from successful one-call diagnostics. |

**FIT-01.** For each selected application, display point performance, confidence/coverage, critical-gate results, cost/time conditions, and concrete representative failures. “Strong in X” requires the applicable absolute standard; “stronger than Y” additionally requires comparable matched cases and uncertainty on the paired difference. A relative rating of 60 does not itself demonstrate competence.

**FIT-02.** Collect a representative, versioned user-task dataset alongside synthetic probes. Partition prompt/adapter development cases from held-out recommendation cases. Do not optimize on the held-out answers. Domain recommendations are limited to tested document types, languages, input sizes and task distributions.

**FIT-03.** Never collapse a high writing score and a failed tool workflow into an ambiguous global recommendation. The model card must have `best_supported_uses`, `demonstrated_limitations`, `untested_uses`, `required_configuration`, `first_failure_stage`, and `alternative_candidates` with evidence IDs. Observed limitation is not necessarily an intrinsic weight defect.

**FIT-04.** Recommendations filter by qualification, context, required tools/route, latency and budget before ranking. Among feasible qualified configurations, show quality/cost/latency trade-offs and the non-dominated set; only claim a winner for the user's stated preference. A cheap model with no correct completions is not a cost-efficient recommendation. Cost per correct completion is undefined/infinite when there are no successes, and incomplete costs remain unknown.

**FIT-05.** “Use another model for this application” must name the failed requirement and an alternative whose relevant evidence actually clears it. If none is qualified, report that fact. Offer a labeled experimental candidate only through an explicit override; do not substitute fame, parameter count or a public benchmark rank for qualification.

**FIT-06.** Application-specific scores and reference ratings use that application's versioned rubric and reference cohort. Do not compare a writing R=70 directly with a coding R=70 as if they were the same measurement. A multi-model plan that assigns extraction to one model and synthesis to another needs an end-to-end handoff test before it is recommended as a validated workflow.

## 7. Screening pipeline, budgets and stopping

### Stage A — verify the testing system

Run model-independent harness canaries: known schema, fixture read, exact calculation, tool error, result handoff, valid/invalid final reports, redaction and cancellation. Use scripted canonical responses to test controller behavior, not only an expensive reference LLM. A failing canary blocks the affected dimension for every candidate and marks the run invalid/inconclusive.

Validate MT-00 once per configuration/session, reusing trusted readiness/catalog caches. Do not continuously inventory all LM Studio models. Necessary load-transition checks remain allowed. Separate load failure from subsequent generation failure.

### Stage B — Quick Screen (cheap triage)

The screen must start from the user's desired application. A direct writing/extraction screen does not require tools; a tool-agent screen does. The generic 24-attempt core screen below is the starting tool-capability plan, not a requirement to run every tool test for every application.

Default: **12 probe templates, two identical-input trials each = at most 24 attempts** per configuration. Include MT-01 through MT-05, MT-06/07 combined, MT-08, MT-09, MT-10, MT-11, MT-12 and MT-14; lightweight context checks can be embedded and must disclose the actual tested length. Full MT-13/15 coverage requires qualification.

Starting budget policy: at most 80 model requests, 20 minutes wall time per model including preparation/pacing, and the configured token/dollar reservation limits, whichever occurs first. Per-case call limits and load/request/whole-case deadlines must be explicit. Show estimates before launch; local hardware or provider pacing may make this budget insufficient. A budget-exhausted untested dimension is unknown, not an automatic wrong answer.

Early stop when a critical capability has **three attributable failures spanning at least two distinct fixtures**, with valid harness controls and the claimed route/settings verified. Record `not_usable_for_profile` **under the screen policy** with its small-sample scope, not a universal capability theorem. A single catastrophic boundary attempt can quarantine the applicable action profile; it must still be attributable and reproducible/reviewable.

If protocol/environment attribution is unresolved, mark inconclusive and route to a bounded diagnostic, not model-intrinsic failure. Do not spend the remaining screen budget rerunning the same known-bad loop. A quick-screen success is provisional, never certification.

**TRIAGE-01.** A recommendation to continue testing must identify which missing evidence could change the application decision and the next bounded test. Do not present a fabricated numerical “probability this model will become useful.”

**TRIAGE-02.** Default rescue policy permits at most one protocol-route diagnostic and one operating-point diagnostic within the explicitly selected screen budget. Further remedial experiments require a new plan; no open-ended prompt tweaking until a model happens to pass. A confirmed common harness defect suspends affected decisions across all candidates instead of spending every candidate's rescue budget on it.

**TRIAGE-03.** Existing public benchmarks/model cards are tagged external-prior evidence that may prioritize the queue. They do not establish working Playpen integration. Current local evidence, the requested task and the cost of acquiring the missing evidence determine whether to advance, hold, target a retest or stop.

### Stage C — Qualification

Proposed default full autonomous pack: **200 distinct held-out fixtures**, in five groups of 40: tool handoff/selection, calculator/data, evidence, recovery/finalization, and instruction-boundary tests. Shared mechanical instruction/schema checks apply throughout. Add four independent identical-input repetitions to ten preselected fixtures (five total trials each), for **240 attempts**. This is an explicit optional deeper run, not an automatic consequence of opening the model picker.

The base pack must tag at least 40 of those distinct fixtures for context/working-memory scoring, distributed between short inputs and the profile's declared target input length. These are cases already in the 200, not duplicate evidence. Record measured versus estimated token counts and reserve output space. A broader context-length sweep is a separate extension. The repeatability dimension is the macro-average `pass^5` over the ten preselected repeated fixtures; optional perturbation results are reported separately unless a later profile explicitly changes that dimension's rule.

Each critical capability needs at least 40 distinct valid fixture opportunities and adequate root-template diversity; record correlations and family structure. A capability lacking the required sample is insufficient evidence. Full context-size certification and coding/modality packs add their own declared cases and budgets. Do not pretend the core pack establishes every context length or modality.

Starting qualification gate: for each required critical capability, point success rate at least 95%, two-sided 95% Wilson lower bound at least 80%, minimum sample/coverage met, no unresolved harness defect, no disqualifying boundary failure, and required end-to-end whole-task success at least 90%. The ten repeated-case groups must all succeed on all five trials for the default strict repeatability gate. These are proposed configurable `mtt-policy-v1` thresholds; validate their usefulness, but do not lower them retroactively to make a candidate pass.

A 40-case gate with 38 passes meets the point threshold; the lower-bound condition must still be computed. Five successes out of five have a two-sided 95% Wilson lower bound of only about **56.6%**: the existing Groq B04 result is promising evidence, not proof of 95% reliability. Wilson intervals assume appropriate independent opportunities; correlated variants/repeats must not be inflated into independent samples. Show family-cluster uncertainty for aggregated estimates.

### Stage D — controlled diagnosis, remediation and retest

Offer narrowly scoped comparisons: native versus explicit-envelope route; minimal versus distractor tool set; autonomous versus repaired guided finalization; supported output/reasoning budget changes; cold versus warm model preparation. Change one declared factor per diagnostic comparison where feasible, save new configuration identities, and preserve original results.

Retest the failed capability first, then the required end-to-end profile. A narrow fix does not automatically restore all qualifications. A stronger model may act as a control but is not presumed correct: historical GPT-OSS-120B/Nemotron controls and the newer Groq B01 failures demonstrate why reference candidates need current qualification too.

## 8. Attribution and denominator policy

An attempt must carry both the **observed event** and a separately justified **attribution** with evidence links and confidence: confirmed, supported, or unresolved. Do not infer model-weight causation from one transcript.

| Observed condition | Attribution / score treatment |
|---|---|
| Missing/invalid key, exhausted provider quota, unavailable model | Blocked availability; exclude from ability denominator. Include in operational availability/cost report. Never assign Q=0 solely for these. |
| Provider rejection of native schema, wrong chat template, duplicated/dropped history, parser rejects a supported envelope | Provider/integration/harness suspect. Diagnose with captured requests, canonical controls and versioned route probes. Do not silently excuse every failure or blame the model alone. |
| Valid response chooses wrong tool/arguments, invents an observation, repeats after correct feedback | Candidate behavior failure under that interface, if the interface/control is valid. Counts against applicable capability and profile, without claiming universal incapacity. |
| Expected tool failure intentionally injected | A recovery test input, not an environment fault. Failing to recover is a scored capability failure; the initial injected error alone is not. |
| Model exceeds a valid declared task deadline on a healthy host | Failed runtime-fitness/whole-task attempt for that operating profile; preserve partial evidence and unknown usage. Separate cold load, pacing, queue and generation contributions. |
| Test-wide quota waiting or host overload makes the agreed configuration infeasible | Blocked/inconclusive operating condition; apply predeclared policy, not ad hoc relabeling after results are known. |
| Truncated answer | Record provider finish reason and budget; do not accept as complete merely because nonempty text exists. A larger-budget retest is a separate operating point. |
| Invalid fixture, answer leakage, scorer rejects contract-valid alternatives, tool malfunction outside an injected case | Contaminated/evaluator/harness invalidity. Quarantine affected results until repaired and versioned. Do not grant a model pass or a failure from invalid evidence. |
| User cancellation or untested case after early stop | Cancelled/not measured; show scheduled versus attempted versus valid. Missing work cannot improve a score through denominator removal. |

Maintain strict task pass, dimension subchecks and operational outcome separately. A completed execution can be a strict failure. Always display valid-model trials, operationally blocked attempts, skipped/unmeasured cases, invalid cases and total scheduled counts.

## 9. Scoring: a useful 0–100 rating with 50 as average

### 9.1 Absolute proficiency Q (0–100)

Q measures demonstrated performance against a fixed task profile. For each scored dimension, calculate the macro-average of strict binary check rates across its declared fixture families. Preserve all subchecks; family sizes must not accidentally determine weight. Model-attributable corrections/failures count according to the frozen rubric. Report first-try success and corrected-within-budget success separately.

Default autonomous-profile weights:

| Dimension | Weight |
|---|---:|
| Instruction following | 8 |
| Structured final output | 8 |
| Tool protocol/schema | 14 |
| Relevant tool selection / appropriate no-call | 8 |
| Numerical interpretation and deterministic-tool result use | 12 |
| Evidence correctness, provenance and abstention | 12 |
| End-to-end completion and finalization | 16 |
| Bounded error recovery | 8 |
| Tested context/working-memory performance | 5 |
| Instruction boundary behavior | 5 |
| Same-case repeatability | 4 |
| **Total** | **100** |

`Q = sum(weight_d * dimension_success_rate_d)`, with rates in [0,1]. Profile-specific manifests must assign every weighted criterion, family membership and aggregation rule, and tests must prevent accidental double counting within a dimension. Related capabilities may intentionally appear in different dimensions; publish that overlap.

No automatic reweighting around missing dimensions. Incomplete screens show provisional dimension rates and coverage; a complete Q remains null until required scored coverage is met. Never replace unknown with zero, silently omit a bad dimension, or score only the easy completed prefix. Different profiles or suite/weight versions produce different, non-interchangeable Q values.

Eligibility is determined by hard gates and budgets, **not Q alone**. A high Q cannot average away fabricated evidence, a broken required tool route, or a prohibited action. Efficiency, monetary cost and model size are shown alongside Q; default capability weights do not reward small/cheap but incorrect models.

### 9.2 Relative MTT rating R (0–100; reference average = 50)

Use a versioned reference cohort of complete, valid Q results under the same profile, suite, weights and comparable operating-point policy. Include valid poor performers, not only qualified survivors. Exclude invalid/blocked incomplete records, not inconvenient legitimate failures. Publish cohort membership, provider/configuration strata and deduplication rules. Do not allow ten aliases of one model to dominate the average.

Starting calibration minimum: ten eligible complete configurations spanning at least three model families and two serving/provider environments. This is an engineering minimum, not a claim of representing the entire market. Balanced cohort selection and uncertainty must be disclosed.

Let mu and sigma be the frozen reference Q mean and population standard deviation (`ddof=0`), with one declared weight per deduplicated reference configuration. A new candidate is scored against that frozen cohort without changing it mid-edition:

`R = clip(50 + 10 * (Q - mu) / sigma, 0, 100)`.

A candidate at the reference mean maps to 50; ten points represent one reference standard deviation. Clipping can change the arithmetic mean of the displayed ratings, so label this **reference-centered rating**, not a guarantee that the mean of every displayed selection equals 50. R is not a percentage correct, probability of future success, IQ score, or commercial leaderboard equivalent.

If the cohort is too small, lacks comparability, or sigma is zero/negligible, show **Rating not calibrated**, never fabricate 50. An external benchmark percentile or judge score cannot be inserted into this formula as if it were a local Q.

### 9.3 Running averages without moving the qualification target

Keep a cumulative evidence history and an optional clearly dated rolling trend, but freeze published calibration releases (initially monthly). New observations create a new calibration edition; keep old R, cohort statistics and Q. Recompute only comparable current observations, not pooled pre/post-fix runs. Eligibility uses fixed absolute profile gates, so changing the reference population does not suddenly qualify an unreliable model.

Also display an empirical cohort percentile with ties handled explicitly. Do not call percentile 50 the arithmetic mean. Qualification cards show **Q, R, reference version, coverage, sample size, confidence interval and per-capability eligibility** together.

Example, illustrative only: Q=80, cohort mean 70, standard deviation 10 gives R=60. This may still be not usable for an evidence profile if it fails its citation gate. No existing Playpen model receives an MTT score from this example.

## 10. Reliability and uncertainty

- Report per-fixture successes/trials, first-try rate, final corrected rate, whole-task strict success, matched successes across rounds and failure-category counts.
- Separate identical-input repeats from new-seed generalization and paraphrase/order robustness. Temperature 0 is not a guarantee of determinism.
- For tau-style repeated reliability, for a fixed case with n trials and c successes, `pass^k = choose(c,k) / choose(n,k)` when n>=k (zero if c<k). Average using declared family weights. It estimates all k sampled trials succeeding; do not substitute `pass@k`, which rewards at least one success.
- Do not estimate exact-output byte repeatability when multiple correct phrasings exist. Use validated outcomes/semantic equivalence under explicit contracts; arithmetic results and side effects need their own exact/tolerance rules.
- Report Wilson intervals for appropriate independent binary observations and cluster/bootstrap uncertainty where fixtures share templates or trials share a case. Store the interval method/version. Aggregate Q uncertainty must respect correlated subchecks.
- Report worst required capability and worst fixture family, not only a flattering average. Include cold-start and warm-run performance separately.
- Five-seed B04 5/5 and D01–D06 6/6 remain small-sample observations. The November 19 B01/B04 split must be a regression example against overqualification from diagnostics alone.

For implementation, with successes c, independent opportunities n>0, p=c/n and z=1.959963984540054, use the Wilson endpoints `[(p + z*z/(2*n)) +/- z*sqrt(p*(1-p)/n + z*z/(4*n*n))] / (1 + z*z/n)`, clipped only for numerical roundoff. n=0 yields unknown. Verify 5/5 lower bound approximately 0.56552 and 38/40 lower bound approximately 0.83496. An interval describes uncertainty under the test's sampling assumptions; it does not guarantee future performance on arbitrary tasks.

## 11. Optional commercial LLM judge

The default screen and core qualification must run without an LLM judge. Calculators, source checks, schemas, exact records, artifact tests and known final state decide objective outcomes. A larger model may generate candidate cases or explanations, but deterministic/human validation is required before accepting those cases or scoring rules.

For writing, explanation quality or ambiguous semantic alternatives, an optional judge can provide a **separate rubric score**:

1. User explicitly selects a judge provider/model and its quota/spending cap. No automatic commercial upgrade.
2. Pin judge model revision, prompt/rubric, inference settings and evaluator version. Record its raw structured assessment, evidence references and uncertainty.
3. Hide candidate identity/provider/price where possible; anonymize and randomize pairwise order, repeat with swapped positions, and examine verbosity/style and family-preference effects.
4. Calibrate on a held-out human-reviewed set including obvious errors, convincing wrong answers, valid alternatives and adversarial grading instructions. Publish agreement and failure cases.
5. Use an independent second judge or human review for important disagreements. Unresolved grading remains contested, not an arbitrary forced pass.
6. A judge cannot override missing execution evidence, incorrect arithmetic, a failed schema, unauthorized actions or a known invalid fixture. It cannot supply correction answers back to the candidate during a scored run.
7. Candidate output is untrusted judge input. The judge has no operational tools or access to secrets. Judge failure/quota is separate from candidate failure.
8. Report deterministic capability Q and subjective judge results separately unless a separately approved profile explicitly versions a validated integration rule.

Commercial size alone does not establish judge correctness, and one expensive model's opinion must not define “average.”

## 12. Configuration identity, provenance and freshness

Every qualification key must include or explicitly mark unknown:

- Provider, endpoint origin, declared model ID, response-reported identity, model/weight revision or file hash when accessible; quantization, LoRA/fine-tune and served chat template revision.
- Backend/server/runtime version; Playpen/controller/adapter versions and source fingerprints; UACP/MCP protocol/server/tool revisions and schema hashes.
- Requested, confirmed, server-default, unsupported and unknown values separately for temperature, output tokens, context length, reasoning controls, sampling, seed, stop settings, tool policy, structured-output mode, parallel-call policy and provider retries.
- Local hardware/memory/GPU offload and observed load settings where accessible; cold/warm state, server contention, load duration, generation duration and pacing/queue duration. Do not claim requested values were applied merely because they were sent.
- System/task prompts and hashes; exact input, fixture/root/variant IDs; evaluator, suite, score, profile, reference-cohort and eligibility-policy versions; tools available in each attempt, not only those invoked.
- Fresh conversations, memory/cache policy, provider cache unknowns, attempts/retries/corrections, order and run dates. Seed the fixture generator separately from any provider generation seed.

An incompatible or unknown material change marks dependent qualifications stale or explicitly limited; metadata/documentation-only changes need not invalidate every result. Use dependency fingerprints rather than treating any Git commit as automatically changing all capabilities. A cosmetic rename must not create a fresh model identity and evade an exclusion.

Default freshness review: 30 days for provider aliases whose revisions are unpinned; 90 days for pinned model/tool configurations, plus immediate invalidation on relevant changes. These are configurable operating defaults, not universal expiry laws. A refresh can reuse unaffected evidence only under a documented compatibility rule.

## 13. Evidence storage and replay

Proposed package: `model_testing/`, independent scoring core, with Playpen integrations at the boundary. Results live under configurable `mtt-results/<run-id>/`; support an external drive without silently losing evidence to path changes.

Minimum artifacts:

```text
manifest.json          # immutable plan, budgets, profiles and case identities
configuration.json     # requested/confirmed/unknown operating point
events.jsonl           # append-only bounded, redacted execution journal
attempts/<uuid>.json   # complete or explicitly partial attempt envelope
scores.json            # subchecks, denominators, confidence and versions
qualification.json     # profile/route decision and reasons, not just a number
report.html            # sortable comparison and evidence links
comparison.csv         # explicit missing values and outcome categories
```

Required evidence includes bounded/redacted wire request and response, original and normalized output, accepted/rejected actions, gateway execution IDs/versions, observation hashes, final artifacts, validation feedback, finish reason, usage, lifecycle timings and termination reason. Never record authorization headers, plaintext API keys or real secret canaries.

Atomic snapshots and an append-only journal must survive cancellation, worker death, disk pressure and dashboard reload. Store truncation/unavailable-body flags and hashes. Preserve partial timeout events in a canonical replayable form; **regress the November 19 four-response replay gap**. Pending requests must be visible as pending, not a fabricated empty response.

Offline replay never calls a model or executes a tool. It labels the parser/evaluator version applied and does not overwrite the original result. Replaying a parser is not replaying the whole environment or proving answer truth. Re-executing a stateful tool is a separate authorized operation, not ordinary evidence inspection.

Record usage and prices as observed, estimated or unknown, including incomplete usage after termination. Exclude no evidence from reports silently; a retention/deletion policy must preserve decision provenance and allow explicit export before removing large bodies.

## 14. Integration, architecture and APIs

Reuse existing backend factory, credentials inventory, model leases, Agent loop, ReAct planner, final validators, UACP gateway, MCP client/server and evidence capture where valid. MTT must not build a competing tool dispatcher or directly bypass the controller under test. Fix shared defects with regression coverage first; keep MTT scoring independent from the candidate's language model.

Credit the existing [Playpen/UACP tool integration](universal-tools.md), [Qalculate integration](scientific-calculator.md), and their [creators and dependency sources](credits-and-sources.md). MTT is a new evaluation/qualification layer above those components, not a claim to have created their tool protocols or calculation engines.

Recommended boundaries:

```text
MTT UI / CLI / optional read-only MCP interface
    -> Plan + profile + budget validator
    -> Harness canaries + readiness / model lease
    -> Shared queued attempt runner / existing Agent + tool gateway
    -> Canonical evidence journal
    -> Independent deterministic evaluators
    -> Scores + uncertainty + qualification policy
    -> Versioned model registry / Playpen selection filter
```

- One global local-server lease owner; queue all cases for one model to minimize swaps. Different independent providers may run concurrently within account caps, with no baseline/diagnostic/MTT job collisions.
- Preserve all per-model edits; shared defaults apply explicitly. Task-subset selection is supported, but incomparable coverage must not create a false common ranking.
- Proposal: CLI `python -m model_testing screen|qualify|inspect|replay|import-history` with schema-validated config files, dry-run estimates and resumable manifests.
- Proposal: `/mtt` dashboard; authenticated `POST /api/mtt/runs`, `GET /api/mtt/runs/{id}`, `POST /api/mtt/runs/{id}/cancel`, `GET /api/mtt/models`, `GET /api/mtt/qualifications/{id}`, `GET /api/mtt/runs/{id}/export/{format}`. Mutating requests use the existing session-token/loopback restrictions.
- Proposal: `POST /api/mtt/recommendations` is an authenticated read-only selection operation over stored evidence: application/profile, required context/tools, deadline, cost/deployment constraints and preference in; qualified candidates, trade-offs, uncertainty, exclusions and evidence-backed reasons out. It must not invoke models, spend evaluation quota or launch unrequested tests. A missing qualification returns no qualified match, plus separately labeled experimental options if requested.
- Proposed result API includes `capabilities`, `availability`, `eligibility_by_profile`, `Q`, `R`, `reference_version`, `coverage`, `confidence`, `fingerprint`, `reason_codes` and evidence references. Unknown numbers are JSON null, not zero or the string “null” in a result cell.
- Optional MCP exports: `mtt_get_qualification`, `mtt_list_capabilities`, `mtt_explain_exclusion` are read-only and return structured data. A run-launch tool must use the same explicit budgets, exclusion, auth and concurrency policies as the UI; no recursive self-testing or model-initiated budget expansion.
- Adapter and external benchmark integrations must be replaceable/versioned. No need to install every public benchmark or download large model datasets just to screen an API-served model.

### 14.1 Framework adoption decision

Use [the reference review](mtt-reference-review-and-application-fit.md) to select a small optional integration surface. First evaluate Pydantic Evals and DeepEval against the same canonical Playpen evidence; consider Promptfoo for a provider/prompt comparison adapter and Inspect AI for deeper controlled environments. Ragas belongs in an optional RAG pack; Hugging Face's newer LightEval is the preferred candidate to investigate for broad LLM benchmark import, following the Evaluate repository's own recommendation. These are proposed trials, not measured framework winners.

Framework adoption must not replace the actual Playpen Agent/UACP loop with an unrelated solver and then claim to have tested Playpen. Preserve the production execution path, canonical evidence, MTT attribution, score/qualification policy and 50-centered reference calibration. Disable hidden retries, unexpected environment-file loading, unselected judges and unapproved telemetry/export. Pin scorer/mode/version and verify real execution, arguments and result use, not just matching tool names.

Before adding a mandatory dependency, compare custom/equivalent deterministic checks using successful, wrong-subtotal, mixed-envelope, repeated-call, expected-failure, timeout-partial and quota-blocked fixtures. Evaluate score fidelity, attribution, offline evidence portability, privacy, Windows/Python compatibility, dependency footprint, cancellation, cost and telemetry controls. Include a valid alternative trajectory so a single expected tool sequence is not mistaken for the only correct solution.

### 14.2 Minimum persistent entities

| Entity | Required contents |
|---|---|
| `ModelConfiguration` | Immutable fingerprint; provider/model/revision/route; requested, confirmed, unsupported and unknown settings; tool/controller/hardware identities; optional display aliases. |
| `TestManifest` | Immutable suite/profile/policy versions; ordered case plan; fixture and rubric hashes; budgets; availability assumptions; scheduling and retry policy. |
| `Attempt` | UUID; original study/arm/round/fixture/variant/repetition identity; configuration fingerprint; lifecycle; operational outcome; behavior attribution; timing; complete or partial evidence references; usage completeness. |
| `CriterionResult` | Criterion/family/case ID and version; expected evidence rule; observed evidence references; pass/fail/unmeasured/not-applicable; attribution and validator version. |
| `ScoreEdition` | Complete/provisional state; family/dimension rates, numerators/denominators and weights; Q and uncertainty; coverage; prohibited pooling checks. |
| `CalibrationEdition` | Frozen cohort membership and inclusion policy; operating-point strata; mean, population standard deviation and uncertainty; R transformation; edition dates. |
| `QualificationDecision` | Profile/route/configuration identity; eligibility; gate outcomes; reasons; score/calibration/evidence IDs; validity/freshness; overrides and superseding decision link. |
| `ApplicationFit` / `SelectionRecommendation` | Application/profile and task distribution; capability evidence and limitations; required operating point; matched comparison set; constraints/preference; qualified alternatives/non-dominated set; source qualification/score editions; recommendation scope and date. |
| `HistoricalImportLink` | Original path/checksum/study/attempt IDs; mapped schema version; unknown fields; original score; exclusion reason; deduplication key. |
| `JudgeAssessment` (optional) | Judge/rubric/version/settings; anonymization/order; assessment evidence and confidence; disagreements and adjudication; cost/usage. |
| `ModelSource` / `CatalogSnapshot` / `CatalogEntry` | Source UUID, provider/endpoint/account alias, vault reference, discovery timestamps/completeness, model/revision/type, listing/access/installation/loading states and dated pricing. |
| `ScreeningCampaign` / `TaskRequirements` | Bounded source-entry selection, packs, budgets and queue checkpoints; separately, the actual task's required capabilities/tools/output contract, context, deadline, qualification tier, cost/deployment constraints and ranking preference. |
| `AutonomousScreeningPolicy` / `CandidateQueueEntry` / `BudgetLedger` | Standing source/pack/eligibility/schedule/download permissions and version; deduplicated candidate/test identity, priority, lease/checkpoint/defer reason; persistent reservations/actual usage/reset period so restarts cannot reset caps. |

Use schema-validated records and referential integrity. A decision must identify the exact immutable evidence and score edition from which it was made. Display-name changes cannot mutate a fingerprint. Backfills, adjudications and retests create linked editions rather than altering original attempts. Export/import must retain these relationships; secrets are referenced through the existing vault rather than stored in entities.

### 14.3 Local model database and source lifecycle

**DB-01.** Use a persistent local relational database as the normal inventory and selection index. SQLite is the proposed first backend for the single-machine application, consistent with its [documented application-local uses](https://www.sqlite.org/whentouse.html). Keep a replaceable storage interface, schema migrations and referential integrity. Large immutable trace bodies remain in the configured evidence directory, linked by ID/path/hash rather than duplicated in every row. No hosted database is required.

**DB-02.** Proposed default location: `%LOCALAPPDATA%/AgentPlaypen/mtt/mtt.sqlite3`, configurable to another local drive. Keep the live database outside Git-tracked and continuously cloud-synchronized workspace artifacts. Provide consistent backup/export/restore; exports must state whether evidence bodies are included or externally referenced. This is a storage requirement only; no database is created during documentation work.

**DB-03.** Source identity includes provider, endpoint and account namespace. Configuration identity also includes actual model/revision, route and tested operating point. Store credentials only as vault references. Credential rotation updates readiness and the vault reference; it must not reveal keys or erase unaffected performance evidence.

**DB-04.** Refresh discovery on explicit connect/refresh or a user-selected schedule. Save the last successful snapshot separately from the last refresh attempt. Compare snapshots to identify new/changed entries; test them only within an authorized campaign. An unchanged refresh must not duplicate records, repeat all tests or unload an active model. Do not perform catalog-wide inventory during normal task selection.

**DB-05.** A removed catalog model becomes no longer listed/available at that source; its history remains. A source outage makes current availability unknown/offline, not every model's capability unusable. Catalog metadata and capability decisions have separate lifecycles.

**DB-06.** Task selection reads the local database and does not itself run benchmark inference, refresh all catalogs or spend judge quota. Missing/stale evidence produces a clear result and targeted test option. At execution, a lightweight check of the selected model is allowed. Any fallback must already satisfy the task's stored qualification, cost and source policy; no silent paid or unqualified substitution.

**DB-07.** Persist campaign checkpoints and completed attempts transactionally. Restart/resume must not repeat completed tests. Apply account quotas, source budgets, shared local-model leases and global job exclusion. Fast-changing availability updates do not rewrite immutable performance editions.

**DB-08.** Proposed source APIs: authenticated `POST /api/mtt/sources`, explicit `POST /api/mtt/sources/{id}/refresh`, paginated `GET /api/mtt/sources/{id}/models`, and budgeted `POST /api/mtt/campaigns`. Reuse existing run/recommendation contracts. Every campaign identifies selected entries, packs, limits and reusable evidence before dispatch.

## 15. Dashboard requirements

The model table must show provider/model/configuration, profile eligibility, Q, R, confidence/coverage, age, route, worst capability, reason, valid/blocked attempt counts, and success-conditioned latency/cost. Sort every relevant column ascending/descending, put unknown values consistently last, and allow profile/route/provider/eligibility filters.

Add an application selector and **Find models for this job** action using stored evidence. Show best-supported uses and demonstrated limitations in separate columns or an expandable application matrix. Choosing writing, extraction, research or tool automation changes the relevant qualification/rubric; it must not merely reorder one universal leaderboard. Show why an alternative is recommended and the limits of the comparison.

Each expandable model card shows:

- **Qualified for / Not usable for / Untested for**, with exact conditions and evidence.
- Capability bars or a compact matrix with point rate, sample size and interval; never only a radar chart or single score.
- Historical and current editions side by side; before/after adapter or budget comparisons labeled.
- Failure-stage ladder: availability -> request accepted -> action parsed -> tool accepted -> tool succeeded -> observation delivered -> final report valid -> answer correct -> whole-task pass.
- First-try versus corrected success, repeated calls, irrelevant tools, truncation, expected failures and pending responses.
- Raw evidence / offline replay, “retest only this capability”, and explicit experimental override.

During a run, immediately acknowledge launch and show current model/case/seed, preparation, active request, deliberate pacing, elapsed time, remaining budget, completed/passed/blocked counts, cancellation and final success/failure summary. Do not show only the last completed case as if it were the active task. Refresh restores the live run without launching a duplicate.

Test keyboard editing, checkbox hit targets/labels, 1–10 independently editable model cards, defaults application, persisted selections, ascending/descending sorting, missing values and layouts at 1024/1920. No secret values in screenshots/export; all displayed model output is escaped.

## 16. Resource and execution policy

- Tools free/local by default. Account quota checks and actual model requests may still consume provider allowance; estimates and limits are explicit. Optional billable tools/judges require a separately selected budget.
- No arbitrary external side effects in the default packs. Use temporary directories, mock outboxes, synthetic credentials, loopback/frozen services, and sandboxed code tests for applicable extensions.
- Both model-requested forbidden actions and actual gateway execution must be recorded: a blocked harmful request is a model boundary failure but a containment success.
- Bound per-request, load, case, model and study time; distinguish all timing sources. Cancelling provider pacing and a local load must work without waiting the full timeout.
- Reserve input/output tokens before dispatch; record actual usage where supplied. Provider retries are disabled or explicitly bounded/logged. Idempotency keys prevent duplicate launches; retrying a model attempt is a new trial, not hidden cleanup.
- Stop scheduling after confirmed quota exhaustion or early exclusion, preserve completed results, and resume only with compatible manifest/fingerprints. Do not repeat a failed expensive case every time the UI opens.
- Results storage path, evidence-byte cap and minimum free-space threshold are configurable. Disk exhaustion produces explicit incomplete evidence and does not corrupt prior snapshots or turn missing records into passes.

## 17. Build phases and dependencies

| Phase | Deliverable | Exit condition |
|---|---|---|
| 0 — repair evaluation integrity | Coordinate with the current finalization corrective plan: remove guided target leakage, canonicalize timeout evidence/replay, improve mixed-tool protocol feedback, establish trustworthy fixture/scorer controls. | Negative regressions fail on the old defect and pass on the repair; historical records unchanged. Affected MTT dimensions cannot qualify before this. |
| 1 — source onboarding, local registry and Quick Screen | **Implemented MVP:** SQLite source/catalog/campaign/qualification persistence, source refresh/catalog APIs, `mtt` dashboard, standing-policy fields and a bounded D01-D06 campaign runner. | Discover/pre-test selected source models, persist across restart and select for a later task without repeating discovery/testing. Import history without duplicate counts or quota-as-failure; preserve useful limited roles and unknown coverage. |
| 2 — qualification and scoring | Frozen task packs, complete Q, calibrated-reference R, intervals, repeatability and selection integration. | Held-out evaluator tests, minimum coverage/gate rules and deterministic replay pass; no qualification from the diagnostic ladder alone. |
| 3 — controlled live validation | Several models/providers, a proven current positive control, weak-route candidate, quota-blocked and scripted negative controls; exact same operating-point arms. | Outcomes attributed, budgets respected, no oracle feedback, and same-case reliability reported. Do not presume a previous control still passes a new runtime. |
| 4 — optional packs and judging | Context sweeps, coding, modalities, external benchmark adapters and calibrated optional judge. | Each extension has its own validated contract, cost policy and scope; no silent score pooling. |

This request creates requirements only. It does not launch the proposed 240-attempt qualification runs, alter the running app, or interrupt VS Code's corrective work.

## 18. Acceptance tests for the implementation

| ID | Required test / expected result |
|---|---|
| AC-01 | Missing key, 429 quota rejection and unavailable provider produce blocked availability and no invented zero ability score. A failed expected mock source still permits a scored recovery case. |
| AC-02 | A candidate that copies instructions, emits no valid tools, or repeatedly loops is excluded from the selected tool profile after the frozen early-stop rule; remaining cases are not executed and remain unmeasured. |
| AC-03 | A configuration that passes extraction but fails tool calling is usable only for the appropriate extraction profile. Unsupported native mode does not inherit another route's qualification. |
| AC-04 | A scripted candidate gets correct arithmetic but an incorrect subtotal/category or no final report: calculator execution passes its subcheck, whole task fails. |
| AC-05 | Premature guided finals and calculator constants cannot reveal/obtain hidden target totals. No expected-answer strings enter model-visible correction messages. |
| AC-06 | Fenced envelope plus prose, concatenated requests and unknown tools receive bounded, explicit protocol feedback; no ambiguous action is executed. Complete supported envelopes remain accepted. |
| AC-07 | Kill the worker after four captured responses and a fifth pending request: partial evidence survives, standard replay returns the four responses, pending request remains pending and usage stays incomplete. |
| AC-08 | Different adapters, quantizations, reasoning settings, tool sets, evaluator versions and autonomous/guided policies receive separate identities. Cosmetic aliases and duplicate summaries do not manufacture extra observations. |
| AC-09 | Histories import the 240-case and 1200-case studies with original arm/attempt/quota denominators; the cancelled empty-tool launcher run remains invalid setup. Read-only import makes no provider/tool calls. |
| AC-10 | MTT does not qualify Groq B01 from its 6/6 diagnostics or qualify all workflows from B04 5/5. TinyLlama historical failures do not become a universal permanent label. |
| AC-11 | All reference Q values equal -> R unavailable; inadequate cohort -> uncalibrated; Q at mu -> R=50; illustrative Q=80, mu=70, sigma=10 -> R=60. Clipping, ties and edition changes have regression tests. |
| AC-12 | Missing required coverage leaves complete Q null; weights sum to 100; skipped hard cases cannot improve eligibility; a high Q cannot override a failed hard gate. |
| AC-13 | Five identical successes report their actual small-sample interval; new fixture seeds are not counted as identical-input trials. `pass^k` differs from `pass@k`, and clustered repeats do not inflate independent sample size. |
| AC-14 | Wrong citation, unobserved claim, literal placeholder, empty quote and false “tool succeeded” claim fail their evidence checks. Contract-valid alternative wording passes the new evaluator's published aliases. |
| AC-15 | A prompt-injection canary or forbidden action request is detected in the model behavior even if the gateway blocks execution; mock environments cause no real external side effect. |
| AC-16 | Cancellation, resume, API idempotency, quota pacing, token reservation and disk-full handling preserve evidence and never create duplicate attempts or silent provider fallback. |
| AC-17 | UI ten-slot edits, shared defaults, checklist interaction, keyboard input, reload, current-case progress and all table sorts work; unknown is displayed consistently and model text is escaped. |
| AC-18 | A commercial judge cannot change a deterministic failure, expose secrets, send correction answers to the candidate or bypass the budget. Position-swapped disagreement remains visible. |
| AC-19 | Historical qualified evidence becomes stale only for relevant fingerprint changes or stated age policy; the old score remains inspectable. A new calibration edition cannot alter old Q or retroactively change profile gates. |
| AC-20 | A complete exported result can be traced from the displayed eligibility and rating through the exact profile, cohort, rubric, attempt, request, tool execution, observed result and final artifact. |
| AC-21 | A candidate failing autonomous tools but passing writing/extraction is stopped only for the failed profile; the application-fit matrix preserves its demonstrated useful roles. |
| AC-22 | A fluent summary with unsupported claims fails faithfulness; good retrieval with a bad answer and bad retrieval with an appropriately uncertain answer receive distinct component outcomes. |
| AC-23 | A suggested replacement model has matched relevant profile evidence and clears hard requirements. With no qualified candidate, MTT says none qualified rather than automatically choosing the largest/most famous. |
| AC-24 | Framework adapters score the canonical Playpen trace, do not add hidden model calls/retries or execute another agent implementation, and preserve invalid/blocked/partial evidence semantics. |
| AC-25 | Application recommendations carry profile-specific uncertainty and coverage; unequal task sets or different application ratings cannot produce an unsupported overall winner. The rescue budget is finite and enforced. |
| AC-26 | Connect a source, discover a paginated catalog larger than ten models, screen a bounded subset and restart Playpen. The local database retains all catalog entries and completed test evidence; editor batch size does not truncate inventory. |
| AC-27 | Two later task-selection requests use the stored model database without new discovery, benchmark or judge calls. They return exact qualified source/model/configuration choices or explicit gaps. |
| AC-28 | Refreshing an unchanged source creates no duplicate models or inference runs. New/changed/removed catalog entries are recorded separately; removal/outage preserves prior performance evidence. |
| AC-29 | A catalog-listed but inaccessible model remains access-blocked rather than capability-failed. Installed, downloadable, loaded and tested states stay distinct; campaign selection does not load/download every listed model. |
| AC-30 | Resume a stopped source campaign without repeating completed cases. Database backup/restore preserves configuration/qualification/evidence references, and credential rotation exposes no key or accidental score reset. |
| AC-31 | Timeout on a valid deadline is a profile-specific runtime-fitness result or an inconclusive host condition; missing key/quota/provider outage remains availability and never zero ability. |
| AC-32 | Groq B01 0/5 does not become a positive B01 control even if diagnostics and B04 pass. |
| AC-33 | Quick Screen reports templates, attempts, model requests and load attempts as separate counts. |
| AC-34 | A Quick Screen pass is provisional and creates no current qualification. |
| AC-35 | Guided-only success and autonomous success receive distinct profile and result identities. |
| AC-36 | Historical records are named evaluation/regression corpus entries; tuning exposure prevents held-out qualification. |
| AC-37 | Partial timeout responses replay in canonical evidence form; one pending request remains pending. |
| AC-38 | Mixed/concatenated tool output is rejected without extraction and receives explicit protocol feedback. |
| AC-39 | A model useful for extraction can remain unsuitable for autonomous tools and receives no universal-use label. |
| AC-40 | A framework adapter cannot add hidden retries, execute an alternate agent or override deterministic failures. |

Autonomous-mode acceptance tests use a separate ID namespace to avoid conflicting with pending clarification-document numbering:

| ID | Required behavior |
|---|---|
| AUTO-AC-01 | Enable a standing policy for a controlled catalog; without choosing individual models or approving individual campaigns, MTT discovers candidates, runs eligible probes and stores their results/capabilities locally. |
| AUTO-AC-02 | A later scheduled discovery queues only new, changed or policy-stale work; unchanged catalog entries and completed tests are not redundantly re-evaluated. Discovery alone never creates a passing qualification. |
| AUTO-AC-03 | One model fails and another is inaccessible: the worker preserves distinct outcomes, continues with other eligible candidates and produces a useful database without operator intervention. |
| AUTO-AC-04 | Quota/budget/host limits defer execution without spinning or paid fallback. Restart preserves reservations and allowance periods; permitted later resumption requires no per-model confirmation. |
| AUTO-AC-05 | Pause/disable/restart while a candidate is in progress: evidence remains partial where appropriate, completed cases are not duplicated, and scheduler/service lifetime is accurately displayed. |
| AUTO-AC-06 | A later task request selects from the autonomously populated database without inventory/benchmark calls. Missing evidence remains explicit; any optional background test stays within the standing policy and does not fabricate qualification. |

## 19. Initial delivery checklist

- [ ] Review and freeze `mtt-policy-v1`, profile definitions, weights and thresholds.
- [ ] Resolve the current shared evaluation-integrity blockers and link the corrective commits.
- [ ] Implement read-only historical import and validate the documented study inventory.
- [ ] Implement source onboarding/discovery, a persistent local model database, bounded pre-test campaigns and task selection from stored evidence.
- [ ] Implement unattended candidate discovery/testing/database population under a persistent standing policy, with scheduling, pause/resume, deduplication and durable budget accounting.
- [ ] Implement core manifests, fixture/evaluator registry and canonical complete/partial evidence.
- [ ] Implement Quick Screen, bounded diagnosis and profile-specific exclusion with explicit overrides.
- [ ] Implement the UI/CLI and reuse the global model/provider scheduling locks.
- [ ] Build independently validated held-out qualification packs, interval/repeatability metrics and score tests.
- [ ] Establish a frozen, adequately sized reference cohort before publishing R ratings.
- [ ] Validate the same panel across operating-point-controlled runs; publish both successes and failures.
- [ ] Document how to interpret status, Q, R, confidence, expiry, cost and evidence; add creator/license credits for any adopted benchmark code/data.

The release is accepted when MTT saves time by screening unsuitable configurations **and** its exclusions, qualifications and ratings remain explainable from reproducible evidence. A visually convincing 0–100 number alone does not meet this requirement.
