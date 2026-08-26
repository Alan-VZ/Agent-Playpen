# Full Folder Structure

agent-playpen/
|-- README.md                       # Project overview and quick-start
|-- pyproject.toml                  # Build system and dependency groups
|-- .env.example                    # All environment variables with comments
|-- .gitignore                      # Git ignore patterns
|
|-- core/                           # Core agent loop and orchestration
|   |-- __init__.py
|   |-- agent.py                    # Main Agent class (Think-Act-Observe loop)
|   |-- runner.py                   # CLI entry point using argparse
|   |-- context.py                  # AgentContext shared state dataclass
|   +-- exceptions.py               # Custom exception hierarchy
|
|-- planner/                        # Planning and task decomposition
|   |-- __init__.py
|   |-- base_planner.py             # Abstract BasePlanner interface
|   |-- react_planner.py            # ReAct (Reason + Act) planner
|   |-- cot_planner.py              # Chain-of-Thought planner
|   |-- tree_planner.py             # Tree-of-Thought planner
|   +-- plan_schema.py              # Pydantic Plan and Step schemas
|
|-- backends/                       # LLM backend adapters
|   |-- __init__.py
|   |-- base_backend.py             # Abstract BaseBackend interface
|   |-- lm_studio.py                # LM Studio local backend (primary)
|   |-- ollama.py                   # Ollama local backend
|   |-- openai_backend.py           # OpenAI API backend
|   |-- anthropic_backend.py        # Anthropic Claude backend
|   |-- azure_openai.py             # Azure OpenAI backend
|   |-- groq_backend.py             # Groq fast inference backend
|   |-- together_backend.py         # Together AI backend
|   +-- backend_factory.py          # Factory pattern for backend creation
|
|-- tools/                          # Plug-in tool system
|   |-- __init__.py
|   |-- base_tool.py                # Abstract BaseTool interface
|   |-- tool_registry.py            # Tool registration and discovery
|   |-- tool_executor.py            # Safe tool execution with timeout
|   +-- packs/
|       |-- web/
|       |   |-- search_tool.py      # Web search (SerpAPI / Tavily / DDG)
|       |   |-- fetch_tool.py       # URL fetch and HTML-to-markdown
|       |   +-- scraper_tool.py     # CSS-selector scraping
|       |-- filesystem/
|       |   |-- read_file.py        # Read files from disk
|       |   |-- write_file.py       # Write files to disk
|       |   +-- list_dir.py         # Directory listing with sandboxing
|       |-- code/
|       |   |-- python_repl.py      # Subprocess-isolated Python REPL
|       |   |-- shell_exec.py       # Sandboxed shell command runner
|       |   +-- linter_tool.py      # Ruff / pyflakes code linter
|       |-- data/
|       |   |-- csv_tool.py         # CSV read, write, and query
|       |   |-- json_tool.py        # JSON manipulation
|       |   +-- sql_tool.py         # SQLite safe query execution
|       |-- api/
|       |   |-- http_tool.py        # Generic HTTP GET/POST/PUT/DELETE
|       |   +-- graphql_tool.py     # GraphQL query tool
|       +-- utils/
|           |-- calculator_tool.py  # Safe math expression evaluator
|           |-- datetime_tool.py    # Date and time utilities
|           +-- summarize_tool.py   # Text summarization helper
|
|-- memory/                         # Memory systems
|   |-- __init__.py
|   |-- base_memory.py              # Abstract BaseMemory interface
|   |-- in_memory.py                # Simple dict-based in-process store
|   |-- conversation_buffer.py      # Rolling token-aware conversation window
|   |-- vector_store.py             # ChromaDB / FAISS vector memory
|   |-- episodic_memory.py          # Session-level episode tracking
|   |-- semantic_memory.py          # Long-term fact store with retrieval
|   |-- working_memory.py           # Short-term scratchpad
|   +-- memory_manager.py           # Unified router across all stores
|
|-- debugging/                      # Debugging and observability tools
|   |-- __init__.py
|   |-- tracer.py                   # Event tracer: think/act/observe/error
|   |-- logger.py                   # Structured JSON logger via structlog
|   |-- inspector.py                # AgentContext state dump at any step
|   |-- replay.py                   # Replay a saved trace file in terminal
|   |-- cost_tracker.py             # Token counting and cost accounting
|   |-- diff_viewer.py              # Context before/after diff viewer
|   +-- dashboard/
|       |-- server.py               # FastAPI debug dashboard server
|       +-- templates/              # Jinja2 HTML templates for dashboard
|
|-- examples/                       # Ready-to-run example agents
|   |-- basic_chat.py               # Minimal chat loop (40 lines)
|   |-- react_agent.py              # ReAct + web search (80 lines)
|   |-- file_agent.py               # File read/process/write (60 lines)
|   |-- code_agent.py               # Code gen + REPL iteration (70 lines)
|   |-- research_agent.py           # Multi-step research pipeline (100 lines)
|   |-- multi_agent/
|   |   |-- orchestrator.py         # Spawns and routes worker agents
|   |   +-- worker_agent.py         # Specialized worker agent
|   +-- memory_demo.py              # Demonstrates all memory types (60 lines)
|
|-- advanced/                       # Advanced and optional modules
|   |-- __init__.py
|   |-- evaluator.py                # LLM-as-judge output scorer
|   |-- self_critique.py            # Self-critique and refinement loop
|   |-- guardrails.py               # Input and output safety guardrails
|   |-- rate_limiter.py             # Token-bucket limiter with backoff
|   |-- prompt_optimizer.py         # A/B prompt testing and selection
|   |-- multi_agent/
|   |   |-- manager.py              # Spawn, register, route, kill agents
|   |   +-- message_bus.py          # Asyncio pub/sub message bus
|   +-- streaming/
|       |-- stream_handler.py       # Streaming response processor
|       +-- token_streamer.py       # Token-by-token yield with UI hooks
|
|-- config/                         # Configuration management
|   |-- settings.py                 # Pydantic-settings config model
|   |-- backends.yaml               # Backend presets (YAML)
|   +-- tools.yaml                  # Tool pack enable/disable config
|
+-- tests/                          # Test suite
    |-- unit/
    |-- integration/
    +-- fixtures/
