# Installation and Quick-Start Guide

## Prerequisites

- Python 3.11+
- For local models: LM Studio or Ollama running on your machine
- For cloud APIs: API keys from your chosen provider

## Create the project directory and enter it

```bash
mkdir agent-playpen && cd agent-playpen
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
pip install openai anthropic pydantic pydantic-settings structlog rich
```

## Install optional dependency groups

| Group | Install Command | What It Enables |
|-------|-----------------|-----------------|
| web-tools | `pip install requests markdownify beautifulsoup4 duckduckgo-search` | WebSearchTool, FetchTool, ScraperTool |
| code-tools | `pip install ruff` | LinterTool (PythonReplTool and ShellExecTool need no extra deps) |
| vector-memory | `pip install chromadb sentence-transformers tiktoken` | ChromaDB vector store and local embeddings |
| faiss-memory | `pip install faiss-cpu` | FAISS alternative to ChromaDB |
| data-tools | `pip install pandas` | Enhanced CSV and data processing |
| dashboard | `pip install fastapi uvicorn jinja2 python-dotenv` | Debug dashboard server and web UI |
| groq | `pip install groq` | Groq backend |
| together | `pip install together` | Together AI backend |
| dev | `pip install pytest pytest-asyncio ruff mypy` | Test suite and linting tools |

## Install with all recommended extras

```bash
pip install -e .[web-tools,dashboard,dev]
```

## Copy and configure the environment file

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in:

- **LM_STUDIO_URL** — typically `http://localhost:1234/v1` (if running LM Studio locally)
- **OPENAI_API_KEY** — if using OpenAI
- **ANTHROPIC_API_KEY** — if using Anthropic
- **GROQ_API_KEY** — if using Groq
- **TAVILY_API_KEY**, **SERPAPI_API_KEY**, or **GOOGLE_API_KEY** + **GOOGLE_CSE_ID** — for web search (if enabled)

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
python -m debugging.dashboard.server --port 8765
```

Or use the **desktop shortcut** on Windows:
- **Start Agent Playpen.cmd** — Located in the project root or on your desktop
- Auto-detects if the server is already running
- Opens the browser automatically

### Access the UI

Open your browser to: `http://localhost:8765`

### Using the web dashboard

1. **Select Backend** — Choose "lm_studio" (local) or a cloud provider
2. **Load Models** — Click the **Load** button to discover available models
3. **Select a Model** — Pick from the dropdown (filters as you type)
4. **Configure Tools** — Check which tools to enable (web_search, fetch, read_file, etc.)
5. **Enter Your Task** — Describe what you want the agent to do
6. **Run Agent** — Click the button and watch it think
7. **View Results** — See the final answer, reasoning steps, and execution trace

**Features:**
- Contextual help on every field (click the `?` icon)
- API keys stored securely in `.env` (never sent to browser)
- Model discovery with live backend queries
- Web search provider `auto` falls back through Google, Tavily, SerpAPI, then DuckDuckGo
- Save configurations as JSON for reuse

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
- `--backend` — Backend name (lm_studio, openai, anthropic, groq, together, ollama, azure_openai)
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
- Try starting manually: `python -m debugging.dashboard.server --port 8765`
- Check that FastAPI is installed: `pip install fastapi uvicorn jinja2`

### Tool execution times out
- Default timeout is 30 seconds; adjust `TOOL_TIMEOUT_SECONDS` in `.env`
- Long fetches or large file operations may exceed the timeout

## Next Steps

- **Read the README** for architecture and design philosophy
- **Explore examples/** — See how to build specialized agents
- **Check the tool packs** — Understand what tools are available and how to add custom ones
- **Review debugging/** — Learn about tracing, cost tracking, and the dashboard
- **Study the planner strategies** — Read `planner/ReAct vs. Chain-of-Thought — Comparison.md`
