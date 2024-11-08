from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Any, Dict
from .models import Paper, ResearchData, Outline, Chart

class ResearchInterface(ABC):
    @abstractmethod
    async def search_papers(self, topic: str) -> List[Paper]:
        pass

class OutlineGeneratorInterface(ABC):
    @abstractmethod
    async def generate_outline(self, research_data: ResearchData) -> Outline:
        pass

class ChartGeneratorInterface(ABC):
    @abstractmethod
    async def generate_charts(self, data_path: Path) -> List[Chart]:
        pass

class FileHandler(ABC):
    @abstractmethod
    async def read_file(self, file_path: Path) -> Any:
        pass
    
    @abstractmethod
    def extract_content(self, file_content: Any) -> Dict:
        pass