# ReAct vs. Chain-of-Thought — Comparison

|Dimension | ReAct | Chain-of-Thought |
|----------|-------|------------------|
|Best for | Tool-heavy tasks | Reasoning-heavy tasks  |
|Latency | Lower (interleaved) | Higher (full chain first) |
|Transparency ||High (step-by-step) | Medium (chain then act) |
|Tool calls | Each iteration | After full plan |
|Error recovery | Per-step | Replanning needed | 
