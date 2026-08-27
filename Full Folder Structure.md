# Full Folder Structure

This file reflects the current repository layout as it exists today.

```text
agent-playpen/
├── .env.example
├── .gitignore
├── CHANGELOG.md
├── Extension Guide.txt
├── Full Folder Structure.md
├── Installation and Quick-Start Guide.md
├── LICENSE
├── README.md
├── Start Agent Playpen.cmd
├── advanced/
│   ├── __init__.py
│   ├── evaluator.py
│   ├── guardrails.py
│   ├── prompt_optimizer.py
│   ├── rate_limiter.py
│   ├── self_critique.py
│   ├── multi_agent/
│   │   ├── manager.py
│   │   └── message_bus.py
│   └── streaming/
│       ├── stream_handler.py
│       └── token_streamer.py
├── assets/
│   ├── Cyberpunk goddess/
│   │   ├── favicon.ico
│   │   └── icon-256x256.ico
│   ├── Cyberpunk goddess.png
│   ├── Cyberpunk goddess_2.png
│   ├── Cyberpunk goddess_3.png
│   ├── icons.zip
│   ├── icons (1).zip
│   └── icons (2).zip
├── backends/
│   ├── __init__.py
│   ├── anthropic_backend.py
│   ├── azure_openai.py
│   ├── backend_factory.py
│   ├── base_backend.py
│   ├── groq_backend.py
│   ├── lm_studio.py
│   ├── ollama.py
│   ├── openai_backend.py
│   └── together_backend.py
├── config/
│   ├── settings.py
│   └── web_agent_config.json
├── core/
│   ├── __init__.py
│   ├── agent.py
│   ├── context.py
│   ├── exceptions.py
│   └── runner.py
├── debugging/
│   ├── __init__.py
│   ├── cost_tracker.py
│   ├── dashboard/
│   │   ├── server.py
│   │   └── templates/
│   │       └── index.html
│   ├── diff_viewer.py
│   ├── inspector.py
│   ├── logger.py
│   ├── replay.py
│   └── tracer.py
├── examples/
│   ├── basic_chat.py
│   ├── code_agent.py
│   ├── file_agent.py
│   ├── memory_demo.py
│   ├── react_agent.py
│   ├── research_agent.py
│   └── multi_agent/
│       ├── orchestrator.py
│       └── worker_agent.py
├── memory/
│   ├── __init__.py
│   ├── base_memory.py
│   ├── conversation_buffer.py
│   ├── episodic_memory.py
│   ├── in_memory.py
│   ├── memory_manager.py
│   ├── semantic_memory.py
│   ├── vector_store.py
│   └── working_memory.py
├── planner/
│   ├── __init__.py
│   ├── base_planner.py
│   ├── cot_planner.py
│   ├── plan_schema.py
│   ├── react_planner.py
│   └── tree_planner.py
├── pyproject.toml
├── tests/
├── tools/
│   ├── __init__.py
│   ├── base_tool.py
│   ├── packs/
│   │   ├── api/
│   │   │   ├── graphql_tool.py
│   │   │   ├── http_tool.py
│   │   │   ├── weather_tool.py
│   │   │   └── "Writing a Custom Tool — Example WeatherTool.md"
│   │   ├── code/
│   │   │   ├── linter_tool.py
│   │   │   ├── python_repl.py
│   │   │   └── shell_exec.py
│   │   ├── data/
│   │   │   ├── csv_tool.py
│   │   │   ├── json_tool.py
│   │   │   └── sql_tool.py
│   │   ├── filesystem/
│   │   │   ├── list_dir.py
│   │   │   ├── read_file.py
│   │   │   └── write_file.py
│   │   ├── utils/
│   │   │   ├── calculator_tool.py
│   │   │   ├── datetime_tool.py
│   │   │   └── summarize_tool.py
│   │   └── web/
│   │       ├── fetch_tool.py
│   │       ├── scraper_tool.py
│   │       └── search_tool.py
│   ├── tool_executor.py
│   └── tool_registry.py
├── traces/
├── .venv/
└── .git/
```

Note: `.venv` and `.git` are local environment metadata and are not usually shown in public project trees, but they are present in this working copy.
