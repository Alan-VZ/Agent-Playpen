# Agent Playpen

Agent Playpen is a lightweight, modular Python framework for building and running AI agents with local or cloud LLM backends, planner strategies, tool execution, memory, and observability.

The project is designed for experimentation and learning: you can run a local LM Studio model, give an agent tools like web search and file I/O, and let it reason through tasks using a ReAct-style or other planning loop.

This repo is intentionally extensible. You can:

- switch between LLM providers such as LM Studio, OpenAI, Anthropic, Groq, Together, and Azure OpenAI
- choose a planning strategy such as ReAct, CoT, or Tree-of-Thought
- register custom tools that the agent can call
- add memory layers for conversation history or vector retrieval
- trace execution and track estimated token cost

## Why this project exists

The goal is to provide a simple but realistic scaffold for building agentic systems without forcing a heavyweight framework. Rather than hiding the execution loop behind a black box, Agent Playpen makes the flow explicit:

1. the agent receives a task
2. the planner chooses an action strategy
3. the LLM decides what to do next
4. the tool executor invokes a registered tool
5. results are fed back into the reasoning loop

This makes it useful for:

- local AI experimentation with LM Studio or Ollama
- function-calling demos with structured tool schemas
- research assistants that can browse the web and read files
- task-based agents that use memory and iterative reasoning

## High-level architecture

The project is organized around a few core concepts:

- Backend: an LLM provider wrapper that exposes a standard chat interface
- Planner: decides how the agent thinks and acts across iterations
- Tool Registry: stores the tools available to the model
- Tool Executor: invokes registered tools with timeout protection
- Memory Manager: keeps conversation or retrieval memory
- Agent: orchestrates the reasoning loop

At runtime, the flow looks like this:

```text
Task
  -> Agent
      -> Planner
      -> Backend.chat(...)
      -> ToolExecutor.run(...)
      -> Memory + Tracer + Cost tracking
      -> next iteration / final answer
```

## Supported backends

The project includes backends for multiple providers, all registered in `backends/backend_factory.py`.

Current built-in backends:

- `lm_studio` — local OpenAI-compatible API served by LM Studio
- `ollama` — local Ollama models
- `openai` — OpenAI API
- `anthropic` — Anthropic Claude API
- `azure_openai` — Azure OpenAI
- `groq` — Groq hosted models
- `together` — Together AI models

The default local path is LM Studio, which is the primary target for this project.

## Planner strategies

The planner layer is intentionally modular. The repo includes multiple strategies:

- ReAct planner: reasoning + tool action loop
- CoT planner: chain-of-thought step flow
- Tree planner: more branching/decision-tree style reasoning

The CLI uses the ReAct planner by default.

## Tool system

Each tool extends `tools/base_tool.py` and implements a `run(self, **kwargs) -> str` method. Tools are converted into OpenAI-style function schemas via `to_openai_schema()` so the model can call them using structured arguments.

The tool registry keeps a set of available tools and the executor runs them in a safe thread with a timeout.

Built-in tools currently include:

- web search
- fetch web page content
- read a file from allowed directories
- write a file
- Python REPL sandbox
- calculator
- datetime utilities

Key files:

- `tools/base_tool.py`
- `tools/tool_registry.py`
- `tools/tool_executor.py`
- `tools/packs/...`

## Memory system

The memory layer manages agent context and conversation persistence.

Relevant modules:

- `memory/base_memory.py`
- `memory/memory_manager.py`
- `memory/conversation_buffer.py`

This allows the agent to keep a rolling conversation buffer and optionally retrieve relevant previous context.

## Debugging and observability

The repo also includes traces and cost tracking utilities:

- `debugging/tracer.py`
- `debugging/cost_tracker.py`

These help inspect the reasoning loop, log actions, and estimate usage cost during execution.

## Project structure

```text
Agent Playpen/
├── advanced/
├── backends/
│   ├── base_backend.py
│   ├── backend_factory.py
│   ├── lm_studio.py
│   ├── ollama.py
│   ├── openai_backend.py
│   ├── anthropic_backend.py
│   ├── azure_openai.py
│   ├── groq_backend.py
│   └── together_backend.py
├── config/
├── core/
│   ├── agent.py
│   ├── context.py
│   ├── runner.py
│   └── ...
├── debugging/
├── examples/
│   ├── basic_chat.py
│   ├── react_agent.py
│   ├── research_agent.py
│   ├── file_agent.py
│   ├── code_agent.py
│   └── multi_agent/
├── memory/
├── planner/
│   ├── base_planner.py
│   ├── react_planner.py
│   ├── cot_planner.py
│   ├── tree_planner.py
│   └── ...
├── tests/
├── tools/
│   ├── base_tool.py
│   ├── tool_registry.py
│   ├── tool_executor.py
│   └── packs/
├── .env.example
├── pyproject.toml
├── README.md
└── ...
```

## Prerequisites

- Python 3.11+
- An LLM runtime or provider available through one of the supported backends
- For local LM Studio usage: LM Studio running locally and exposing an OpenAI-compatible API at `http://localhost:1234/v1`

## Installation

