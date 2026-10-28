# Concept: Bayesian aggregation for multi-agent consensus

Status: proposed design; no consensus engine, configuration keys, or APIs described below are implemented by this documentation change.

## Purpose

For tasks with a configurable number of agents, initially evaluate groups of 2 through 10 agents. Combine independently produced proposals, identify the disagreement that matters, and spend the next tool call or review on resolving it. The aggregation formulas do not impose a four-agent limit; 10 is an initial evaluation target, not a demonstrated capacity or mathematical ceiling. The objective is a verified solution within a budget. Unanimity is optional; an unresolved result is valid.

Bayesian aggregation combines information through explicit probabilistic assumptions. It can represent uncertainty and incorporate evidence as it arrives. It does not make a majority correct, turn self-reported confidence into reliability, or guarantee fewer tokens or rounds.

The motivating failure case is three agents sharing an incorrect assumption while a fourth finds a counterexample. The coordinator must preserve that counterexample and allow the minority to change the result.

## Existing integration points

| Existing component | Current behavior | Proposed use |
| --- | --- | --- |
| [`AgentManager`](../advanced/multi_agent/manager.py) | Registers agents, routes tasks, and collects text responses; broadcast runs sequentially | Collect independent proposals and dispatch targeted reviews |
| [`MessageBus`](../advanced/multi_agent/message_bus.py) | Async queue-based pub/sub transport | Carry versioned proposal, evidence, and decision messages |
| [`Evaluator`](../advanced/evaluator.py) | LLM judge scores relevance, accuracy, completeness, and format | Optional auxiliary assessment, calibrated against external outcomes |
| [`Tracer`](../debugging/tracer.py) | Records execution events; observation text is truncated | Link decisions to separately persisted evidence artifacts |
| [Example orchestrator](../examples/multi_agent/orchestrator.py) | Researcher-to-writer pipeline | Example location for a future consensus demonstration |

A future `ConsensusCoordinator` could live beside the manager. Keep transport, probabilistic aggregation, evidence verification, and stopping policy separate. These are proposed responsibilities, not existing classes or methods.

## What numbers should represent

Use measurements or assessments with a shared meaning: estimated runtime, probability of a named hypothesis, or a distribution over a fixed candidate set. Raw token IDs are vocabulary labels; their differences and averages do not measure agreement. Token counts measure cost. Embeddings may help retrieve or group related proposals, but semantic proximity does not establish logical consistency or truth.

For categorical problems, define mutually exclusive hypotheses, including an `other` option when the candidate set may be incomplete. For code or plans, retain separate candidate artifacts and versions; do not average their text. Nonexclusive requirements should be tracked as separate claims.

### Proposed proposal format

This illustrative JSON describes one agent's complete distribution over a shared candidate set. It is not an accepted runtime input today.

```json
{
  "task_id": "task-17",
  "round": 1,
  "agent_id": "reviewer-4",
  "candidate_set_version": 1,
  "candidate_probabilities": {"patch-a": 0.15, "patch-b": 0.75, "other": 0.10},
  "candidate_versions": {"patch-a": "sha-a", "patch-b": "sha-b"},
  "evidence_ids": ["test-run-42"],
  "depends_on_proposals": [],
  "assumptions": ["The documented empty-input contract applies"],
  "verification_request": "Run the empty-input regression on both patches",
  "abstain": false
}
```

Validate finite probabilities in [0, 1], a sum of one within tolerance, unique message IDs, known candidates, and matching versions. An abstention supplies no probability distribution. Malformed or missing output is missing information, not a neutral vote. Persist evidence with its source, exact artifact version, retrieval or execution time, relevant excerpt or test result, and verification status. A changed patch requires fresh checks.

### Structured evidence with freedom of approach

Standardize the handoff between agents, while leaving research, tools, decomposition, and solution generation open. "Show your work" means a concise, auditable justification and reproducible evidence; it does not require a full internal reasoning transcript or a prescribed sequence of thoughts. A polished explanation remains a claim until checked.

Use two layers: a small required envelope for routing and comparison, plus task-specific evidence and optional free-form notes. Candidate probabilities are optional when an agent cannot provide a meaningful forecast; an evidence-only report must not be converted into a fabricated probability or counted as a vote.

