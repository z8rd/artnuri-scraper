import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
import urllib.parse
import logging

logger = logging.getLogger("ArtnuriSubAgent")

class SubAgent:
    def __init__(self, keyword: str, progress_callback=None):
        self.keyword = keyword
        self.progress_callback = progress_callback
        self.total_items = 0
        self.total_pages = 0
        self.current_page = 0
        self.processed_items = 0
        self.status = "대기 중"
        self.results = []
        self.base_url = "https://artnuri.or.kr/crawler/info/search.do"
        self.detail_url = "https://artnuri.or.kr/crawler/info/view.do"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.semaphore = asyncio.Semaphore(5)  # Limit concurrent detail fetches to be polite

    def report_progress(self, status: str):
        self.status = status
        if self.progress_callback:
            try:
                self.progress_callback(
                    keyword=self.keyword,
                    status=self.status,
                    current_page=self.current_page,
                    total_pages=self.total_pages,
                    processed_items=self.processed_items,
                    total_items=self.total_items
                )
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

    async def fetch_page(self, session: aiohttp.ClientSession, url: str, params: dict) -> str:
        async with self.semaphore:
            try:
                async with session.get(url, params=params, headers=self.headers, timeout=15) as response:
                    if response.status != 200:
                        logger.error(f"HTTP {response.status} for {url} with params {params}")
                        return ""
                    
                    # Read raw bytes and decode using apparent encoding or fallback to euc-kr/utf-8
                    content_bytes = await response.read()
                    content_type = response.headers.get('Content-Type', '')
                    
                    encoding = 'utf-8'
                    if 'charset=' in content_type:
                        encoding = content_type.split('charset=')[-1].strip()
                    else:
                        # Try to detect encoding or fallback to common Korean encodings
                        try:
                            # Let's try decodes
                            encoding = 'utf-8'
                            content_bytes.decode('utf-8')
                        except UnicodeDecodeError:
                            encoding = 'euc-kr'
                            
                    try:
                        return content_bytes.decode(encoding, errors='replace')
                    except Exception:
                        return content_bytes.decode('euc-kr', errors='replace')
            except Exception as e:
                logger.error(f"Network error fetching {url} with params {params}: {e}")
                return ""

    def parse_total_count(self, html: str) -> int:
        soup = BeautifulSoup(html, 'html.parser')
        total_tag = soup.find(class_="total") or soup.find(class_="total-rang")
        if total_tag:
            text = total_tag.get_text(strip=True)
            # Match digits in "전체 153건" or "153"
            match = re.search(r'\d+', text)
            if match:
                return int(match.group(0))
        return 0

    def parse_list_items(self, html: str) -> list:
        soup = BeautifulSoup(html, 'html.parser')
        items = []
        
        # Search for items inside type-card or type-list
        # The titles contain the onclick="goView(...)" call
        titles = soup.find_all("a", class_="title")
        for a in titles:
            title_text = a.get_text(strip=True)
            onclick = a.get("onclick", "")
            
            # Extract arguments from goView('docid', 'source', 'seNo')
            match = re.search(r"goView\s*\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*\)", onclick)
            if match:
                docid = match.group(1)
                source = match.group(2)
                seNo = match.group(3)
                
                # Try to extract deadline and status from the surrounding item card
                # The parent lists contains the deadline and state
                parent_li = a.find_parent("li")
                state = ""
                deadline = ""
                if parent_li:
                    state_tag = parent_li.find(class_=re.compile("state|prog"))
                    if state_tag:
                        state = state_tag.get_text(strip=True)
                    
                    # Find deadline date
                    for li_txt in parent_li.find_all("li"):
                        strong = li_txt.find("strong")
                        if strong and "마감일" in strong.get_text():
                            em = li_txt.find("em")
                            if em:
                                deadline = em.get_text(strip=True)
                                
                items.append({
                    "docid": docid,
                    "source": source,
                    "seNo": seNo,
                    "title": title_text,
                    "state": state,
                    "deadline": deadline
                })
        return items

    def parse_detail_page(self, html: str, meta: dict) -> dict:
        soup = BeautifulSoup(html, 'html.parser')
        
        sub_content = soup.find(class_="sub-content")
        if not sub_content:
            return {**meta, "error": "Content wrapper not found"}
        
        # Title and view count
        title_text = meta.get("title", "")
        views = "0"
        title_div = sub_content.find(class_="info-tit")
        if title_div:
            # Extract view count span first
            view_span = title_div.find("span", class_="view")
            if view_span:
                views = view_span.get_text(strip=True)
                view_span.extract() # Remove view count from title div to get clean title
            title_text = title_div.get_text(strip=True)

        details = {
            "docid": meta.get("docid"),
            "title": title_text,
            "state": meta.get("state"),
            "deadline": meta.get("deadline"),
            "views": views,
            "source_site": meta.get("source"),
            "host": "",
            "host_logo": "",
            "host_url": "",
            "target": "",
            "region": "",
            "period": "",
            "business_type": "",
            "apply_link": "",
            "genre": "",
            "files": [],
            "description": "",
            "contact_name": "",
            "contact_phone": "",
            "original_url": f"https://artnuri.or.kr/crawler/info/view.do?docid={meta.get('docid')}&source={urllib.parse.quote(meta.get('source'))}&seNo={meta.get('seNo')}&key=2301170002"
        }
        
        # Parse fields from info-txt
        info_txt = sub_content.find("ul", class_="info-txt")
        if info_txt:
            lis = info_txt.find_all("li", recursive=False)
            for li in lis:
                text = li.get_text()
                if "주관기관" in text:
                    # Find logo or homepage links
                    logo_a = li.find("a", class_="logo")
                    if logo_a:
                        details["host_url"] = logo_a.get("href", "")
                        # Try to get the host name from the logo image onError em text or source params
                        # Or extract from a inside
                    # Check for host name
                    details["host"] = meta.get("source") # Fallback to search list source
                elif "지원대상" in text:
                    target_list = [item.get_text(strip=True) for item in li.find_all("li")]
                    details["target"] = ", ".join(target_list) if target_list else text.replace("지원대상", "").strip()
                elif "지역" in text:
                    region_list = [item.get_text(strip=True) for item in li.find_all("li")]
                    details["region"] = ", ".join(region_list) if region_list else text.replace("지역", "").strip()
                elif "신청기간" in text:
                    details["period"] = text.replace("신청기간", "").strip()
                elif "사업유형" in text:
                    type_list = [item.get_text(strip=True) for item in li.find_all("li")]
                    details["business_type"] = ", ".join(type_list) if type_list else text.replace("사업유형", "").strip()
                elif "온라인신청" in text or "신청사이트" in text:
                    link_a = li.find("a", class_="site-link")
                    if link_a:
                        details["apply_link"] = link_a.get("href", "")
                elif "분야" in text:
                    genre_list = [item.get_text(strip=True) for item in li.find_all("li")]
                    details["genre"] = ", ".join(genre_list) if genre_list else text.replace("분야", "").strip()
                elif "첨부파일" in text:
                    files = []
                    for file_li in li.find_all("li"):
                        file_a = file_li.find("a")
                        if file_a:
                            href = file_a.get("href", "")
                            if href and not href.startswith("http"):
                                href = f"https://artnuri.or.kr{href}"
                            files.append({
                                "name": file_a.get_text(strip=True),
                                "url": href
                            })
                    details["files"] = files

        # Description (본문 내용)
        desc_div = sub_content.find("div", class_="supt-content")
        if desc_div:
            # Strip file-wrap if present
            if "file-wrap" in desc_div.get("class", []):
                # Look for another supt-content
                desc_divs = sub_content.find_all("div", class_="supt-content")
                for d in desc_divs:
                    if "file-wrap" not in d.get("class", []):
                        desc_div = d
                        break
            details["description"] = desc_div.get_text(separator="\n", strip=True)

        # Contact Info (문의처, 연락처)
        inqu_div = sub_content.find("div", class_="supt-inqu")
        if inqu_div:
            inqu_text = inqu_div.get_text()
            # Match "문의처: X" and "연락처: Y"
            name_match = re.search(r"문의처\s*:\s*([^\n\r]+)", inqu_text)
            phone_match = re.search(r"연락처\s*:\s*([^\n\r]+)", inqu_text)
            
            if name_match:
                details["contact_name"] = name_match.group(1).strip()
            if phone_match:
                details["contact_phone"] = phone_match.group(1).strip()
                
            # If not matched, try list items
            if not details["contact_name"] or not details["contact_phone"]:
                lis = inqu_div.find_all("li")
                for li in lis:
                    txt = li.get_text(strip=True)
                    if "문의처" in txt:
                        details["contact_name"] = txt.replace("문의처:", "").replace("문의처", "").strip()
                    elif "연락처" in txt:
                        details["contact_phone"] = txt.replace("연락처:", "").replace("연락처", "").strip()
                        
        return details

    async def scrape_detail(self, session: aiohttp.ClientSession, item_meta: dict) -> dict:
        params = {
            "docid": item_meta["docid"],
            "source": item_meta["source"],
            "seNo": item_meta["seNo"],
            "key": "2301170002"
        }
        html = await self.fetch_page(session, self.detail_url, params)
        if not html:
            return {**item_meta, "error": "상세 페이지 로드 실패"}
        
        try:
            detail = self.parse_detail_page(html, item_meta)
            self.processed_items += 1
            self.report_progress("상세 정보 스크랩 중")
            return detail
        except Exception as e:
            logger.error(f"Error parsing detail for {item_meta['docid']}: {e}")
            return {**item_meta, "error": f"상세 페이지 파싱 오류: {str(e)}"}

    async def start(self) -> list:
        self.report_progress("시작 중")
        self.current_page = 1
        
        async with aiohttp.ClientSession() as session:
            # 1. First request to determine total count
            params = {
                "pageIndex": 1,
                "recordCountPerPage": 50,
                "sw": self.keyword,
                "key": "2301170002"
            }
            first_page_html = await self.fetch_page(session, self.base_url, params)
            if not first_page_html:
                self.report_progress("검색 오류 (목록 페이지 로드 실패)")
                return []
                
            self.total_items = self.parse_total_count(first_page_html)
            if self.total_items == 0:
                self.report_progress("검색 결과 없음")
                return []
                
            # Compute total pages
            self.total_pages = (self.total_items + 49) // 50
            self.report_progress(f"검색 성공 ({self.total_items}건 발견, 전체 {self.total_pages}페이지)")
            
            # Parse first page items
            all_list_metas = self.parse_list_items(first_page_html)
            
            # 2. Fetch subsequent page list items
            if self.total_pages > 1:
                self.report_progress("목록 수집 중 (페이징)")
                tasks = []
                for p in range(2, self.total_pages + 1):
                    p_params = {**params, "pageIndex": p}
                    tasks.append(self.fetch_page(session, self.base_url, p_params))
                
                pages_html = await asyncio.gather(*tasks)
                for html in pages_html:
                    if html:
                        all_list_metas.extend(self.parse_list_items(html))
            
            # Remove duplicates just in case
            seen_ids = set()
            unique_metas = []
            for meta in all_list_metas:
                if meta["docid"] not in seen_ids:
                    seen_ids.add(meta["docid"])
                    unique_metas.append(meta)
                    
            self.total_items = len(unique_metas)
            self.report_progress(f"목록 수집 완료 (총 {self.total_items}건 상세 스크랩 준비)")
            
            # 3. Scrap all detail pages concurrently
            if unique_metas:
                self.report_progress("상세 정보 스크랩 중")
                detail_tasks = [self.scrape_detail(session, meta) for meta in unique_metas]
                self.results = await asyncio.gather(*detail_tasks)
                
            self.report_progress("수집 완료")
            return self.results
