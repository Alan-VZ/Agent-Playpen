# MTT additional reference review and application-fit decisions

Reviewed: November 19, 2026. Companion to the [MTT requirements](mtt-model-testing-tool-requirements.md). Status: research and proposed requirements; no frameworks were installed, no integrations benchmarked and no new model inference runs performed for this review.

## 1. The user's two decisions

MTT must deliver two usable answers, in this order:

1. **Is this model configuration worth further evaluation for my Playpen application?** Return advance, bounded targeted retest, operational hold, or stop for the selected application. Explain the cheapest informative next step, or why further spending is not justified under the present policy.
2. **What applications fit its strengths, and where should I use another model?** Produce a capability/application matrix with absolute performance, evidence, uncertainty and qualified alternatives. Preserve useful limited roles even when a broader autonomous-agent role fails.

An evaluation framework can help collect and score this evidence. It does not automatically know the user's requirements, establish that Playpen's runtime is correct, calibrate 50 as average, or prove that a model will work in a new application. These remain MTT responsibilities.

## 2. Review of every supplied reference

Vendor comparisons are useful discovery guides, but their product rankings are not independent evidence. Technical integration conclusions below use the product/project's own documentation where available. Tracking parameters were removed from the LangChain URL. The Stanford landing page had no extractable text in this browser; its method and implementation were checked against the HELM paper already cited in the main requirements and the official repository.

