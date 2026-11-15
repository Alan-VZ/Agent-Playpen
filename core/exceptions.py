class AgentError(Exception):
    """Base exception for agent runtime failures."""


class AgentCancelledError(AgentError):
    """The caller stopped the run; no further operations should be scheduled."""


class AgentMaxIterationsError(AgentError):
    """Raised when the agent exceeds its iteration limit."""

    def __init__(self, iterations: int):
        self.iterations = iterations
        super().__init__(f"Agent exceeded max iterations ({iterations}).")


class AgentToolError(AgentError):
    """Raised when a tool execution fails during the agent loop."""

    def __init__(self, tool_name: str, original_exception: Exception):
        self.tool_name = tool_name
        self.original_exception = original_exception
        super().__init__(f"Tool '{tool_name}' failed: {original_exception}")
