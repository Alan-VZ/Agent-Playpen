#  settings.py — Full Pydantic-Settings Class
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """
    Central configuration for Agent Playpen.
    All values can be overridden by environment variables or .env file.
    """

    # ----------------------------------------------------------------
    # Backend settings
    # ----------------------------------------------------------------
    LM_STUDIO_URL: str = "http://localhost:1234/v1"
    LM_STUDIO_MODEL: str = "local-model"
    LM_STUDIO_TEMPERATURE: float = 0.7
    LM_STUDIO_MAX_TOKENS: int = 2048

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_ORG_ID: Optional[str] = None

    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"

    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"

    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    TOGETHER_API_KEY: Optional[str] = None
    TOGETHER_MODEL: str = "meta-llama/Llama-3-70b-chat-hf"

    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_KEY: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT: Optional[str] = None
    AZURE_OPENAI_API_VERSION: str = "2024-05-01-preview"

    DEFAULT_BACKEND: str = "lm_studio"

    # ----------------------------------------------------------------
    # Memory settings
    # ----------------------------------------------------------------
    MEMORY_VECTOR_PROVIDER: str = "chroma"       # chroma | faiss
    MEMORY_EMBED_MODEL: str = "all-MiniLM-L6-v2"
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    MAX_CONVERSATION_TOKENS: int = 4000
    MEMORY_ENABLED_STORES: str = "working,conversation"

    # ----------------------------------------------------------------
    # Tool settings
    # ----------------------------------------------------------------
    TOOLS_ENABLED: str = "web_search,fetch,read_file,write_file,calculator"
    TOOL_TIMEOUT_SECONDS: int = 30
    PYTHON_REPL_FORBIDDEN_IMPORTS: str = (
        "os.system,subprocess,__import__,eval,exec,socket"
    )
    ALLOWED_DIRS: str = "."
    WEB_SEARCH_PROVIDER: str = "auto"    # auto | duckduckgo | serpapi | tavily | google
    SERPAPI_API_KEY: Optional[str] = None
    TAVILY_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    GOOGLE_CSE_ID: Optional[str] = None

    # ----------------------------------------------------------------
    # Debug and observability settings
    # ----------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "console"    # console | json
    TRACE_DIR: str = "./traces"
    COST_TRACKING_ENABLED: bool = True
    DASHBOARD_PORT: int = 8765

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        