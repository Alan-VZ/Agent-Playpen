# Project documentation index

**Start here:** [Executive summary — the story so far](executive-summary.md). A short account of the original concept, problems, implemented changes, key decisions and current limits.

- [Multiple model comparisons](model-comparisons.md): independent model cards, parameter overrides, and matched baseline comparisons.
- [Baseline findings and corrective actions](baseline-failure-findings-and-corrective-actions.md): implementation status, settlement modes, diagnostic evidence, and live-qualification gates.
- [Baseline finalization corrective plan](baseline-finalization-corrective-plan.md): November 19 live findings, phased implementation and acceptance gates for finalization, malformed tool requests, timeout replay, profiles and rubric-v2.
- [MTT assessment and code-enhancement recommendations](mtt-assessment-and-enhancement-recommendations.md): independent assessment of the MTT specification, application-fit scope, framework choices, existing-code reuse and prioritized implementation phases.
- [MTT implementation clarifications](mtt-assessment-implementation-clarifications-2026-11-19.md): timeout, controlled-study import, Quick Screen, guided policy, positive-control and framework-adapter clarification for the existing MTT specification.
- [MTT model-testing requirements](mtt-model-testing-tool-requirements.md): authoritative build specification for source onboarding, autonomous bounded pre-testing, the persistent model database and database-first task selection.
- [MTT implementation assessment](mtt-assessment-and-enhancement-recommendations.md): MVP scope, code reuse, framework trial and deferred qualification work.

- [Issues found and implemented resolutions](issues-and-resolutions.md): complete issue register and evidence boundaries.
- [Universal tool gateway / MCP](universal-tools.md): architecture, setup, direct console, external servers, native calls, status, records and limitations.
- [Calculator](scientific-calculator.md): Qalculate engine, precision, units, graphs and portable package.
- [Creators and sources](credits-and-sources.md): software dependencies, licenses and research inspiration.
- [Universal tool smoke observations](studies/2026-11-17-universal-tools-smoke.md): actual local timeout and Groq native-tool success, with limited inference scope.
- [Baseline workflow](baseline-tests.md), [controlled studies](controlled-study.md), [five-task results](studies/2026-11-17-five-task-matched.md).
- [Local troubleshooting](local-model-troubleshooting.md), [backend setup](backend-setup.md), [testing](testing.md), [live activity](live-activity.md).
- [API inventory and maintenance](keys-costs-maintenance.md), [search reliability](search-reliability.md), [search providers](search-providers.md).

Historical studies are evidence snapshots. New gateway/model calling routes require labeled follow-up evaluation rather than retroactive changes to their results.

- [Four local model failures, November 18](studies/2026-11-18-four-local-models.md): truncation, wrong category subtotal, repeated reads and timeout distinguished.

- [Five models / two tasks with recovery-v1](studies/2026-11-18-five-model-two-task-recovery.md): 0/10 strict passes; transport, loop, evidence and final-report failures distinguished.

- [Capability diagnostics, evidence and replay](diagnostics.md): six focused cases, actual wire capture, source checks, and configuration-first/per-model scheduling.

- [Completed capability diagnostics and protocol follow-ups](studies/2026-11-18-capability-diagnostics.md): 36 cases plus a one-request serialization probe, separate settings/provenance and machine-readable evidence.
