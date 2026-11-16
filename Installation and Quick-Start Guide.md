# Installation and Quick-Start Guide

## Prerequisites

- Python 3.11+
- For local models: LM Studio or Ollama running on your machine
- For cloud APIs: API keys from your chosen provider

## Clone the complete repository and enter it

```bash
git clone https://github.com/Alan-VZ/Agent-Playpen.git
cd Agent-Playpen
```

## Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows
```

## Install core dependencies

```bash
pip install -U pip
pip install -e ".[web-tools,dashboard,dev]"
```

## Install optional dependency groups

| Group | Install Command | What It Enables |
| --- | --- | --- |
| web-tools | `python -m pip install -e ".[web-tools]"` | Supported search, page/PDF reading, and scraping dependencies |
| code-tools | `python -m pip install -e ".[code-tools]"` | LinterTool; arbitrary Python/shell tools are not benchmark sandbox tools |
| vector-memory | `python -m pip install -e ".[vector-memory]"` | ChromaDB vector store and local embeddings |
| faiss-memory | `python -m pip install -e ".[faiss-memory]"` | FAISS and its embedding dependencies |
| data-tools | `python -m pip install -e ".[data-tools]"` | Enhanced CSV and data processing |
| dashboard | `python -m pip install -e ".[dashboard]"` | Dashboard server, templates, and retrieval dependencies |
| groq | `python -m pip install -e ".[groq]"` | Optional Groq SDK dependencies |
| together | `python -m pip install -e ".[together]"` | Optional Together SDK dependencies |
| dev | `python -m pip install -e ".[dev]"` | Test suite, coverage, and linting tools |

## Install with all recommended extras

```bash
python -m pip install -e ".[web-tools,dashboard,dev]"
```

## Copy and configure the environment file

```bash
cp .env.example .env
```

Use `.env` for non-secret settings, including local URLs and Azure deployment
information. Save API keys using the dashboard credential manager or a hidden CLI
prompt:

```bash
python -m config.credentials set OPENROUTER_API_KEY
```

Keys are stored in Windows Credential Locker, macOS Keychain, or Linux Secret
Service, outside the repository. Saving fails if native encrypted storage is
unavailable. Existing `.env` keys can be moved with **Migrate Legacy Keys**.
See the [complete credential guide](docs/credentials-and-openrouter.md).

## Start LM Studio for local inference (optional)

1. Download and open the [LM Studio](https://lmstudio.ai) desktop application
2. Download a model — **Mistral 7B Instruct** or **Qwen 2.5** are recommended for beginners
3. Go to the **Local Server** tab and click **Start Server**
4. Verify the server is running:

   ```bash
   curl http://localhost:1234/v1/models
   ```

## Option 1: Web UI (Recommended for most users)

### Start the web dashboard

```bash
python -m debugging.dashboard.server
```

Or use the **desktop shortcut** on Windows:

- **Start Agent Playpen.cmd** — Located in the project root or on your desktop
- Auto-detects if the server is already running
- Opens the browser automatically

### Access the UI

Open your browser to: `http://localhost:8765`

### Using the web dashboard

1. **Select Backend** — Choose "lm_studio" (local) or a cloud provider such as "openrouter"; save its key with the credential manager before running
2. **Load Models** — Click the **Load** button to discover available models
3. **Select a Model** — Pick from the dropdown (filters as you type)
4. **Configure Tools** — Check which tools to enable (web_search, fetch, read_file, etc.)
5. **Enter Your Task** — Describe what you want the agent to do
6. **Run Agent** — Click the button and watch model/tool activity
7. **View Results** — See the final answer, public action summaries, and execution trace

**Features:**

- Contextual help on every field (click the `?` icon)
- API keys saved in native encrypted OS storage; status does not return their values
- Model discovery with live backend queries
- Web search provider `auto` can use saved authenticated providers and key-free fallback; see [search providers](docs/search-providers.md) for ordering and cost implications
- Save configurations as JSON for reuse

