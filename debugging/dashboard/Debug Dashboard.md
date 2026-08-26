# Debug Dashboard (Web Interface)

The debug dashboard is a FastAPI + Jinja2 web application that provides a browser-based interface for agent configuration, execution, and observability. Launch with:

```bash
python -m debugging.dashboard.server --port 8765
```

Then open `http://localhost:8765` in your browser.

## Desktop Launcher

On Windows, use the provided desktop shortcut to launch the web app:

**Start Agent Playpen.cmd** — Detects if the server is already running, starts uvicorn if needed, and auto-opens the browser.

## Features

### Configuration Management
- **Backend Selection** — Choose from LM Studio, Ollama, OpenAI, Anthropic, Groq, Together, or Azure OpenAI
- **Model Discovery** — Live model listing from your selected backend (supports LM Studio, Ollama, and cloud APIs)
- **API Key Storage** — Securely save API keys to `.env` so you don't have to re-enter them
- **Base URL Configuration** — Set custom LLM endpoints
- **Planner Strategy** — Select ReAct, CoT, or Tree-of-Thought reasoning

### Tool Management
- Enable/disable individual tools (web search, file I/O, code execution, etc.)
- Configure search provider (DuckDuckGo, Tavily, SerpAPI)
- Set working directory sandbox for file operations

### Execution Controls
- Specify the task to complete
- Configure max iterations, temperature, and max output tokens
- Run the agent and view results in real-time
- Save configurations as JSON for reuse

### Help System
- Contextual `?` help buttons on every form field
- Field-level explanations with examples
- Quick-start guide for local model workflow

## API Endpoints

### Configuration & Execution

**POST /api/run** — Execute an agent with the provided config
- Body: form data from the web UI
- Returns: session ID, trace file path, and final answer

**POST /api/save-config** — Save current form as JSON
- Body: form data
- Returns: success message

**POST /api/save-env** — Merge form settings into `.env` file
- Body: form data
- Returns: success message, preserves existing keys and comments

### Model Discovery

**GET /api/models** — Discover available models from the backend
- Query params: `backend`, `base_url`, `api_key` (optional)
- Returns: `{ status, source: 'live'|'fallback', models: [list], message }`
- Queries all configured backends with automatic fallback if backend is offline

### API Key Management

**GET /api/keys** — Get status of stored API keys
- Returns: `{ KEY_NAME: { set: bool, hint: 'sk-...abcd' }, ... }`
- Keys are never returned to the browser; only a masked hint is shown

**POST /api/save-key** — Securely save an API key to `.env`
- Body: `{ name: 'OPENAI_API_KEY', value: 'sk-...' }`
- Returns: success message
- Merges into `.env` without overwriting unrelated keys

**POST /api/clear-key** — Remove an API key from `.env`
- Body: `{ name: 'OPENAI_API_KEY' }`
- Returns: success message

## Observability

The dashboard stores and displays:

- **Execution Traces** — Captured in `traces/` directory as JSON files
- **Session ID** — Unique identifier for each run
- **Thought History** — Full chain of reasoning steps
- **Action History** — Tools called and their arguments
- **Observation History** — Results from each tool call (truncated at 2000 chars)

## Configuration Persistence

- **Config Files** — Saved configurations live in `config/web_agent_config.json`
- **Environment Variables** — API keys stored in `.env` using merge logic (preserves comments and unrelated variables)
- **Backend Selection** — Automatically detects available backends (LM Studio at localhost:1234, etc.)

## Example Usage

1. Open `http://localhost:8765` in your browser
2. Select "lm_studio" as the backend
3. Click **Load** to fetch available models
4. Pick a model from the dropdown
5. Enable **web_search** and **calculator** tools
6. Enter your task
7. Click **Run Agent**
8. View results in the "Execution Result" panel

