from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path

@dataclass
class Paper:
    title: str
    authors: Optional[List[str]] = None
    abstract: Optional[str] = None
    url: Optional[str] = None
    pdf_path: Optional[Path] = None

@dataclass
class ResearchData:
    topic: str
    related_files: Dict[str, str]
    papers: Dict[str, str]

@dataclass
class Outline:
    sections: List[Dict]
    references: List[Paper]

@dataclass
class Chart:
    title: str
    data: Dict
    code: str
    image_path: Path

class FileType(Enum):
    PDF = "pdf"
    IMAGE = ("png", "jpg", "jpeg", "gif", "bmp")
    PPT = "ppt"
    DOCX = "docx"
    MD = "md"
    UNKNOWN = "unknown"

class OCRFileType(Enum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    HTML = "html"

# @dataclass
# class InputFile:
#     path: Path
#     file_type: FileType
#     content: Any = None