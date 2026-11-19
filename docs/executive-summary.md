# Agent Playpen — the story so far

**Updated November 19, 2026 · Start here · About four minutes to read**

Agent Playpen began as a place to experiment with AI agents. It is growing into a way to discover which models and tools can reliably do a particular job—and keep that knowledge for next time.

The central lesson: **a model giving a good answer and an agent completing a job are different achievements.** Playpen now tests the whole journey: connecting, following instructions, using tools, checking evidence and delivering a usable result.

## How the project evolved

| Step | What we wanted or discovered | What changed |
|---|---|---|
| **1. An agent playground** | Try local and cloud models, planners and tools without building a separate application for each combination. | A modular Python agent framework and web workspace. [Project introduction](../README.md#why-this-project-exists) |
| **2. Fair comparisons** | Impressive demonstrations were not enough. We needed the same repeatable work for each model or team. | Five selectable baseline tasks, repeat runs, shared inputs and comparison reports. [Baseline guide](baseline-tests.md) |
| **3. Easier setup and operation** | Keys, model loading, settings and unclear run feedback made testing frustrating. | Credential inventory and checks, model selection and runtime preparation, editable model configurations, progress and evidence views. [Maintenance](maintenance-screen.md) · [Model comparisons](model-comparisons.md) |
| **4. Investigate the failures** | Many runs failed, but for different reasons: timeouts, invalid tool arguments, repeated actions, provider limits or an unusable final response. Some scoring rules also rejected equivalent wording. | Focused diagnostics, captured interactions and failure-specific corrective work. [Findings and actions](baseline-failure-findings-and-corrective-actions.md) |
| **5. Give models dependable tools** | Correct arithmetic did not guarantee correct tool use—or a correct final report. Models also spoke different tool-call formats. | A Qalculate scientific calculator and a shared tool gateway, with MCP support, validation and execution records. [Calculator](scientific-calculator.md) · [Universal tools](universal-tools.md) |
| **6. Test once, reuse what we learn** | Repeatedly trying unsuitable configurations wastes time. A model that struggles with one job may still be useful for another. | MTT: discover a source's models, screen them within policy, save the evidence locally and later choose candidates from that database. Foundations are implemented; autonomous acceptance and full qualification remain unfinished. [MTT requirements](mtt-model-testing-tool-requirements.md) |

## What the evaluations taught us

One matched study scheduled **1,200 cases**. It attempted 801 and skipped 399 because of quota restrictions. The selected local configurations earned no strict tool-assisted baseline passes in that study, while some produced useful direct answers. Some Groq configurations performed better; OpenRouter's quota prevented a comparable conclusion for its selected models. [Study results and limitations](studies/2026-11-17-five-task-matched.md)

That evidence changed our approach. A failed run can point to the model, its settings, the provider, the interface, the tool, the time allowance or the evaluator. **We need to identify the failing stage before rejecting a model.** Results describe the tested configuration and conditions; they are not a verdict on every local model or an entire provider.

## Decisions that guide the application

- **Let models interpret; let dependable software calculate.** The calculator handles numerical work, while the model must still form the right expression and use the result correctly. PAL research helped motivate this division of work.
- **Use a common tool interface.** The universal control-plane gateway and MCP provide consistent tool access and records. They help integration; they do not guarantee that every model will choose or use a tool correctly.
- **Select for the job.** MTT should retain strengths, weaknesses and untested areas, rather than label a model universally good or bad. A single score must not override a missing essential skill.
- **Keep screening separate from qualification.** A quick diagnostic pass is provisional. Reliable unattended use needs sufficient repeated evidence. Application test passes are also separate from live model success.
- **Preserve the evidence.** Provider outages and quotas are operational blocks, not proof of poor capability. Changed interfaces or scoring rules need new, labeled evaluations rather than rewritten historical results.

The [creators and sources](credits-and-sources.md) record acknowledges Qalculate, MCP, the universal agent control plane, PAL and other software and research behind these choices. The [evaluation reference review](mtt-reference-review-and-application-fit.md) explains how outside frameworks inform MTT.

## Where we are now

**Working foundations:** multi-model configuration, repeatable baselines, diagnostic evidence, credential maintenance, calculator/tool integration and MTT's local database, APIs and dashboard.

**Latest independent check:** 573 application tests passed, nine were skipped, and five live pages each delivered one shared menu. Additional offline probes still found campaign accounting and recovery defects: multiple valid attempts can exceed the recorded allowance, and an unresolved attempt can be dispatched again after restart. These findings concern MTT orchestration, not model capability. [Latest verification](verification-mtt-reservations-and-navigation-2026-11-19.md)

**Deferred for later:** finish campaign accounting and recovery, reconcile time reservations after completed work, and verify a complete bounded live screen. Broader capability profiles, calibrated rankings and full model qualification also remain open. The application should not yet be described as an approved unattended model-qualification service. [To-do list](../todo.md)

## Keeping this overview useful

Update this page when a milestone changes what the user can do or what we know. Keep the problem, decision, result and one useful detail link; put logs, implementation notes and individual test runs in the linked records. Dates and test counts above are snapshots, not permanent status indicators.
