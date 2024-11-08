import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import pprint
from autogen import ConversableAgent, GroupChat, GroupChatManager
from core.interfaces import OutlineGeneratorInterface  
from core.models import ResearchData

NUM_OUTLINE_WRITERS = 3

class OutlineGenerator(OutlineGeneratorInterface):
    def __init__(self, lm):
        self.lm = lm
        self.outline_writers = []
        self.expert = ExpertAgent(self.lm)
        
    # async def generate_outline(self, research_data: ResearchData):
    async def generate_outline(self):
        # 创建多个OutlineWriter
        self.outline_writers.extend(OutlineWriter(self.lm, f"perspective_{i}") for i in range(NUM_OUTLINE_WRITERS))
        # 组织讨论
        groupchat = GroupChat(
            agents=[self.expert] + self.outline_writers,
            messages=[],
            max_round=10,
        )
        group_chat_manager = GroupChatManager(
            groupchat=groupchat,
            llm_config=self.lm,
        )
        # 生成最终大纲
        chat_result = self.expert.initiate_chat(
        group_chat_manager,
        message="Let's generate an outline for this research",
        summary_method="reflection_with_llm",
        )
        return chat_result

class ExpertAgent(ConversableAgent):
    def __init__(self, lm):
        super().__init__(
            name="ExpertAgent", 
            llm_config=lm, 
            system_message="You are an expert agent."
        )
        self.tool_use = True

class OutlineWriter(ConversableAgent):
    def __init__(self, lm, perspective):
        super().__init__(
            name=f"OutlineWriter-{perspective}", 
            llm_config=lm, 
            system_message=f"You are an outline writer with perspective:{perspective}"
        )
        self.tool_use = True

async def main():
    lm = {"config_list": [{
        "model": "llama3.2:latest", 
        "api_key": 'ollama', 
        'base_url':'http://localhost:11434/v1',
        'price': [0, 0]
    }]}
    outline = await OutlineGenerator(lm=lm).generate_outline()
    pprint.pprint(outline)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())