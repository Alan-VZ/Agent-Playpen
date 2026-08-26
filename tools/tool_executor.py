import concurrent.futures
from tools.tool_registry import ToolRegistry


class ToolExecutor:
    """
    Executes tools safely with a configurable timeout.
    Uses concurrent.futures to enforce the deadline.
    """

    def __init__(self, registry: ToolRegistry, default_timeout: int = 30):
        self.registry = registry
        self.default_timeout = default_timeout

    def run(self, name: str, args: dict, timeout: int = None) -> str:
        """
        Run a named tool with the given arguments.

        Args:
            name: registered tool name
            args: keyword arguments for tool.run()
            timeout: seconds before TimeoutError (default: 30)

        Returns:
            String result from the tool.

        Raises:
            TimeoutError: if tool execution exceeds the timeout
            KeyError: if the tool is not registered
        """
        tool = self.registry.get(name)
        deadline = timeout if timeout is not None else self.default_timeout

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(tool.run, **args)
        try:
            return future.result(timeout=deadline)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(
                f"Tool '{name}' exceeded {deadline}s timeout."
            )
        finally:
            # Don't wait for the thread—return control immediately.
            # This prevents hangs if the tool is stuck.
            # Trade-off: a timed-out thread may keep running in the background.
            executor.shutdown(wait=False)
                