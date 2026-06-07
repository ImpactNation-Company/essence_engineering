from reasoning.engine import ReasoningEngine
from memory.store import MemoryStore
from reflection.engine import ReflectionEngine
from agents.stub import StubAgent
from utils.logger import log

class Orchestrator:
    def __init__(self):
        self.reasoning = ReasoningEngine()
        self.memory = MemoryStore()
        self.reflection = ReflectionEngine()
        self.agent = StubAgent()

    def run(self, query: str):

        log("ORCH", f"Received query: {query}")

        # 1. Reasoning
        reasoning = self.reasoning.process(query)

        # 2. Agent execution (stub)
        agent_output = self.agent.execute(query, reasoning)

        # 3. Memory write
        self.memory.store(query, agent_output, reasoning)

        # 4. Reflection
        reflection = self.reflection.evaluate(query, agent_output)

        return {
            "response": agent_output,
            "reasoning": reasoning,
            "reflection": reflection
        }