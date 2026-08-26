# summarize_tool.py
from tools.base_tool import BaseTool


class SummarizeTool(BaseTool):
    """Summarize a block of text by calling the agent's backend."""

    name = "summarize"
    description = "Summarize a long text into a concise paragraph."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to summarize"},
            "max_words": {
                "type": "integer",
                "default": 100,
                "description": "Target word count for the summary",
            },
        },
        "required": ["text"],
    }

    def __init__(self, backend):
        self.backend = backend

    def run(self, **kwargs) -> str:
        text = kwargs["text"]
        max_words = kwargs.get("max_words", 100)
        prompt = (
            f"Summarize the following text in at most {max_words} words. "
            f"Be concise and factual.\n\nText:\n{text}"
        )
        messages = [{"role": "user", "content": prompt}]
        return self.backend.chat(messages)
