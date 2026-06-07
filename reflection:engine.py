from utils.logger import log

class ReflectionEngine:

    def evaluate(self, query, response):

        success = response is not None

        reflection = {
            "query": query,
            "success": success,
            "lesson": "v0 uses deterministic reasoning; no semantic evaluation yet"
        }

        log("REFLECT", "Reflection recorded")

        return reflection