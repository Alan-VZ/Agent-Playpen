# Controlled B01 diagnostic study

Run the matched two-arm comparison from the repository root:

```powershell
.venv\Scripts\python.exe -u -m benchmarks.controlled --plan benchmarks/configs/controlled-b01-12-models.json --output controlled-results/<32-character-hex-study-id>
```

The fixed manifest schedules 240 cases: 12 models across LM Studio, OpenRouter and Groq, two arms, five B01 fixture seeds, and two rounds. The same four model IDs per provider repeat in round two. Arm order alternates to reduce ordering effects. Temperature is zero; inference has a shared 180-second per-case deadline, ten ReAct iterations, and a 2,048-token response limit. Cloud request starts are spaced by four seconds. No paid OpenRouter models or model substitutions are permitted.

Arm A supplies the actual input document directly without tools. Its answer checks diagnose arithmetic and instruction following, but it can never count as a strict baseline pass. Arm B uses the production ReAct agent, real read_fixture/calculator tools and unchanged independent scorer. Native tool-calling arm C is deferred until A/B evidence is available.

Open `/controlled-tests/<study-id>` on the local dashboard for progress, current model/seed/arm, outcome tables, stop control and HTML/CSV/JSON exports. All processed cases appear in the denominator, with provider quota and other unavailable outcomes labeled separately. A provider rejection is not evidence of incorrect arithmetic. If OpenRouter explicitly reports daily free-request exhaustion, remaining OpenRouter cases are marked unavailable without issuing more requests. Transient or model-specific 429 responses remain individual rate-limit outcomes.

Every case is checkpointed in study.json; diagnostic JSONL files preserve bounded, redacted messages, response text, finish reasons, usage, reported model identity, and safe provider error details. They contain task data and generated text and remain local under the git-ignored controlled-results directory. Keys and headers are excluded. Inspect or delete these local diagnostics according to your retention needs.

Use `--resume` with the identical manifest and output directory to continue missing cases. Finished cases are preserved, including unavailable outcomes. Resume clears an explicit STOP marker. Changes to source fingerprint, source commit or plan identity require a new study. Each case gets a fresh process and conversation; provider-side caches are uncontrolled. The CLI snapshots the loaded LM Studio model once, then attempts to restore it on exit; restoration.json records success or the need for verification. Catalog reads occur for deliberate model preparation/verification, not background inventory polling.
