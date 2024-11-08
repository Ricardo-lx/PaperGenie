import instructor
from autogen import ConversableAgent, GroupChat

class OutlineGeneration():
    def __init__(self, lm):
        self.lm = lm
    


class WriteOutline():
    def __init__(self, lm):
        self.lm = lm

    def write_outline(self, agent: ConversableAgent, chat: GroupChat):
        # Generate outline
        outline = self.lm.generate_outline(agent, chat)
        return outline
    
class WriteOutlineFromConv():
    