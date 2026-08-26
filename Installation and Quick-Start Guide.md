# Installation and Quick-Start Guide

## Create the project directory and enter it

mkdir agent-playpen && cd agent-playpen
Create and activate a virtual environment:

python -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows

### Install core dependencies

pip install openai anthropic pydantic pydantic-settings structlog rich

#### Install optional dependency groups

|Group | Install Command | What It Enables
|web-tools | pip install requests markdownify beautifulsoup4 duckduckgo-search | WebSearchTool, FetchTool, ScraperTool
|code-tools | pip install ruff | LinterTool (PythonReplTool and ShellExecTool need no extra deps)
|vector-memory | pip install chromadb sentence-transformers tiktoken | ChromaDB vector store and local embeddings
|faiss-memory | pip install faiss-cpu | FAISS alternative to ChromaDB
|data-tools | pip install pandas | Enhanced CSV and data processing
|dashboard | pip install fastapi uvicorn jinja2 | Debug dashboard server
|groq | pip install groq | Groq backend (or use openai client directly)
|together | pip install together | Together AI backend
|dev | pip install pytest pytest-asyncio ruff mypy | Test suite and linting tools

##### Copy the environment file and fill in your keys

cp .env.example .env
'' Open .env in your editor and fill in API keys and paths

###### Start LM Studio for local inference

* Open the LM Studio desktop application
* Download a model — Mistral 7B Instruct is recommended for beginners
* Go to the Local Server tab and click Start Server
* Verify the server is running: curl <http://localhost:1234/v1/models>

###### Run the basic chat example

python examples/basic_chat.py
Launch the debug dashboard:

python -m debugging.dashboard.server --port 8765
'' Open <http://localhost:8765> in your browser
