import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

import aiohttp
import urllib
import urllib.request
import asyncio
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
import xml.etree.ElementTree as ET


from downloader import batch_download_pdfs
from core.interfaces import ResearchInterface


class Author(BaseModel):
    name: str
    affiliation: Optional[str] = None
    profile_url: Optional[str] = None  # Google Scholar
    author_id: Optional[str] = None  # Google Scholar


class PaperEntry(BaseModel):
    id: str
    title: str
    authors: List[Author]
    summary: Optional[str] = None
    pdf_link: Optional[str] = None

    # arXiv
    updated: Optional[datetime] = None
    published: Optional[datetime] = None
    doi: Optional[str] = None
    journal_ref: Optional[str] = None
    primary_category: Optional[str] = None

    # Google Scholar
    cited_by_count: Optional[int] = None
    cited_by_url: Optional[str] = None
    position: Optional[int] = None
    venue: Optional[str] = None
    year: Optional[int] = None


class SearchResponse(BaseModel):
    entries: List[PaperEntry]
    total_results: int
    start_index: int = 0
    items_per_page: int = 10
    source: str  # 'arxiv' && 'google_scholar'


class GoogleScholarResearcher(ResearchInterface):
    """
    Google Scholar论文搜索实现
    https://serpapi.com/google-scholar-api
    """

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.base_url = "https://serpapi.com/search.json"
        self.api_key = (
            "5a37566593ffb2363efe51ee4551c0f6001bf3bd62f48549f06e3f16693b2399"
        )

    async def _parse_author(self, author_data: dict) -> Author:
        """异步解析作者信息"""
        return Author(
            name=author_data["name"],
            profile_url=author_data.get("link"),
            author_id=author_data.get("author_id"),
        )

    async def _parse_paper(self, result: dict) -> PaperEntry:
        """异步解析单个论文条目"""
        # 处理作者
        authors = []
        if "publication_info" in result and "authors" in result["publication_info"]:
            authors = await asyncio.gather(
                *[
                    self._parse_author(author)
                    for author in result["publication_info"]["authors"]
                ]
            )

        # 获取PDF链接
        pdf_link = None
        if "resources" in result:
            for resource in result["resources"]:
                if resource.get("file_format") == "PDF":
                    pdf_link = resource["link"]
                    break

        # 处理引用信息
        cited_by_count = None
        cited_by_url = None
        if "inline_links" in result and "cited_by" in result["inline_links"]:
            cited_by_count = result["inline_links"]["cited_by"]["total"]
            cited_by_url = result["inline_links"]["cited_by"]["link"]

        return PaperEntry(
            id=result["result_id"],
            title=result["title"],
            authors=authors,
            summary=result.get("snippet"),
            pdf_link=pdf_link,
            position=result["position"],
            cited_by_count=cited_by_count,
            cited_by_url=cited_by_url,
        )

    @staticmethod
    def _validate_parameters(max_results: int) -> None:
        """验证请求参数"""
        if max_results < 1 or max_results > 100:
            raise ValueError("max_results must be between 1 and 100")

    async def search_papers(
        self, topic: str, max_results: int = 10, start: int = 0
    ) -> SearchResponse:
        """
        从Google Scholar搜索论文
        Args:
            topic: 搜索关键词
            max_results: 最大返回结果数
            start: 起始索引
        Returns:
            SearchResponse: 包含解析后的论文信息
        """
        self._validate_parameters(max_results)
        encoded_topic = urllib.parse.quote(topic)
        url = f"{self.base_url}?engine=google_scholar&q={encoded_topic}&start={start}&num={max_results}&api_key={self.api_key}"

        retry_count = 0
        while retry_count < self.max_retries:
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            organic_results = data.get("organic_results", [])

                            # 并行解析所有论文
                            entries = await asyncio.gather(
                                *[
                                    self._parse_paper(result)
                                    for result in organic_results
                                ]
                            )

                            return SearchResponse(
                                entries=entries,
                                total_results=len(entries),
                                start_index=0,
                                items_per_page=max_results,
                                source="google_scholar",
                            )
                        elif response.status == 429:  # Too Many Requests
                            wait_time = min(2**retry_count, 32)
                            await asyncio.sleep(wait_time)
                        else:
                            raise Exception(
                                f"API request failed with status {response.status}"
                            )
            except aiohttp.ClientError as e:
                if retry_count == self.max_retries - 1:
                    raise Exception(
                        f"Network error after {self.max_retries} retries: {str(e)}"
                    )
                await asyncio.sleep(1)
            except Exception as e:
                if retry_count == self.max_retries - 1:
                    raise Exception(
                        f"Unexpected error after {self.max_retries} retries: {str(e)}"
                    )
                await asyncio.sleep(1)

            retry_count += 1

        raise Exception(f"Failed to get response after {self.max_retries} retries")


