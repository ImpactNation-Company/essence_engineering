"""Abstract base class for all Essence tools."""
from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """Every tool must declare a name, description, and a run() method."""

    name: str = "BaseTool"
    description: str = "Abstract tool."

    @abstractmethod
    def run(self, input_str: str) -> str:
        """Execute the tool and return a string result."""
        raise NotImplementedError

    def to_dict(self) -> dict:
        return {"name": self.name, "description": self.description}

    def __repr__(self) -> str:
        return f"<Tool: {self.name}>"
