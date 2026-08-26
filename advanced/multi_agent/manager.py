#  Multi-Agent Manager (advanced/multi_agent/)
# manager.py — Spawn, register, route, and kill agents
from core.agent import Agent


class AgentManager:
    """
    Registry and router for multiple Agent instances.
    Each agent is identified by a string agent_id.
    """

    def __init__(self):
        self._registry: dict[str, Agent] = {}

    def spawn(self, agent_id: str, agent: Agent) -> None:
        """Register a pre-built Agent under agent_id."""
        if agent_id in self._registry:
            raise ValueError(f"Agent '{agent_id}' already registered.")
        self._registry[agent_id] = agent
        print(f"[AgentManager] Spawned agent: {agent_id}")

    def route(self, task: str, agent_id: str) -> str:
        """Run a task on the specified agent and return the result."""
        if agent_id not in self._registry:
            raise KeyError(f"Agent '{agent_id}' not found.")
        print(f"[AgentManager] Routing to {agent_id}: {task[:60]}")
        return self._registry[agent_id].run(task)

    def broadcast(self, task: str) -> dict[str, str]:
        """Run the same task on all registered agents, collect results."""
        results = {}
        for agent_id, agent in self._registry.items():
            print(f"[AgentManager] Broadcasting to {agent_id}")
            results[agent_id] = agent.run(task)
        return results

    def kill(self, agent_id: str) -> None:
        """Remove an agent from the registry."""
        if agent_id in self._registry:
            del self._registry[agent_id]
            print(f"[AgentManager] Killed agent: {agent_id}")

    def list_agents(self) -> list[str]:
        return list(self._registry.keys())
    