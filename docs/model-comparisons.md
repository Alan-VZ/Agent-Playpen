# Editing and comparing multiple models

The workspace supports 1–10 independent model configurations. Set **Number of models** or click **Add model**. Every model has its own visible card, model chooser, provider, endpoint, planner, tool-calling mode, iteration limit, temperature, output-token limit, tools, allowed directories and search provider. Model 1 uses the same card layout as subsequent models. Additional cards have a Remove model button. Reducing and increasing the count preserves retained slot settings; explicitly removing a slot removes that configuration. Changing another model or the active LM Studio model does not replace an explicitly selected slot.

The Task box is shared: **Run Agent** sends that same task independently to each selected configuration. Slot-specific parameters override the main defaults; older saved slots without overrides inherit those defaults. Models on one local server execute under the existing server coordination; provider credentials remain in the credential manager and are not copied into cards or comparison URLs. Unspecified provider sampling/reasoning/load settings remain server-controlled; these cards expose supported Playpen parameters, not every LM Studio desktop setting.

For baseline comparisons, select the task checkboxes and load the selected tasks, then run, or open the comparison page. Each workspace model becomes a **separate single-agent comparison configuration**, not a member of one collaborating team. All receive the same selected tasks, repetitions and fixture seeds. Each retains its own temperature, tool-calling mode, maximum iterations and output-token budget. The browser defaults to 210 seconds per task. Required baseline tools and ReAct are automatic. Custom workspace tools and filesystem/search settings do not replace the frozen baseline tools/fixtures.

On the baseline page each configuration exposes maximum iterations, output tokens and task time limit; each member exposes temperature and tool-calling mode. Turn off automatic baseline setup only to edit baseline planner/tool selection deliberately. The separate team preset remains available for experiments with collaborating agents. Up to ten comparison configurations are accepted by the browser and API. Baseline output tokens are limited to 16384; the workspace explains this limit before launch.

Verification uses simulated provider catalogs and captures launch payloads: ten slots, independent model choice, failed switches, preserved edits on resize, separate baseline configurations, independent temperatures/token budgets, and execution forwarding with an identical task. No model completions or paid tool calls are needed for these UI/configuration checks.

Model selection only queues the requested ID. Choosing a model does not load, unload, or generate with it. At runtime the existing local-server lease loads the selected model when its turn begins and protects it through the entire run. Explicit selections stay pinned even if another model is active. Selection is safe while another experiment runs; it does not modify that running experiment.

## Reproducibility and model profiles

A Playpen request record distinguishes requested values, effective/confirmed values,
server defaults, and unknown values. Temperature and max output tokens are sent
explicitly by supported chat paths. Max iterations belongs to Playpen's agent loop.
LM Studio load settings, provider reasoning settings, and server presets remain
separate unless their values are actually sent or confirmed.

Do not describe an unconfirmed LM Studio GUI preset as reproduced. Native tool
capability is recorded separately: untested, advertised by the provider, observed
working, or observed failing. `Auto` is an execution policy and does not by itself
prove native model support.

## Compact settings and defaults

The workspace starts with a compact summary table of all models. Each row has a chooser and editable ReAct/other planner, tool-calling mode, temperature, iterations, tokens and baseline seconds. Detailed cards remain available below. The **Apply defaults to all models** button applies those common settings to current slots without changing identities, endpoints or tools. Defaults are saved in this browser, not in the credential vault. Applying them is explicit; restoring the defaults editor does not overwrite individual model settings. New slots inherit Model 1 settings.

The baseline time limit is visible in the summary and every card, validates 1–1800 seconds, and is forwarded independently to each baseline configuration and comparison-page URL. It defaults to 210 seconds; a diagnostic run with slow reasoning models may use 600. It is specifically a baseline task budget: custom agent runs still use iteration limits and provider request timeouts.

Visible planner names use **ReAct**, **Chain of Thought**, and **Tree of Thought** while serialized values remain react/cot/tree. Help punctuation was repaired from incorrect text encoding; help markup continues to render as formatted text.