| Supplied reference | What it contributes | Decision for Playpen / MTT |
|---|---|---|
| [LocalLLaMA curated list](https://www.reddit.com/r/LocalLLaMA/comments/1c87h6c/curated_list_of_open_source_tools_to_test_and/) | Discovery of Ragas, Promptfoo, AutoEvals, DSPy, Instructor, Guidance and Langtrace; comments also suggest Langfuse. The author explicitly notes their involvement with Langtrace. | Useful source list, not a current compatibility test or product ranking. Verify the linked primary projects. Separate evaluation from tracing, structured generation and optimization; do not install the whole list. |
| [DeepEval repository](https://github.com/confident-ai/deepeval) | Python evaluation tooling and agent-oriented metrics. Official [tool correctness](https://deepeval.com/docs/metrics-tool-correctness) distinguishes configurable matching of tool names, inputs and outputs; [task completion](https://deepeval.com/docs/metrics-task-completion) uses full-trace assessment. | **High-priority optional adapter trial.** Map actual gateway traces, enforce the strictness MTT requires, and pin the evaluator mode. Matching tool names is insufficient proof of execution or final correctness. Judge/provider requirements must be explicit. |
| [Cognee's evaluation-tool article](https://www.cognee.ai/llm-agent-evaluation-tools) | Distinguishes output, retrieval, trajectory and final outcome; surveys DeepEval, Ragas, Promptfoo, Inspect AI and Opik. | Adopt the evaluation-layer distinction. Check technical details against each project's docs. The article is not evidence that Cognee itself is needed for MTT or that one surveyed tool will solve model qualification. |
| [Evidently evaluation-framework article](https://www.evidentlyai.com/blog/llm-evaluation-framework) | Distinguishes generic model benchmarks from evaluation of the actual application, including development, release and monitoring workflows. | Adopt application-specific datasets and regression/monitoring concepts. Consider an optional reporting/monitoring export, not a second required model runner. Verify [the actual project](https://github.com/evidentlyai/evidently) before any integration. |
| [LangSmith evaluation landing page](https://info.langchain.com/llm-evaluation) | Product overview of testing and tracing. Official [evaluation docs](https://docs.langchain.com/langsmith/evaluation) describe datasets, offline/online evaluation, human/code/judge methods, repetitions and experiments. | Borrow trace-to-regression-dataset and experiment-comparison workflows. Hosted account, deployment, retention, pricing and export policies are separate adoption decisions. No LangChain application rewrite or cloud upload is required by MTT. |
| [Pydantic's comparison article](https://pydantic.dev/articles/best-llm-evaluation-tools) | Emphasizes linking scores to traces, portable instrumentation and the distinction between offline/online workflows and judge methods. It is written by a vendor promoting Logfire. | Check [Pydantic Evals directly](https://pydantic.dev/docs/ai/evals/evals/). **High-priority code-first adapter candidate** because it exposes datasets, evaluators and reports. Its docs explicitly say `pydantic-evals` does not depend on `pydantic-ai`; Logfire integration is optional. Do not confuse that library with a requirement to purchase hosted observability. |
| [Patronus LLM-testing guide](https://www.patronus.ai/llm-testing) | Application-centric testing, layered objectives, synthetic/real cases, adversarial examples and evaluator explanations. | Use as methodology/background and a possible later specialized evaluator source. No mandatory commercial judge or Patronus account. Any selected external evaluator must pass calibration, budget and evidence-portability requirements. |
| [Hugging Face Evaluate](https://github.com/huggingface/evaluate) | Reusable metrics, comparisons and dataset measurements. Its README recommends the newer, more actively maintained **LightEval** for recent LLM evaluation approaches. | Use Evaluate only where a specific validated metric is helpful. Investigate [LightEval](https://github.com/huggingface/lighteval) for broad task/benchmark adapters. Neither supplies Playpen's profile-specific usability gates by itself. Do not import leaderboard scores into MTT's local rating scale. |
| [Stanford HELM](https://crfm.stanford.edu/helm/) / [official implementation](https://github.com/stanford-crfm/helm) | Holistic, reproducible evaluation with multiple metrics and visible operating conditions. | Already foundational in the main requirements. Preserve multidimensional capability, uncertainty and efficiency, instead of equating one number with universal fitness. A wholesale HELM deployment is optional. |
| [FastChat LLM Judge](https://github.com/lm-sys/FastChat/tree/main/fastchat/llm_judge) | MT-Bench open-ended multi-turn questions, judge prompts and agreement tooling. | Useful optional writing/conversation assessment and judge-calibration reference. It does not test actual Playpen gateway success merely by grading a convincing response. Reference prompts/judges and biases remain explicit; no compulsory paid judge. |

## 3. Projects discovered through those references

These decisions are an engineering shortlist, not results of a head-to-head installation or runtime benchmark.

| Project / primary source | Useful role | Priority / boundary |
|---|---|---|
| [Pydantic Evals](https://pydantic.dev/docs/ai/evals/evals/) | Python cases, custom deterministic checks, optional rubric judges, reports and trajectory/span assessment. | Trial first alongside DeepEval. Assess how its canonical evidence/telemetry representation maps to existing Playpen records. |
| [DeepEval](https://github.com/confident-ai/deepeval) | Agent metric taxonomy and Python regression integration. | Trial first; verify actual scorer mode and dependencies rather than assuming a metric is deterministic or free. The README documents automatic `.env` loading; an adapter must preserve Playpen's vault policy and disable unintended loading. |
| [Promptfoo](https://www.promptfoo.dev/docs/intro/) | Configurable provider/prompt comparisons, assertions and matrix views. | Good optional comparison/import/export adapter. Calls must still exercise Playpen's actual agent for system qualification; direct prompts are a separate arm. |
| [Inspect AI](https://inspect.aisi.org.uk/) | Composable tasks, agents, tools, scorers, logs, limits and sandboxed evaluations. | Strong candidate for a later deeper qualification/coding environment. Preserve the existing Agent through a bridge rather than silently replacing it with a different solver. |
| [Ragas metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/) | Retrieval precision/recall, faithfulness, relevance, and agent/tool-use metrics. | Optional RAG/research pack. Separate retriever/index quality, grounded answer quality and complete task success. Freeze judged/embedding/deterministic metric modes and their costs. |
| [LightEval](https://github.com/huggingface/lighteval) | Broad LLM benchmark tasks, configurable metrics and per-sample results across backends. | Optional broad capability survey, after Playpen eligibility checks. Exact benchmark conditions and context must remain attached to imported scores. |
| [AutoEvals](https://github.com/braintrustdata/autoevals) | Reusable output-scoring functions and evaluator patterns. | Consider a small pinned metric adapter when needed. Output quality does not establish an executed tool trajectory. |
| [DSPy](https://github.com/stanfordnlp/dspy) | Programming/optimizing language-model pipelines. | Optimization lane, not an independent competence certificate. Tuned pipelines get new configuration identities and must be evaluated on held-out cases. |
| [Instructor](https://github.com/567-labs/instructor) and [Guidance](https://github.com/guidance-ai/guidance) | Structured-generation and output-control techniques. | Candidate remediation arms for format failures, not objective scorers. Preserve added retries, supported backend restrictions and token/call costs; a repaired configuration cannot inherit an old raw-model score. |
| [Langtrace](https://github.com/Scale3-Labs/langtrace), [Langfuse](https://github.com/langfuse/langfuse), [Opik](https://github.com/comet-ml/opik) | Trace/evaluation inspection and observability/experiment workflows. | Optional telemetry/report integration after measuring a real gap in Playpen's evidence UI. Avoid three overlapping trace stores and mandatory hosted services. Verify each exact version's licensing, deployment and retention terms. |

### Proposed adoption order

1. Keep **MTT's profiles, attribution, evidence, qualification and calibration** as the portable core.
2. Run a small **Pydantic Evals versus DeepEval versus existing deterministic checks** adapter trial using saved/synthetic traces before selecting a dependency. This is not a reason to rebuild all existing tooling.
3. Add Promptfoo comparison interchange only if it reduces practical work; add Inspect AI when isolation or richer task environments justify it.
4. Add Ragas for actual retrieval research, LightEval for broad benchmark import, and optional judge/observability tooling for demonstrated needs.

The shortlist is based on documented fit, not measured speed, correctness or cost in Playpen. Library licensing and local installation do not imply zero judge/model calls, no telemetry, or no optional hosted charges. Check these in the exact pinned release before adoption.

## 4. What the application-fit report must look like

Each model/configuration should have a compact matrix:

| Application | Status | Measured strength | Limiting behavior | Operating point | Qualified alternative |
|---|---|---|---|---|---|
| Extraction | qualified/provisional/failed/untested | Field accuracy, schema and missing-value handling | Fabrication, omissions or malformed output | Context/input type/route | Only if the alternative has relevant current evidence |
| Summarization | same status vocabulary | Faithfulness, coverage and constraint satisfaction | Unsupported claims or omitted qualifications | Document/domain/length | Same matched application tests |
| Writing | same | Meaning/style/constraint utility | Factual/style/consistency weakness | Rubric and judge/human provenance | Same blinded rubric and examples |
| Coding | same | Executable fixes and verified artifacts | Failing tests or unsupported claims | Sandbox/language/project type | Matching coding pack |
| Calculator/data work | same | Correct operands, equations and result use | Category/sign/unit errors or unfinished reports | Actual tools and budget | Matching mathematical workflow |
| Research/RAG | same | Source relevance, grounded claims and conflicts | Retrieval misses or fabricated citations | Frozen/live corpus and retrieval setup | Same corpus and evidence requirements |
| Autonomous tools | same | Complete bounded workflows and recovery | Repeated calls, mixed protocols or no final answer | Exact controller/adapter/tool set | Same workflow contract |

Every cell links to counts, uncertainty, coverage, traces and profile version. Empty cells say untested; they are not implicit weaknesses. A factual extraction model need not be rejected because it is poor at creative writing. A fluent writer cannot automatically be promoted to an autonomous agent.

Default selection rules:

- Filter by necessary capability, qualification, context, route, response deadline, budget and any deployment restriction.
- Compare remaining models on matched application cases. Report paired performance differences with uncertainty; do not infer superiority solely from two separate point estimates.
- Present quality/cost/latency trade-offs. Only claim a single best choice after the user specifies the preference or service-level objective.
- If no model qualifies, say so and show the cheapest informative next test or an explicitly experimental fallback. Do not recommend a failed candidate as qualified because it is the best of a weak cohort.
- A recommendation combining multiple models must include an end-to-end test of the handoff and final outcome. Individual capability cards alone do not prove the combined workflow.

## 5. How our completed testing informs these additions

The full study inventory remains in [section 3 of the MTT requirements](mtt-model-testing-tool-requirements.md). The new references do not replace or rescore it.

| Our evidence | What it establishes for MTT | What remains unestablished |
|---|---|---|
| Historical GPT-OSS-20B correct direct B01 answers but repeated tool-arm provider rejections | Direct-answer capability and route compatibility require separate decisions. | That the same configuration works after an interface change without retesting. |
| Nov. 19 Groq 6/6 diagnostics, B01 0/5, B04 5/5 | A narrow successful skill can coexist with an unsuitable longer autonomous workflow. | Broad autonomous-agent qualification or generic research/writing excellence. |
| Local Qwen2.5 5/6 diagnostics but failed longer pilot tasks | Supported one-operation handoffs are useful evidence; mixed output and longer-task evidence need separate checks. | That every deployment of this model is useless, or that it is a qualified coder merely because its name includes Coder. |
| Local Qwen3.5 4/6 diagnostics and successful calculations before B01 timeout/looping | Tool/calculator success, task finalization and local time limits are distinct. | Exact causal attribution to model weights versus template/controller/operating point. |
| Real Qalculate integration tests and observed scientific-tool smoke | The calculation engine and some integration paths work. | Every model's ability to formulate the right equation or finish a report. |
| Guided-answer leakage and timeout replay gap | Evaluator/controller integrity must be checked before judging candidates. | Trustworthy qualification from those defective evaluation paths. |

No completed study tested a broad writing, summarization, coding, translation or domain-specialist application pack. Those cells must stay **untested** until representative cases are actually run. MTT must not invent strengths from model branding or a few tool tests.

## 6. Concrete changes to the main specification

- Added the two explicit product decisions: **worth further testing?** and **best-supported applications / alternatives?**
- Added application-specific packs and `FIT-01`–`FIT-06` for strengths, weaknesses, held-out user tasks, qualified replacements and trade-off-aware selection.
- Added `TRIAGE-01`–`TRIAGE-03`: next-test value explained from evidence gaps, finite rescue experiments and public benchmarks used only as external priors.
- Added a bounded framework-adoption trial and required preservation of the actual Playpen execution path.
- Added acceptance tests for preserving useful limited roles, retrieval versus generation attribution, evidence-backed alternatives, adapter fidelity and comparable application recommendations.

## 7. Required integration trial before adopting a framework

The engineering trial must be small and inspectable. It should first run without new model calls by feeding canonical saved/synthetic evidence to the candidate evaluators:

1. A successful read/calculate/final sequence with exact artifacts.
2. Correct grand total but incorrect category subtotal.
3. A named tool in prose with no real execution.
4. One supported explicit JSON envelope versus fenced-envelope-plus-prose and multiple concatenated requests.
5. Successful tool results followed by repeated calls and no final report.
6. An expected failed source followed by a verified fallback.
7. A forced timeout retaining four responses and one pending request.
8. A genuine quota block with no capability observation.
9. Two different valid trajectories reaching the same verified outcome.
10. A fluent unsupported answer and a contract-valid alternative answer.

The trial report must state which scorers are code, model, hybrid or human; their defaults and external calls; reproducibility; agreement with known outcomes; evidence portability; cancellation and partial-run behavior; Windows/Python compatibility; installation/storage footprint; and licensing. Review any automatic `.env` loading, retries, cache use, telemetry/export and model-judge defaults. No account setup, dependency installation or live benchmark run is implied by this reference review.

An evaluator that cannot preserve blocked/incomplete distinctions, or that awards success for tool-name mentions without actual required execution, cannot be MTT's qualification authority. A useful partial metric may still be imported under its own name, mode and limits.