class ArxivResearcher(ResearchInterface):
    """
    arXiv论文搜索实现
    https://info.arxiv.org/help/api/user-manual.html
    """

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.base_url = "http://export.arxiv.org/api/query"

    async def _parse_author(self, author_elem: ET.Element) -> Author:
        """异步解析作者信息"""
        name = author_elem.find("{http://www.w3.org/2005/Atom}name").text
        affiliation = author_elem.find("{http://arxiv.org/schemas/atom}affiliation")
        return Author(
            name=name, affiliation=affiliation.text if affiliation is not None else None
        )

    async def _parse_entry(self, entry: ET.Element) -> PaperEntry:
        """异步解析单个论文条目"""
        # 并行解析所有作者
        author_elems = entry.findall("{http://www.w3.org/2005/Atom}author")
        authors = await asyncio.gather(
            *[self._parse_author(author_elem) for author_elem in author_elems]
        )

        # 获取PDF链接
        pdf_link = None
        for link in entry.findall("{http://www.w3.org/2005/Atom}link"):
            if link.get("title") == "pdf":
                pdf_link = link.get("href")
                break

        return PaperEntry(
            id=entry.find("{http://www.w3.org/2005/Atom}id").text,
            title=entry.find("{http://www.w3.org/2005/Atom}title").text,
            authors=authors,
            summary=entry.find("{http://www.w3.org/2005/Atom}summary").text.strip(),
            updated=datetime.strptime(
                entry.find("{http://www.w3.org/2005/Atom}updated").text,
                "%Y-%m-%dT%H:%M:%SZ",
            ),
            published=datetime.strptime(
                entry.find("{http://www.w3.org/2005/Atom}published").text,
                "%Y-%m-%dT%H:%M:%SZ",
            ),
            pdf_link=pdf_link,
            doi=entry.find("{http://arxiv.org/schemas/atom}doi").text
            if entry.find("{http://arxiv.org/schemas/atom}doi") is not None
            else None,
            journal_ref=entry.find("{http://arxiv.org/schemas/atom}journal_ref").text
            if entry.find("{http://arxiv.org/schemas/atom}journal_ref") is not None
            else None,
            primary_category=entry.find(
                "{http://arxiv.org/schemas/atom}primary_category"
            ).get("term"),
        )

    async def _parse_arxiv_result(self, xml_string: str) -> SearchResponse:
        """异步解析arXiv API返回的XML"""
        root = ET.fromstring(xml_string)

        total_results = int(
            root.find("{http://a9.com/-/spec/opensearch/1.1/}totalResults").text
        )
        start_index = int(
            root.find("{http://a9.com/-/spec/opensearch/1.1/}startIndex").text
        )
        items_per_page = int(
            root.find("{http://a9.com/-/spec/opensearch/1.1/}itemsPerPage").text
        )

        # 并行解析所有条目
        entry_elems = root.findall("{http://www.w3.org/2005/Atom}entry")
        entries = await asyncio.gather(
            *[self._parse_entry(entry) for entry in entry_elems]
        )

        return SearchResponse(
            entries=entries,
            total_results=total_results,
            start_index=start_index,
            items_per_page=items_per_page,
            source="arxiv",
        )

    async def search_papers(
        self, topic: str, max_results: int = 10, start: int = 0
    ) -> SearchResponse:
        """
        Asynchronously searches for papers on arXiv based on a given topic.
        This method performs a search query on arXiv's API and handles rate limiting and retries.
        The results are parsed and returned as a SearchResponse object.
        Args:
            topic (str): The search query topic to look for in arXiv papers
            max_results (int, optional): Maximum number of results to return. Defaults to 10.
            start (int, optional): Starting index for pagination. Defaults to 0.
        Returns:
            SearchResponse: Object containing the search results with paper information
        Raises:
            Exception: If API request fails, network error occurs, parsing fails, or max retries exceeded
        """
        
        self._validate_parameters(max_results, start)

        encoded_topic = urllib.parse.quote(topic)
        url = f"{self.base_url}?search_query=all:{encoded_topic}&start={start}&max_results={max_results}"

        retry_count = 0
        while retry_count < self.max_retries:
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            content = await response.text()
                            return await self._parse_arxiv_result(content)
                        elif response.status == 429:
                            wait_time = min(2**retry_count, 32)
                            await asyncio.sleep(wait_time)
                        else:
                            raise Exception(
                                f"API request failed with status {response.status}"
                            )
            except aiohttp.ClientError as e:
                if retry_count == self.max_retries - 1:
                    raise Exception(
                        f"Network error after {self.max_retries} retries: {str(e)}"
                    )
                await asyncio.sleep(1)
            except ET.ParseError as e:
                raise Exception(f"Failed to parse arXiv response: {str(e)}")
            except Exception as e:
                raise Exception(f"Unexpected error: {str(e)}")

            retry_count += 1

        raise Exception(f"Failed to get response after {self.max_retries} retries")

    @staticmethod
    def _validate_parameters(max_results: int, start: int) -> None:
        """验证请求参数"""
        if max_results < 1 or max_results > 100:
            raise ValueError("max_results must be between 1 and 100")
        if start < 0:
            raise ValueError("start must be non-negative")


async def main():
    research = ArxivResearcher()
    results = await research.search_papers("cyberpunk", max_results=10)

    pdfs = []
    for entry in results.entries:
        print(f"标题: {entry.title}")
        print(f"PDF链接: {entry.pdf_link}")
        print(f"摘要：{entry.summary}")
        print("-" * 50)
        if entry.pdf_link:
            secure_link = entry.pdf_link.replace("http://", "https://")
            pdfs.append(secure_link)

    print(f"总共找到 {results.total_results} 条结果")
    print(f"准备下载 {len(pdfs)} 个PDF文件")
    result = await batch_download_pdfs(pdfs)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
