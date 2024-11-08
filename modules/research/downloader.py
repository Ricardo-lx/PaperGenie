import os
import aiohttp
import asyncio
from enum import Enum
from tqdm import tqdm
from typing import List, Dict
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

class DownloadStatus(Enum):
    SUCCESS = "成功"
    FORBIDDEN = "访问被拒绝"
    NOT_FOUND = "文件不存在"
    SSL_ERROR = "SSL证书错误"
    NETWORK_ERROR = "网络错误"
    UNKNOWN_ERROR = "未知错误"

class DownloadResult:
    def __init__(self, url: str, status: DownloadStatus, message: str = ""):
        self.url = url
        self.status = status
        self.message = message

class DownloadManager:
    def __init__(self, 
                 max_concurrent: int = 5,
                 chunk_size: int = 1024 * 1024,  # 1MB chunks
                 timeout: int = 30,
                 max_retries: int = 3):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.chunk_size = chunk_size
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.connector = aiohttp.TCPConnector(
            limit=max_concurrent,
            force_close=False,
            enable_cleanup_closed=True
        )
        self.session = None
        self.thread_pool = ThreadPoolExecutor(max_workers=max_concurrent)

    @asynccontextmanager
    async def get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=self.timeout
            )
        try:
            yield self.session
        finally:
            pass  # 保持连接池开启

    async def download_pdf(self, url: str, output_dir: str, pbar: tqdm) -> DownloadResult:
        async with self.semaphore:  # 控制并发
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/pdf,application/x-pdf',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            
            retry_count = 0
            while retry_count < self.max_retries:
                try:
                    async with self.get_session() as session:
                        async with session.get(url, headers=headers) as response:
                            if response.status == 200:
                                if 'application/pdf' not in response.headers.get('content-type', ''):
                                    return DownloadResult(url, DownloadStatus.NOT_FOUND, "响应不是PDF文件")
                                    
                                filename = os.path.join(
                                    output_dir,
                                    os.path.basename(urlparse(url).path) or f"document_{hash(url)}.pdf"
                                )
                                if not filename.endswith(".pdf"):
                                    filename += ".pdf"

                                # 使用异步文件写入和分块下载
                                content = await response.read()
                                if not content.startswith(b'%PDF'):
                                    return DownloadResult(url, DownloadStatus.NOT_FOUND, "文件内容不是PDF格式")
                                
                                loop = asyncio.get_event_loop()
                                await loop.run_in_executor(
                                    self.thread_pool,
                                    lambda: open(filename, 'wb').write(content)
                                )
                                
                                pbar.update(1)
                                return DownloadResult(url, DownloadStatus.SUCCESS, f"已下载到: {filename}")
                                
                            elif response.status == 403:
                                return DownloadResult(url, DownloadStatus.FORBIDDEN, "需要认证或访问被拒绝")
                            elif response.status == 404:
                                return DownloadResult(url, DownloadStatus.NOT_FOUND, "文件不存在")
                            else:
                                if retry_count == self.max_retries - 1:
                                    return DownloadResult(url, DownloadStatus.UNKNOWN_ERROR, f"HTTP错误: {response.status}")
                        
                        wait_time = min(2 ** retry_count, 32)
                        await asyncio.sleep(wait_time)
                            
                except Exception as e:
                    if retry_count == self.max_retries - 1:
                        return DownloadResult(url, DownloadStatus.UNKNOWN_ERROR, str(e))
                    
                retry_count += 1
            
            return DownloadResult(url, DownloadStatus.UNKNOWN_ERROR, "超过最大重试次数")

async def batch_download_pdfs(urls: List[str], output_dir: str = "documents") -> Dict[str, DownloadResult]:
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    results = {}
    manager = DownloadManager(max_concurrent=5)  # 调整并发数
    
    try:
        with tqdm(total=len(urls), desc="Downloading PDFs") as pbar:
            tasks = [manager.download_pdf(url, output_dir, pbar) for url in urls]
            download_results = await asyncio.gather(*tasks)
            
            for url, result in zip(urls, download_results):
                results[url] = result

        success_count = sum(1 for r in results.values() if r.status == DownloadStatus.SUCCESS)
        print("\n下载统计:")
        print(f"总数: {len(urls)}")
        print(f"成功: {success_count}")
        print(f"失败: {len(urls) - success_count}")
        
        for url, result in results.items():
            if result.status != DownloadStatus.SUCCESS:
                print(f"\n{result.status.value}: {url}")
                print(f"错误信息: {result.message}")
                
    except Exception as e:
        print(f"批量下载出错: {str(e)}")
    finally:
        if manager.session:
            await manager.session.close()
        
    return results