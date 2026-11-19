# Baseline Finalization and Verification Corrective Plan

Date: 2026-11-19

## Approval status

Do not approve the baseline corrective plan as complete based on the November 18
and November 19 work alone. The implementation mechanics pass focused and full
offline checks, and several live tool paths work, but B01 finalization remains
the primary live blocker.

Evidence source:

- [Independent November 19 verification report](verification-baseline-spec-2026-11-19.md)
- [November 19 case results](studies/2026-11-19-verification-case-results.csv)

No implementation code or runtime configuration is changed by this document.
The baseline-v1 fixture and scorer remain immutable unless a separately approved
versioned rubric and fixture change is published.

## November 19 live verification snapshot

The live case study does not change the design described below. It establishes
the following measured points:

- Groq Qwen3.8 passed D01-D06 and B04, but five-seed B01 produced 0/5 passes
  because repeated calculator calls replaced final reports.
- Qwen3.5 passed D01, D04, D05 and D06 and B04, but B01 timed out after
  successful calculations and repeated calls.
- Qwen2.5 passed five diagnostics and failed B01/B04 for mixed tool-request/
  final-report and missing evidence behavior.
- Timeout replay must consume 57 partial events, including four complete provider
  responses, rather than only the normal interaction list.
- Guided B01 answer leakage and mixed tool protocol feedback remain approval
  blockers.

The [November 19 verification report](verification-baseline-spec-2026-11-19.md)
and [case CSV](studies/2026-11-19-verification-case-results.csv) are evidence
for that snapshot. They are not retroactive baseline qualification.

## Findings to implement

| Priority | Finding | Required corrective behavior |
|---|---|---|
| P0 | Successful tool operations can be followed by repeated calculations instead of a report | Add a bounded finalization phase using verified operation state |
| P0 | Guided B01 feedback leaks target totals | Never place target values or exact missing answers in model-visible feedback |
| P0 | Mixed or ambiguous tool text can be misclassified | Add a distinct malformed mixed-tool-request category and protocol feedback |
| P1 | Timeout replay ignores partial events | Normalize partial response events into the replay evidence envelope |
| P1 | Three arbitrary calculations can appear sufficient | Track named calculation slots and verified evidence, not expression count |
| P1 | Complete profiles and rubric-v2 remain unfinished | Keep partial implementation labeled partial and publish only versioned future baselines |

## Phase 1: Safe task-state and finalization controller

Implement an explicit finalization state machine rather than increasing
calculator repetition limits or unconditionally forcing the next turn to finish.

The controller has two modes:

- **Autonomous:** the model decides when to finish, subject to existing format,
  tool, iteration, timeout and repetition guards.
- **Guided:** Playpen tracks observed evidence and can request a final report
  only after a task-specific observed-state test passes.

Guided and autonomous results remain separate in configuration, execution
identity, reports, exports and live-result labels.

### Observed evidence ledger

Record only verified execution outcomes:

- fixture read succeeded
- fixture read failed or was denied
- calculator call succeeded
- calculator expression and bounded result
- write_artifact succeeded or failed
- primary source failure was observed
- backup and empty results were observed
- final report candidate was accepted or rejected

Do not advance guided state from:

- tool name or arguments alone
- an error or denial result
- model prose describing a tool call
- a final-report field that was not observed
- an expression that is syntactically valid but unrelated to the required
  task calculation

### B01 state rules

For B01, maintain named state slots:

- fixture read
- net-total calculation
- parts category calculation
- service category calculation

Derive the required operation slots from the fixture inside trusted application
code. Do not expose the target values in model-visible feedback.

The finalization check should verify:

- the fixture was read successfully
- each named calculation slot has a successfully executed arithmetic operation
  with the observed fixture values
- the calculated observations are internally consistent
- the final JSON is structurally valid and consistent

An answer with the correct number but no successful supporting operation must not
advance guided state. A successful supporting operation must not be hidden from
the audit trail merely because the model used a later expression.

### Finalization budget

When guided state is complete, enter a separate bounded finalization phase:

- allow one concise structured final-report request
- include an advertised report JSON schema
- do not provide expected fixture answers
- prohibit tool calls in the finalization request if the task state is complete
- permit at most one valid-format correction without a second tool loop
- remain within the existing iteration, token and task deadline budgets
- label any guided pass as guided, not autonomous

The current B01, B02 and B05 baseline-v1 scorers remain authoritative and
unchanged. This phase improves handoff mechanics; it does not repair or inflate
historical baseline-v1 results.

## Phase 2: Structured final reports

Use provider-supported structured output only where actually supported.
Represent unsupported structured output explicitly as unavailable or prompt
enforced, not as native capability.

The common report contract should require:

- no prose outside the JSON object
- no tool-call envelope as the final report
- required task fields
- JSON number versus integer types
- exact evidence fields where required
- explicit unknown/null handling

For B01, include:

- `net_total`
- `valid_orders`
- `duplicate_ids`
- `category_totals.parts`
- `category_totals.service`