| Field | Purpose |
| --- | --- |
| Report ID, task ID, agent ID, round | Identify and deduplicate reports |
| Claim ID and candidate/artifact version | Establish exactly what is being assessed |
| Position: support, oppose, or abstain | Distinguish disagreement from missing information |
| Concise justification | Explain the connection between evidence and claim |
| Evidence references | Link sources, calculations, test artifacts, and observations |
| Assumptions and limitations | Expose conditions that could invalidate the conclusion |
| Verification request | Specify a useful check or what would change the assessment |
| Dependencies and superseded report IDs | Track inherited information and revisions |
| Optional forecast and free-form notes | Preserve uncertainty estimates and ideas outside the standard fields |

The earlier proposal JSON illustrates forecasts over candidates; a claim report is a complementary proposed message type. A verification response should reference the claim, evidence, and version checked; give a result of confirmed, contradicted, or inconclusive; and link the resulting artifact. An LLM review and an executed test should retain distinct verifier types and limitations. Confirmation establishes the scope of that check, not universal correctness.

Do not require a URL for mathematical reasoning: an explicit derivation or counterexample can be checkable evidence. Do not require all agents to use the same method or provide the same amount of detail. Permit agents to add a new candidate, challenge the task framing, or report that none of the current candidates fits. Version the candidate set and refresh affected assessments before pooling across it.

Keep required fields short, provide examples, and allow a bounded format-repair attempt. Preserve invalid submissions and useful artifacts, mark them unparsed, and exclude them from numerical aggregation until validated. Report schema failures separately from task errors. Long forms can consume context, encourage invented evidence, or exclude unusual solutions; require only fields needed for the current task. Comparison should operate on claims and checks rather than writing style.

## Scaling coordination to 10 agents

Separate the number of registered participants from the number running at once. A future coordinator should configure group size, concurrency, reviewer assignments, per-agent timeouts, and total budgets independently. The existing manager's broadcast is sequential; parallel execution would be a separate implementation change with backend rate-limit and resource handling.

For N reports over K common candidates, a linear opinion pool takes O(NK) arithmetic. Review traffic and context are more likely bottlenecks: every agent reviewing every other agent produces N(N-1) directed review assignments per round, or 90 at N=10. More agents do not necessarily improve accuracy or reduce latency, especially when they share errors.

Proposed scheduling policy:

1. Collect independent first-round reports into a shared evidence ledger. Missing or timed-out agents remain missing, not negative votes; record the participating set and check any required specialist coverage before accepting a result.
2. Group reports by candidate and disputed claim for navigation. Preserve minority evidence and distinct counterexamples even when summarizing duplicate reports.
3. Assign targeted reviews by relevant expertise and provenance. A baseline of at most two peer reviewers per proposal creates at most 2N initial assignments (20 for 10 agents), rather than 90. This assignment budget is not an accuracy guarantee; material unresolved objections may require extra checks or an unresolved result.
4. Route reviewers the necessary claim, artifact, assumptions, and evidence references instead of replaying every conversation. Use a reproducible tool check where feasible and retain access to original evidence behind summaries.
5. Recompute the aggregate after new verified evidence. Avoid broadcasting another full round when one targeted check can resolve the decision.

For example, a 10-agent roster could contain four proposal generators, three domain reviewers, two verification workers, and one coordinator. Roles may rotate. A worker executing a test contributes a check, not an extra independent opinion about its own result. A coordinator without a substantive independent assessment does not cast a vote. Ten agents therefore need not mean ten probability distributions; normalize pooling weights over eligible forecasts and record their actual coverage.

If review is hierarchical, preserve source dependencies through every level. A subgroup summary and its underlying reports are not separate evidence. Shared sources or models should not gain confidence merely because additional agents repeat them. Acceptance remains tied to task criteria, checked evidence, and declared risk thresholds rather than a universal vote count.

## Two distinct aggregation mechanisms

### 1. Bayesian updating from evidence

For hypotheses H and newly verified evidence E:

```text
P(H | E) = P(E | H) P(H) / sum_h[P(E | h) P(h)]
```

The likelihood must describe how probable the observation is under each hypothesis. An agent's reported probability of H is not itself P(E | H). Obtain likelihood assumptions from a specified generative model or measured verifier performance, document them, and examine sensitivity when they are uncertain.

