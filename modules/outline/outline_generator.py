import sys
from pathlib import Path
from typing import Iterable, List
sys.path.append(str(Path(__file__).parent.parent.parent))

import instructor
from pprint import pprint
from openai import OpenAI
from pydantic import BaseModel
from autogen import ConversableAgent, GroupChat, GroupChatManager

from core.models import ResearchData
from modules.outline.file_processor import DocumentManager
from core.interfaces import OutlineGeneratorInterface 



class DraftOutline(BaseModel):
    outline: str
    perspectives: List[str]

class OutlineGenerator(OutlineGeneratorInterface):
    def __init__(self, lm):
        self.lm = lm
        self.doc_manager = DocumentManager()
        
    async def generate_outline(self, research_data: ResearchData):
        """
        Asynchronously generates a refined research paper outline through collaborative discussion.
        This method orchestrates a multi-step process involving an expert agent and multiple outline writers
        to create and refine a research paper outline through group discussion.
        Args:
            research_data (ResearchData): Object containing the research topic, related files, and papers.
                                        Expected to have attributes:
                                        - topic: The research topic
                                        - related_files: Reference materials
                                        - papers: Research papers
        Returns:
            dict: The result of the group chat discussion containing the refined outline.
                  Format determined by the chat_result from expert.initiate_chat().
        Process:
            1. Generates initial draft outline and perspectives using expert
            2. Creates outline writers based on different perspectives
            3. Sets up a group chat with expert and outline writers
            4. Initiates discussion to refine the outline based on provided context
        Example:
            >>> research_data = ResearchData(
                    topic="AI Ethics",
                    related_files=["ethics_guidelines.pdf"],
                    papers=["paper1.pdf", "paper2.pdf"]
            >>> outline = await generator.generate_outline(research_data)
        """
        # 1. 让 expert 生成初始大纲和perspectives
        initial_result = await self.generate_draft_outline(
            topic=research_data.topic,
            related_files=research_data.related_files
        )
        draft_outline = initial_result["draft_outline"]
        perspectives = initial_result["perspectives"]
        
        # 2. 创建 outline writers
        self.outline_writers = [
            OutlineWriter(self.lm, perspective) 
            for perspective in perspectives
        ]
        
        # 3. 设置 group chat
        groupchat = GroupChat(
            agents=self.outline_writers,
            messages=[],
        )
        
        group_chat_manager = ExpertAgent(groupchat, self.lm)
        
        # 4. 启动讨论
        context_message = f"""
            Topic: {research_data.topic}
            Draft Outline: {draft_outline}
            Related Files: {research_data.related_files}
            Papers: {research_data.papers}

            Let's refine this outline together based on the provided information.
            """
        
        chat_result = self.outline_writers[0].initiate_chat(
            group_chat_manager,
            message=context_message,
            summary_method="reflection_with_llm",
            summary_args={
                "summary_prompt": "Output the final outline.",
            }
        )
        
        pprint(chat_result)
        return chat_result
    
    async def generate_draft_outline(self, topic: str, related_files: List[Path]) -> dict:
        files_content = {}
        if related_files:
            try:
                files_content = await self.doc_manager.process_and_cache_files(related_files)
                
                # 格式化文件内容
                files_context = "\n\n".join([
                    f"文件 {filename}:\n{content}" 
                    for filename, content in files_content.items()
                ])
            except Exception as e:
                print(f"警告: 文件处理失败 - {e}")
                files_context = "无法处理相关文件"
        else:
            files_context = "未提供参考文件"

        prompt = f"""
            Based on the research topic: {topic}
            And related files content: {files_context}

            Please perform two tasks:
            
            1. Generate a detailed draft outline for this research paper. The outline should:
            - Follow standard academic paper structure (Introduction, Literature Review, Methodology, References, etc.)
            - Have a clear hierarchical structure with depth up to 3 levels
            - Include suggested content/focus for each section
            - Highlight potential research gaps or contributions
            - Estimate approximate length/importance for each section

            2. Analyze the topic from multiple angles by providing:
            - 3-5 key theoretical perspectives relevant to the topic
            - Potential methodological approaches (both qualitative and quantitative if applicable)
            - Critical research questions that could be addressed
            - Potential challenges or limitations to consider
            - Suggested areas for future research

            Format your response as:
            OUTLINE:
            [The outline here]

            PERSPECTIVES:
            [List of perspectives]
            """
        client = instructor.from_openai(OpenAI(
            base_url=self.lm["config_list"][0]["base_url"],
        )
        )
        
        try:
            response = client.chat.completions.create(
                model = self.lm["config_list"][0]["model"],
                messages = [
                    {"role": "user", "content": prompt}
                ],
                response_model = DraftOutline,
            )
            return {
                "draft_outline": response.outline,
                "perspectives": response.perspectives
            }
        except Exception as e:
            print(f"Fail to generate Outline: {e}")
            raise

class ExpertAgent(GroupChatManager):
    def __init__(self, groupchat, lm):
        super().__init__(
            groupchat=groupchat,
            name="ExpertAgent",
            llm_config=lm,
            system_message="""You are an expert discussion leader who:
                1. Analyzes research topics and manages outline refinement discussions
                2. Ensures EVERY outline writer participates and contributes their unique perspective
                3. Actively solicits feedback from quiet participants
                4. Synthesizes different viewpoints into a cohesive outline
                5. Guides the discussion by:
                   - Asking direct questions to specific outline writers
                   - Encouraging debate on conflicting viewpoints
                   - Maintaining focus on key outline sections
                   - Summarizing progress periodically
                
                Important: You MUST ensure each outline writer contributes at least twice before finalizing the outline.
                
                Output the final outline when you believe it is comprehensive and well-structured.
                """
        )
        self.tool_use = True

class OutlineWriter(ConversableAgent):
    def __init__(self, lm, perspective):
        super().__init__(
            name=f"OutlineWriter-{perspective}",
            llm_config=lm,
            system_message=f"""You are an outline writer focusing on the {perspective} perspective.
                You should:
                1. Analyze content from your unique perspective
                2. Suggest outline improvements based on your expertise
                3. Collaborate with other writers to create a comprehensive outline"""
            )
        self.tool_use = True

async def main():
    lm = {"config_list": [{
        "model": "qwen2.5", 
        "api_key": 'ollama', 
        'base_url':'http://localhost:11434/v1',
        'price': [0, 0],
    }]}
    researchData = ResearchData(
        topic="quantum computing",
        related_files=[Path("documents/input/1.pdf")],
        papers=[],
    )
    outline = await OutlineGenerator(lm=lm).generate_draft_outline(researchData.topic, researchData.related_files)
    pprint(outline)

    # response = await OutlineGenerator(lm=lm).generate_outline(researchData)
    
    # from typing import Dict, Any, List
    # chat_history: List[Dict[str, Any]] = response.chat_history
    # chat_summary: str = response.summary
    # import json
    # # 使用JSON格式保存到文件
    # with open('chat_history.json', 'w', encoding='utf-8') as f:
    #     json.dump(chat_history, f, ensure_ascii=False, indent=2)
    # with open('chat_summary.txt', 'w', encoding='utf-8') as f:
    #     f.write(chat_summary)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())