### VS Code launch and tests

Open this repository folder in VS Code after installing the Python and Python
Debugger extensions. Create/install `.venv` as above. The Windows workspace
settings select `.venv/Scripts/python.exe` and enable pytest discovery in `tests`.
Choose **Agent Playpen: Local Dashboard** in Run and Debug and press F5. The launch
configuration starts the dashboard from this repository and opens its local URL
when Uvicorn reports readiness. Stop an existing server on port 8765 first.
On other platforms, select the appropriate interpreter and adjust the Windows
interpreter path in the shared settings/launch configuration.

### API inventory and repeated baseline comparisons

Use **☰ Menu → Secrets & API inventory** to expand a provider, open its key website,
save its key in encrypted OS storage, check access, and record a review date.
Saving a key does not trigger paid verification. Missing credentials required by
the selected configuration open setup before a run; unused providers do not block it.

Use **☰ Menu → Baseline tests** to compare single agents or 1–10-agent benchmark
teams across five objective tasks, with 1/5/20 repeats and HTML/CSV/JSON exports.
You can also select baseline-task checkboxes below the workspace Task field and
click **Load selected tasks** or **Compare using this agent**. The comparison page
retains those tasks and the current model settings; every configuration runs the
same selected fixtures. Unchecked tasks are excluded from execution and scoring.
The ordinary task workspace remains single-agent. See [baseline tests and inventory](docs/baseline-tests.md)
for configuration, CLI commands, execution boundaries, and live-validation limits.

## Option 2: CLI (For power users)

### Run a simple chat example

```bash
python examples/basic_chat.py
```

This creates an interactive chat loop with LM Studio.

### Run the CLI agent

```bash
python core/runner.py \
  --task "Research the latest trends in local AI agents" \
  --backend lm_studio \
  --planner react \
  --tools web_search fetch calculator
```

**CLI Arguments:**

- `--task` — The task to solve
- `--backend` — Backend name (lm_studio, openrouter, openai, anthropic, groq, together, ollama, azure_openai)
- `--model` — Provider model ID, including OpenRouter model slugs
- `--planner` — Planning strategy (react, cot, tree)
- `--tools` — Space-separated tool names
- `--max-iter` — Max reasoning iterations (default: 10)

## Troubleshooting

### LM Studio server won't start

- Ensure you have a model downloaded in LM Studio
- Check that port 1234 is not in use: `netstat -an | findstr 1234` (Windows) or `lsof -i :1234` (Mac/Linux)
- Try restarting the LM Studio application

### Model dropdown shows 0 models

- Verify LM Studio is running and the model is loaded
- Check the Base URL is correct: `http://localhost:1234/v1`
- The status message will show if using a fallback list vs. live query

### Web UI won't open

- Ensure port 8765 is free: `netstat -an | findstr 8765` (Windows)
- Try starting manually: `python -m debugging.dashboard.server`
- Check that FastAPI is installed: `pip install fastapi uvicorn jinja2`

### Tool execution times out

- The ordinary executor waits 30 seconds by default; a timed-out thread may continue running
- Long fetches or large file operations may exceed the timeout
- Benchmark task deadlines and worker-process supervision are configured separately on the Baseline tests page

## Security and testing

Unrestricted Python tools are disabled in the credential-enabled dashboard. The
trusted CLI retains them; same-user arbitrary code can access your credentials.
Run `python -m pytest -q` and `ruff check .` after installing the dev extras.
See [testing](docs/testing.md) and [credential security](docs/credentials-and-openrouter.md).

## Next Steps

- **Read the README** for architecture and design philosophy
- **Explore examples/** — See how to build specialized agents
- **Check the tool packs** — Understand what tools are available and how to add custom ones
- **Review debugging/** — Learn about tracing, cost tracking, and the dashboard
- **Study the planner strategies** — Read `planner/ReAct vs. Chain-of-Thought — Comparison.md`