Create a virtual environment and install the package with the most common dependency extras:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e .[web-tools,dev]
```

You can also install only the base package if you want a minimal setup:

```bash
pip install -e .
```

The project's `pyproject.toml` includes optional dependency groups for:

- `web-tools`
- `code-tools`
- `vector-memory`
- `faiss-memory`
- `data-tools`
- `dashboard`
- `groq`
- `together`
- `dev`

## Environment configuration

The project includes a sample environment file at `.env.example`.

Copy it to `.env` and customize as needed:

```bash
cp .env.example .env
```

Example settings include:

- `LM_STUDIO_URL`
- `LM_STUDIO_MODEL`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GROQ_API_KEY`
- `TOGETHER_API_KEY`
- `TOOLS_ENABLED`
- `TOOL_TIMEOUT_SECONDS`
- `MAX_CONVERSATION_TOKENS`

## Quick start with LM Studio

1. Open LM Studio
2. Start a local model server
3. Ensure it is exposing an OpenAI-compatible endpoint such as:
   `http://localhost:1234/v1`
4. Start the project from the repo root

Run a simple chat session:

```bash
python examples/basic_chat.py
```

This script creates an `LMStudioBackend`, checks the health of the endpoint, then runs an interactive chat loop.

## Running the CLI agent

The main CLI entry point is `core/runner.py`.

Example:

```bash
python core/runner.py --task "Research the latest trends in local AI agents and summarize them." --backend lm_studio --planner react --tools web_search fetch calculator
```

The CLI accepts:

- `--task` — the task to solve
- `--backend` — the LLM backend name
- `--planner` — planner strategy
- `--tools` — tool names to enable
- `--max-iter` — max reasoning loop iterations

## Web UI

Agent Playpen also includes a browser-based wrapper for configuration and execution so you can manage the agent from a web page instead of the terminal.

Start the UI with:

```bash
python -m debugging.dashboard.server
```

Then open:

```text
http://localhost:8765
```

The web UI lets you:

- choose the backend and model
- set provider credentials and endpoint details
- pick the planner and tools
- type the task directly into the page
- save configuration as JSON or `.env` from the UI if you want a file created automatically
- run the agent and inspect the result and trace path

This keeps the core implementation in Python while allowing configuration and orchestration to happen entirely in the browser.

## Example usage

### Basic chat

```bash
python examples/basic_chat.py
```

### Research workflow

```bash
python examples/research_agent.py
```

### File-oriented agent

```bash
python examples/file_agent.py
```

### Code assistant

```bash
python examples/code_agent.py
```

### Multi-agent worker pattern

```bash
python -m examples.multi_agent.worker_agent
```

## Using the project as a library

You can also build custom agent flows directly in Python.

```python
from backends.backend_factory import BackendFactory
from planner.react_planner import ReActPlanner
from tools.tool_registry import ToolRegistry
from tools.packs.web.search_tool import WebSearchTool
from tools.packs.web.fetch_tool import FetchTool
from core.agent import Agent
from memory.memory_manager import MemoryManager
from debugging.tracer import Tracer

backend = BackendFactory.create("lm_studio")
planner = ReActPlanner(backend=backend)
registry = ToolRegistry()
registry.register(WebSearchTool())
registry.register(FetchTool())

agent = Agent(
    backend=backend,
    planner=planner,
    tool_registry=registry,
    memory_manager=MemoryManager(),
    tracer=Tracer(),
    max_iterations=10,
)

result = agent.run("Find and summarize a useful local AI news article.")
print(result)
```

## Tool contract and extensibility

All tools follow an abstract contract defined by `BaseTool`:

```python
class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    def run(self, **kwargs) -> str:
        ...
```

This enables a consistent pattern for dynamically registered functions. To add a tool, you usually:

1. create a subclass of `BaseTool`
2. set `name`, `description`, and `parameters`
3. implement `run(**kwargs)`
4. register it in the `ToolRegistry`

This design makes it easy to extend the agent with domain-specific actions.

## Development workflow

Run static checks and tests if available:

```bash
pytest
```

Use ruff for linting if installed:

```bash
ruff check .
```

## Security and safety notes

Because the project includes tools like filesystem access and Python execution, use this repository carefully:

- restrict filesystem access using allowed directories
- avoid running untrusted code in the Python REPL tool
- review tool permissions before permitting broad file or shell access
- do not expose the agent to unsafe network or shell execution in production environments

## Typical use cases

- Local-first AI research assistant
- Document analysis with file reading and summarization
- Code assistant with REPL execution and file editing
- Task automation with internet access and tool orchestration
- Experiments in multi-step reasoning and autonomous actions

## Summary

Agent Playpen is a hands-on agent framework for experimenting with LLM-powered task execution. It combines the key ingredients of modern agent systems:

- model backends
- planner logic
- tool calling
- memory
- execution tracing
- iterative reasoning loops

It strikes a balance between accessibility and flexibility, making it well-suited for local experimentation, coding prototypes, and custom agent development.

## License

This project does not currently declare a license in the repository metadata. Check the project root for any additional licensing files or project-specific legal guidance before distributing or commercializing the code.