Validation feedback must identify missing fields or inconsistent categories
without supplying target amounts.

## Phase 3: Malformed tool-request feedback

Classify and report these cases separately:

- one complete advertised tool JSON object
- tool object plus prose
- multiple tool objects
- unknown tool name
- missing required argument
- invalid argument type or expression
- invented observation
- partial/truncated call

Only the first category may execute through the normal tool gateway.
Mixed, multiple and unknown requests must be rejected without extracted execution.

The recovery response for mixed or ambiguous output should be explicit:

> Return one complete tool object for one advertised tool, without prose or
> multiple calls. No tool was executed.

Do not route malformed tool intent through final-report validation. Preserve the
original bounded/redacted response in the attempt trace.

## Phase 4: Timeout and partial-event replay

Normalize `isolated_attempt.partial_events` into the same replayable evidence
shape as `interactions`:

- `transport_request` from captured request events
- `transport_response` from captured response events
- `request_diagnostic` for request settings and call index
- `response_diagnostic` for response text and finish reason
- `partial` or `incomplete` metadata for an unfinished worker request

Replay must remain read-only:

- no model calls
- no tool calls
- no calculator or fixture execution
- no attempt to synthesize missing responses

Missing usage for an unfinished response remains unknown. The replay report must
distinguish complete recorded responses from absent/incomplete worker responses.

Add a forced-timeout regression that proves:

- partial events are retained
- complete captured responses replay
- an unfinished request is reported as unmatched
- replay does not call a model or tool

## Phase 5: Repetition and history handling

Replace whitespace-removing duplicate keys with conservative syntax
normalization:

- preserve whitespace/token boundaries
- normalize only validated numeric arithmetic
- canonicalize decimals only after the expression passes syntax validation
- never record an invalid expression as a successful prior calculation
- do not infer equivalence solely because two expressions share operands
- treat category subtotal and grand total as distinct operations

Audit history must retain every original tool attempt and outcome. Model-facing
history may be compressed only when the full tool trace remains separately
available.

## Phase 6: Provider/model profile provenance

Complete the partial profile work before claiming reproducibility:

- supported request parameters
- requested value
- effective or confirmed value
- server/default value
- unknown value
- load-profile values where the provider exposes them
- provider/model capability state
- tested settings and route

Capability states must remain separate:

- untested
- advertised by provider
- observed working
- observed failing

Unsupported values must remain unknown. Do not infer an LM Studio GUI preset was
applied unless the load/request API confirms it.

## Phase 7: Rubric and baseline separation

Keep baseline-v1 immutable.

Publish baseline-v2 only after:

- B02/B05 contracts are explicit
- accepted answer aliases are listed
- exact quotation rules are versioned
- source coverage is separate from quotation correctness
- deliberate alternative answers and wrong answers pass the pilot scorer
- baseline-v1 and baseline-v2 reports are never pooled silently

B06 and B07 remain proposals until their manifests, fixtures, scorers and
alternative-answer tests are implemented, frozen and documented.

Use D02-D06 capability diagnostics for narrow live follow-up until those
baselines exist.

## Live verification sequence

Use the following sequence instead of starting a broad sweep:

1. One captured B01 defect, one positive-control model, one seed.
2. Add Qwen2.5 Coder for malformed mixed-tool protocol behavior.
3. Add Qwen3.5 for timeout/partial-replay behavior.
4. Run a small repeated Groq positive-control pilot.
5. Run matched autonomous and guided comparisons only after both contracts are
   recorded separately.
6. Run repeated B01 and B04 controls before adding B02/B05.

All live runs must record:

- exact requested settings
- provider response metadata
- native versus prompt versus textual JSON route
- rejected actions
- successful/failed tool outcomes
- partial events
- usage or unknown usage
- elapsed time
- finalization mode
- strict pass and quality score independently

Quota, timeout, setup, provider rejection and unavailable evidence are outcome
categories, not model correctness.

## Acceptance gates

### Change-level gates

- failed reads, calculations and writes do not advance task state
- guided terminal reports cannot bypass state
- no target value appears in guided model-visible feedback
- one complete advertised tool call is the only executable JSON-call shape
- mixed/multiple/unknown tool output has explicit protocol feedback
- timeout replay consumes complete partial responses
- `1 2` and `12` remain distinct repetition keys
- native error-only handoff does not mark capability working
- fixture-name wrong-name and allowed-name tests pass

### Live gates

- Groq B01 candidate follow-up passes repeatedly before B01 qualification
- Groq B04 remains reproducible under matched settings
- Qwen2.5 malformed tool behavior is improved without silent extraction
- Qwen3.5 timeout evidence replays and remains labeled incomplete
- autonomous and guided runs remain separate
- baseline-v1 score/rubric remains unchanged
- no guided pass is described as improved autonomous behavior

## Remaining work explicitly out of scope

The following completion gaps remain separate from this plan:

- complete inference/load profiles
- supported provider reasoning/load apply/query UI
- profile diff
- rubric-v2
- B06/B07 implementation
- broad live reliability claims
- general web-search or broad task qualification
