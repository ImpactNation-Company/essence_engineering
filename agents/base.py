"""Abstract base class for all Essence agents."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class Agent(ABC):
    """Base interface every agent must implement."""

    name: str = "BaseAgent"
    description: str = "Abstract agent base."

    @abstractmethod
    def execute(self, query: str, reasoning: Dict[str, Any], context: List[Dict] = None) -> str:
        """
        Execute the agent against a query.

        Args:
            query:     The raw user query.
            reasoning: Structured reasoning dict from ReasoningEngine.
            context:   Optional list of relevant past memory records.

        Returns:
            The agent's response string.
        """
        raise NotImplementedError
