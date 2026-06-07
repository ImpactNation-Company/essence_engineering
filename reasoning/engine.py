class ReasoningEngine:

    def process(self, query: str):

        observations = self.observe(query)
        analysis = self.analyze(observations)
        conclusion = self.conclude(analysis)

        return {
            "observations": observations,
            "analysis": analysis,
            "conclusion": conclusion
        }

    def observe(self, query):
        return {"input": query}

    def analyze(self, obs):
        return {
            "keywords": obs["input"].split()
        }

    def conclude(self, analysis):
        return {
            "summary": "This is a simplified reasoning output based on keyword decomposition."
        }