For illustration only, take two hypotheses A and B with equal prior probability. A reproducible test fails. Suppose the specified model gives P(failure | A) = 0.1 and P(failure | B) = 0.8. Then P(B | failure) = 0.8 / (0.1 + 0.8), approximately 0.889. Those likelihoods are invented for the example, not recommended defaults. A hard requirement can also disqualify a candidate directly without assigning a synthetic probability to a deterministic failure.

Multiplying likelihoods for several observations requires conditional independence or an explicit joint likelihood. Several agents citing the same failing test contribute one observation, not several independent failures. Rephrased reports and later rounds do not create fresh evidence.

### 2. Reliability-weighted opinion pooling

When likelihoods are unavailable, a transparent baseline is a linear pool:

```text
p_pool(H) = sum_i[w_i p_i(H)], with w_i >= 0 and sum_i[w_i] = 1
```

This is a pooled opinion, not automatically a Bayesian posterior. Historical calibration, task competence, and source dependence should inform its weights. If no calibration data exists, disclose that fact and compare an equal-weight baseline.

For example, three agents assign B probability 0.2 and a fourth assigns 0.9. Equal-weight pooling gives B probability 0.375. That describes their combined opinion; it does not invalidate the fourth agent's failing test. Verification must remain able to override the pooled preference.

Agents using the same model, source, or upstream answer can have correlated errors. Track shared provenance and consider pooling within evidence families before pooling across families. This is a dependence-management heuristic, not an independence guarantee. New model providers alone do not establish independence. Do not multiply agent posteriors: this can count shared evidence and common priors repeatedly.

## Learning reliability without rewarding conformity

A simple proposed model for independently adjudicated binary correctness is:

```text
r_i ~ Beta(alpha_i, beta_i)
E[r_i] = alpha_i / (alpha_i + beta_i)
alpha_i <- alpha_i + independently verified successes
beta_i  <- beta_i  + independently verified failures
```

Use a declared prior, such as Beta(1, 1), and retain uncertainty and sample counts. This model assumes comparable Bernoulli outcomes; it is a limited approximation to competence. Track domains separately when enough data exists. Delayed or unknown outcomes receive no update. An abstention is not a failure. Record one adjudicated outcome per evaluation unit rather than repeatedly counting the same task each round.

Never define success as agreement with the final group answer, or failure as slowing consensus. Those rules train conformity. Evaluate probability forecasts with proper scoring rules such as Brier score or log loss and calibration plots; binary hit rate alone does not calibrate probability reports. A decayed Beta count may accommodate drift as a heuristic but is not the same stationary conjugate model.

## Bounded coordination loop

1. Define the task's acceptance criteria, shared candidates or claims, independent first-round prompts, and token/tool/time budgets.
2. Collect initial proposals without exposing peers' answers. Validate their structure and capture provenance.
3. Separate candidate preference from verified evidence. Apply each new observation once and calculate the declared pool or posterior.
4. Identify decision-relevant conflicts, especially a counterexample to a leading candidate. With small groups, IQR or MAD thresholds are unstable; increasing to 10 agents still does not make statistical distance establish who is correct. Text and categorical proposals need claim comparison, not numeric outlier arithmetic.
5. Request the cheapest useful discriminating check: reproduce a test, inspect a primary source, check a constraint, or ask a reviewer to examine a specific counterexample. Selection by expected information gain or value of information is a later extension requiring estimated check costs and outcomes.
6. Update using the new evidence and retain proposal dependencies. Revised opinions based on the same observation are not additional independent observations.
7. Accept only when task criteria and the chosen decision policy are satisfied. Otherwise continue within budget, or return `unresolved` with remaining conflicts and the next useful check. Reaching the budget bounds execution; it does not guarantee consensus or correctness.

Possible decision states are `accepted`, `needs_verification`, and `unresolved`. Thresholds must be calibrated for the task and error costs. A high pooled probability or several stable rounds cannot override a failing required test or an unresolved material counterexample.

### Protecting the correct outlier

Do not inject the majority answer as a "strong prior fact" or penalize an agent merely for dissent. Tool use, response length, entropy, and predicting one's own minority status do not independently establish accuracy. Unique evidence is a reason to investigate, not an automatic reliability boost.

Suggested concise review prompts:

> Challenger: State the disputed claim, the candidate version, and the smallest reproducible test or primary-source excerpt that would distinguish the alternatives. Include evidence references and assumptions.

