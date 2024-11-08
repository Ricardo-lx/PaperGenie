import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import asyncio
from pathlib import Path
from typing import List
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
    WordFormatOption,
)
from docling.pipeline.simple_pipeline import SimplePipeline
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

from utils.logger import Logger


class FileProcessor:
    """A class for processing and converting documents to markdown format.
    This class handles the conversion of various document formats (PDF, DOCX, etc.) 
    to markdown using an asynchronous approach. It supports multiple input formats
    and provides logging capabilities.
    Attributes:
        logger: A logging instance for tracking processing events.
    Methods:
        process_files(file_paths: List[Path]) -> List[ConversionResult]:
            Asynchronously processes a list of files and converts them to markdown format.
            Args:
                file_paths: A list of Path objects pointing to input files.
            Returns:
                A list of ConversionResult objects containing the conversion results.
            Raises:
                IOError: If there's an error writing the output markdown files.
                Exception: If there's an error during the conversion process.
    """
    def __init__(self):
        self.logger = Logger.get_logger()
        self.logger.info("Initializing FileProcessor")

    async def process_files(self, file_paths: List[Path]):
        self.logger.info(f"Starting to process {len(file_paths)} files")
        
        doc_converter = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.IMAGE,
                InputFormat.DOCX,
                InputFormat.HTML,
                InputFormat.PPTX,
                InputFormat.ASCIIDOC,
                InputFormat.MD,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=StandardPdfPipeline, 
                    backend=PyPdfiumDocumentBackend
                ),
                InputFormat.DOCX: WordFormatOption(
                    pipeline_cls=SimplePipeline
                ),
            },
        )

        try:
            conv_results = await asyncio.to_thread(doc_converter.convert_all, file_paths)
            
            for res in conv_results:
                out_path = Path(r"C:\Users\Ricar\Documents\project\PaperGenie\documents")
                self.logger.info(
                    f"Document {res.input.file.name} converted. "
                    f"Saved markdown output to: {str(out_path)}"
                )
                self.logger.debug(
                    res.document._export_to_indented_text(max_text_len=16)
                )
                
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: open(out_path / f"{res.input.file.stem}.md", "w").write(res.document.export_to_markdown())
                    )
                except IOError as e:
                    self.logger.error(f"Failed to write markdown file: {str(e)}")
                    
            return conv_results
            
        except Exception as e:
            self.logger.error(f"Error during file processing: {str(e)}")
            raise

# async def main():
#     test = FileProcessor()
#     # 获取目录下所有需要处理的文件
#     dir_path = Path(r'C:\Users\Ricar\Desktop\test')
#     file_paths = [
#         f for f in dir_path.glob('*') 
#         if f.is_file() and f.suffix.lower() in ('.pdf', '.docx', '.md', '.html', '.pptx')
#     ]
#     await test.process_files(file_paths=file_paths)

# if __name__ == "__main__":
#     asyncio.run(main())