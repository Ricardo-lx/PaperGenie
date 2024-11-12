import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import asyncio
import aiofiles
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Dict, List, Optional, Set
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
    """Optimized file processor for document conversion."""
    
    def __init__(self, max_workers: int = 4):
        self.logger = Logger.get_logger()
        self.logger.info("Initializing FileProcessor")
        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self._converter = None
        
    @property
    @lru_cache(maxsize=1)
    def converter(self) -> DocumentConverter:
        """Lazy initialization of DocumentConverter with caching."""
        if not self._converter:
            self._converter = DocumentConverter(
                allowed_formats={
                    InputFormat.PDF,
                    InputFormat.IMAGE,
                    InputFormat.DOCX,
                    InputFormat.HTML,
                    InputFormat.PPTX,
                    InputFormat.ASCIIDOC,
                    InputFormat.MD,
                },
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
        return self._converter

    async def process_files(self, file_paths: List[Path], batch_size: int = 5):
        """Process files in batches with improved concurrency."""
        self.logger.info(f"Starting to process {len(file_paths)} files")
        
        batches = [file_paths[i:i + batch_size] for i in range(0, len(file_paths), batch_size)]
        results = []
        
        for batch in batches:
            batch_results = await asyncio.gather(
                *[self._process_single_file(file_path) for file_path in batch],
                return_exceptions=True
            )
            results.extend([r for r in batch_results if not isinstance(r, Exception)])
            
        return results

    async def _process_single_file(self, file_path: Path):
        """Process a single file with error handling."""
        try:
            result = await asyncio.to_thread(self.converter.convert, file_path)
            await self._save_markdown(result)
            return result
        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {str(e)}")
            raise

    async def _save_markdown(self, result):
        """Save markdown content asynchronously."""
        out_path = Path('.cache')
        out_path.mkdir(exist_ok=True)
        
        file_path = out_path / f"{result.input.file.stem}.md"
        content = result.document.export_to_markdown()
        
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(content)
        
        self.logger.info(f"Saved markdown output to: {file_path}")
        self.logger.debug(result.document._export_to_indented_text(max_text_len=16))

class DocumentManager:
    """Optimized document manager with improved caching."""
    
    def __init__(self, cache_dir: str = '.cache'):
        self.processor = FileProcessor()
        self._content_cache: Dict[str, str] = {}
        self._cache_dir = Path(cache_dir)
        self._cache_file = self._cache_dir / 'document_cache.json'
        self._modified_files: Set[str] = set()
        asyncio.create_task(self._init_cache())

    async def _init_cache(self):
        """Initialize cache asynchronously."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        if self._cache_file.exists():
            try:
                async with aiofiles.open(self._cache_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    self._content_cache = json.loads(content)
            except Exception as e:
                self.processor.logger.error(f"Failed to load cache: {e}")
                self._content_cache = {}

    async def _save_cache(self):
        """Save cache asynchronously with modification tracking."""
        if not self._modified_files:
            return
            
        try:
            async with aiofiles.open(self._cache_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self._content_cache, ensure_ascii=False, indent=2))
            self._modified_files.clear()
        except Exception as e:
            self.processor.logger.error(f"Failed to save cache: {e}")

    @lru_cache(maxsize=1000)
    def _get_cache_key(self, file_path: Path) -> str:
        """Cache-aware key generation."""
        return str(file_path.resolve())

    async def process_and_cache_files(self, file_paths: List[Path]) -> Dict[str, str]:
        """Process and cache files with improved concurrency."""
        result_cache = {}
        files_to_process = []

        # Parallel file existence check and cache lookup
        async def check_file(file_path: Path):
            if not file_path.exists():
                self.processor.logger.warning(f"File does not exist: {file_path}")
                return None
            cache_key = self._get_cache_key(file_path)
            return (file_path, cache_key)

        check_tasks = [check_file(fp) for fp in file_paths]
        results = await asyncio.gather(*check_tasks)
        
        for result in results:
            if result:
                file_path, cache_key = result
                if cache_key in self._content_cache:
                    result_cache[str(file_path)] = self._content_cache[cache_key]
                else:
                    files_to_process.append(file_path)

        if files_to_process:
            try:
                conv_results = await self.processor.process_files(files_to_process)
                
                # Process results in parallel
                async def process_result(result):
                    if result and hasattr(result, 'input') and hasattr(result, 'document'):
                        cache_key = self._get_cache_key(result.input.file)
                        md_content = result.document.export_to_markdown()
                        return cache_key, str(result.input.file), md_content
                    return None

                process_tasks = [process_result(result) for result in conv_results]
                processed_results = await asyncio.gather(*process_tasks)
                
                for processed in processed_results:
                    if processed:
                        cache_key, file_str, md_content = processed
                        self._content_cache[cache_key] = md_content
                        result_cache[file_str] = md_content
                        self._modified_files.add(cache_key)
                
                await self._save_cache()
                
            except Exception as e:
                self.processor.logger.error(f"Failed to process files: {str(e)}")
                raise

        return result_cache

    def get_document_content(self, file_path: Path) -> Optional[str]:
        """Get cached document content."""
        cache_key = self._get_cache_key(file_path)
        return self._content_cache.get(cache_key)

    def get_all_documents(self) -> Dict[str, str]:
        """Get all cached documents."""
        return dict(self._content_cache)

    async def clear_cache(self):
        """Clear cache asynchronously."""
        self._content_cache.clear()
        self._modified_files.clear()
        
        if self._cache_file.exists():
            await asyncio.to_thread(self._cache_file.unlink)
        
        # Parallel file deletion
        tasks = []
        for md_file in self._cache_dir.glob('*.md'):
            tasks.append(asyncio.to_thread(md_file.unlink))
        await asyncio.gather(*tasks)





async def main():
    doc_manager = DocumentManager()
    dir_path = Path('documents/input')
    
    # 确保目录存在且创建
    dir_path.mkdir(parents=True, exist_ok=True)
    
    # 检查并打印目录内容
    print(f"Checking directory: {dir_path.absolute()}")
    all_files = list(dir_path.glob('*'))
    print(f"All files in directory: {[f.name for f in all_files]}")
    
    # 获取有效的文件路径并打印
    file_paths = [
        f for f in dir_path.glob('*') 
        if f.is_file() and f.suffix.lower() in ('.pdf', '.docx', '.md', '.html', '.txt')
    ]
    print(f"Valid files found: {[f.name for f in file_paths]}")
    
    if not file_paths:
        print("No valid files found in the input directory.")
        return
    
    try:
        print("开始处理文件...")
        documents = await doc_manager.process_and_cache_files(file_paths)
        if not documents:
            print("No documents were processed or cached.")
            print("Cache content:", doc_manager._content_cache)
        else:
            print(f"Successfully processed {len(documents)} documents:")
            for file_path, content in documents.items():
                print(f"- {file_path}: {content}")
    except Exception as e:
        print(f"Error processing documents: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())