> Reviewer: Check this counterexample independently. Report whether it reproduces, which requirement it affects, and what would change your assessment. You may retain either candidate or abstain.

For example, three reviewers prefer patch A, but the fourth supplies an empty-input failure. The coordinator reproduces the failure against A's exact version, checks the requirement, and rejects or requests a revision of A if the failure violates it. It preserves the minority report regardless of the original voting weights. A reproducible check is useful even if the challenger lacks unique tool observations; that condition must not gate review.

Bayesian Truth Serum is a distinct peer-prediction mechanism with its own assumptions. It is not implemented by this proposal, and asking agents to predict the majority does not by itself deliver its guarantees.

## Relationship to other methods

| Method | Role and distinction |
| --- | --- |
| Bayesian model averaging (BMA) | Mixes model predictive distributions using posterior model probabilities under a specified model/prior setup; reliability-weighted agent voting is not automatically BMA |
| Predictive stacking | Learns mixture weights to optimize predictive performance, commonly using held-out or cross-validation predictions; weights are not posterior model probabilities |
| Sensor fusion | Combines observations through measurement and noise models; provides a useful analogy when agent observations have defensible likelihoods |
| Preference aggregation | Combines beliefs and potentially utilities; factual correctness and stakeholder preferences require separate decision rules |
| Federated Bayesian learning | Aggregates distributions or parameters from locally trained models; this proposal coordinates inference-time reports and does not train or merge model weights |
| Crowdsourced label models | Infer labels and annotator reliability, sometimes including community structure; relevant to future modeling of agent-specific and shared errors |
| Kalman filtering | Appropriate for continuous state estimation with specified dynamics and measurement errors; raw token IDs and arbitrary prose lack that measurement scale |

## Implementation outline and evaluation

A future implementation would add a schema validator, evidence ledger, aggregation strategies, coordinator policy, and example. The ledger should deduplicate observations and track dependencies, candidate versions, verification outcomes, and decisions. Store full evidence separately: current tracer observations are truncated, so a trace alone cannot serve as the complete evidence ledger.

The current evaluator's malformed-JSON fallback returns scores of 5. A future adapter must flag that assessment as invalid rather than count it as evidence. LLM judge scores require external calibration; the average of format, relevance, completeness, and accuracy is not a probability of correctness. Log concise rationales and reproducible evidence rather than requiring private reasoning traces.

Compare majority vote, equal-weight pooling, calibrated pooling, and the proposed evidence-checking loop on tasks with known outcomes. Include numerical questions, factual claims, and executable code cases. Hold calibration data apart from evaluation data. Include shared-source errors, a correct minority, unanimous wrong answers, agent abstentions, invalid JSON, duplicated evidence, stale patch checks, ties, and budget exhaustion.

Evaluate group sizes 2, 4, 6, 8, and 10, including a single correct dissenter among nine incorrect reports. Compare compact structured reports, free-form reports, and structured reports with optional notes using matched models, tools, tasks, and independent repeated runs. Count any extraction or format-repair calls in cost and latency. Compare both a fixed total task budget and a fixed per-agent budget: otherwise apparent gains may simply come from more compute. Record report validity, verification success, candidate diversity, participating-agent coverage, review assignments, and correct-minority recovery alongside task accuracy. Keep scoring independent of report format so a neat schema is not rewarded as correctness. The hybrid reporting format is a proposed default to test, not a proven improvement.

Measure final correctness, false acceptance, Brier score or log loss where applicable, calibration, correct-minority recovery, unresolved rate and coverage, latency, token use, and tool cost. Report accuracy and cost together. Claims of 30-50% token savings, convergence in two or three rounds, or guaranteed truth require evidence and are not promises of this design.

## Background reading

These sources describe related research, not validation of this proposed Agent Playpen design:

- Yuling Yao, [Bayesian Aggregation](https://arxiv.org/abs/1912.11218): BMA and predictive stacking.
- Prateek Tandon, [Bayesian Aggregation](https://prateektandon.com/bayesian-aggregation/): noisy sensor observations and robotics applications.
- Fischer et al., [Federated Bayesian Deep Learning](https://arxiv.org/abs/2403.15263): aggregation strategies for distributed Bayesian models.

The broader preference-aggregation and community label-aggregation literature may inform later extensions. Their assumptions should be checked before transferring guarantees to a small group of interacting LLM agents.
