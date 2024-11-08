import autogen
from typing import List, Dict

class BaseAgent:
    def __init__(self, config: Dict):
        self.config = config
        self.llm_config = {
            "temperature": 0.7,
            "model": "gpt-4"
        }

    def create_agent(self, name: str, system_message: str):
        return autogen.AssistantAgent(
            name=name,
            system_message=system_message,
            llm_config=self.llm_config
        )

class OutlineWriterAgent(BaseAgent):
    def __init__(self, config: Dict, perspective: str):
        super().__init__(config)
        self.perspective = perspective
        self.agent = self.create_agent(
            f"outline_writer_{perspective}",
            f"You are an outline writer focusing on {perspective} perspective."
        )

class ExpertAgent(BaseAgent):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.agent = self.create_agent(
            "expert",
            "You are an expert in academic writing and research."
        )