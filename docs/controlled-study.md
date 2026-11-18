# Controlled baseline diagnostic studies

The full five-task manifest is `benchmarks/configs/controlled-five-tasks-12-models.json`. It schedules **1,200 cases**: the same twelve models, B01–B05, five seeds, two arms and two rounds. Use that path in the command below for the full suite. The B01-only manifest remains available for a 240-case comparison.

Only free local `read_fixture`, bounded `calculator` and isolated `write_artifact` tools are allowed, automatically selected per task. Frozen research sources do not use a live search API. The strict B scorer and fixtures are unchanged. A scores answer fields only: it excludes input-read evidence, report creation and actual fault-recovery execution. In A, B03 does not request a report write and B04 explicitly asks for the recovery result from supplied source snapshots. These exclusions do not apply to B.

Cloud models and task types are interleaved in a fixed rotating order to spread scarce free quota across the matrix. Local cases remain grouped by model to avoid repeated unload/load cycles. Arm order is reversed by matched seed between rounds. B02/B03/B05 use identical frozen source content across seeds, so those seeds are repeated trials rather than independently varied problems. A quota rejection or timeout cannot establish model correctness or incorrectness. The analysis should compare task-specific answer checks and calculator usage, without treating optional tool-use correlations as proof of a causal benefit.

Run the matched two-arm comparison from the repository root:

```powershell
.venv\Scripts\python.exe -u -m benchmarks.controlled --plan benchmarks/configs/controlled-b01-12-models.json --output controlled-results/<32-character-hex-study-id>
```

The fixed manifest schedules 240 cases: 12 models across LM Studio, OpenRouter and Groq, two arms, five B01 fixture seeds, and two rounds. The same four model IDs per provider repeat in round two. Arm order alternates to reduce ordering effects. Temperature is zero; inference has a shared 180-second per-case deadline, ten ReAct iterations, and a 2,048-token response limit. Cloud request starts are spaced by four seconds. No paid OpenRouter models or model substitutions are permitted.

Arm A supplies the actual input document directly without tools. Its answer checks diagnose arithmetic and instruction following, but it can never count as a strict baseline pass. Arm B uses the production ReAct agent, real read_fixture/calculator tools and unchanged independent scorer. Native tool-calling arm C is deferred until A/B evidence is available.

Open `/controlled-tests/<study-id>` on the local dashboard for progress, current model/seed/arm, outcome tables, stop control and HTML/CSV/JSON exports. All processed cases appear in the denominator, with provider quota and other unavailable outcomes labeled separately. A provider rejection is not evidence of incorrect arithmetic. If OpenRouter explicitly reports daily free-request exhaustion, remaining OpenRouter cases are marked unavailable without issuing more requests. Transient or model-specific 429 responses remain individual rate-limit outcomes.

Every case is checkpointed in study.json; diagnostic JSONL files preserve bounded, redacted messages, response text, finish reasons, usage, reported model identity, and safe provider error details. They contain task data and generated text and remain local under the git-ignored controlled-results directory. Keys and headers are excluded. Inspect or delete these local diagnostics according to your retention needs.

Use `--resume` with the identical manifest and output directory to continue missing cases. Finished cases are preserved, including unavailable outcomes. Resume clears an explicit STOP marker. Changes to source fingerprint, source commit or plan identity require a new study. Each case gets a fresh process and conversation; provider-side caches are uncontrolled. The CLI snapshots the loaded LM Studio model once, then attempts to restore it on exit; restoration.json records success or the need for verification. Catalog reads occur for deliberate model preparation/verification, not background inventory polling.


## November 17 integration update

All selected agent tools now execute through the shared Universal Agent Control Plane gateway. The [universal tool guide](universal-tools.md) documents typed contracts, readiness, the direct console, native/prompt model adapters, MCP exposure/connections, execution records, replay and timeout limits. The [issue register](issues-and-resolutions.md) distinguishes observed problems, implemented resolutions and remaining limits; [credits and sources](credits-and-sources.md) acknowledges the upstream creators. Historical study outputs and baseline-v1 scoring remain unchanged. A successful tool operation does not establish final-answer faithfulness or general model reliability.
