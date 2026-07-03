import asyncio
import json
import os
import time
import logging
from typing import List, Dict, Any
from sub_agent import SubAgent

logger = logging.getLogger("ArtnuriOrchestrator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class ScrapeProgress:
    def __init__(self):
        self.status = "대기 중"  # 대기 중, 수집 중, 완료, 오류
        self.start_time = 0.0
        self.end_time = 0.0
        self.elapsed_time = 0.0
        self.total_found = 0
        self.total_scraped = 0
        self.agent_statuses = {} # Dict of keyword -> status dict

class Orchestrator:
    def __init__(self, data_dir: str = "."):
        self.data_dir = data_dir
        self.data_file = os.path.join(data_dir, "scraped_results.json")
        self.progress = ScrapeProgress()
        self.is_running = False

    def update_agent_progress(self, keyword: str, status: str, current_page: int, total_pages: int, processed_items: int, total_items: int):
        self.progress.agent_statuses[keyword] = {
            "status": status,
            "current_page": current_page,
            "total_pages": total_pages,
            "processed_items": processed_items,
            "total_items": total_items,
            "progress_percentage": int((processed_items / total_items * 100)) if total_items > 0 else 0
        }
        
        # Recalculate global progress summary
        total_found = 0
        total_scraped = 0
        for kw, state in self.progress.agent_statuses.items():
            total_found += state["total_items"]
            total_scraped += state["processed_items"]
            
        self.progress.total_found = total_found
        self.progress.total_scraped = total_scraped
        if self.is_running:
            self.progress.elapsed_time = time.time() - self.progress.start_time

    def get_status(self) -> Dict[str, Any]:
        if self.is_running:
            self.progress.elapsed_time = time.time() - self.progress.start_time
            
        return {
            "status": self.progress.status,
            "elapsed_time": round(self.progress.elapsed_time, 1),
            "total_found": self.progress.total_found,
            "total_scraped": self.progress.total_scraped,
            "agents": self.progress.agent_statuses
        }

    async def scrape_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        agent = SubAgent(
            keyword=keyword,
            progress_callback=self.update_agent_progress
        )
        # Initialize progress entry
        self.update_agent_progress(keyword, "대기 중", 0, 0, 0, 0)
        try:
            results = await agent.start()
            return results
        except Exception as e:
            logger.error(f"Error in SubAgent for keyword '{keyword}': {e}")
            self.update_agent_progress(keyword, f"오류: {str(e)}", 0, 0, 0, 0)
            return []

    async def start_scraping(self, keywords: List[str]):
        if self.is_running:
            logger.warning("Scraping is already in progress!")
            return
            
        self.is_running = True
        self.progress = ScrapeProgress()
        self.progress.status = "수집 중"
        self.progress.start_time = time.time()
        
        # Initialize statuses
        for kw in keywords:
            self.progress.agent_statuses[kw] = {
                "status": "대기 중",
                "current_page": 0,
                "total_pages": 0,
                "processed_items": 0,
                "total_items": 0,
                "progress_percentage": 0
            }

        logger.info(f"Starting parallel scraping for keywords: {keywords}")
        
        # Run sub-agents in parallel
        tasks = [self.scrape_keyword(kw) for kw in keywords]
        results_list = await asyncio.gather(*tasks)
        
        # Combine results and remove duplicates
        combined_results = {}
        
        for idx, keyword in enumerate(keywords):
            kw_results = results_list[idx]
            for item in kw_results:
                if "error" in item:
                    continue # Skip items that failed to load
                    
                docid = item["docid"]
                if docid in combined_results:
                    # Append keyword if already exists (item matched multiple keywords)
                    existing_item = combined_results[docid]
                    matched_kws = existing_item.get("matched_keywords", [])
                    if keyword not in matched_kws:
                        matched_kws.append(keyword)
                    existing_item["matched_keywords"] = matched_kws
                else:
                    item["matched_keywords"] = [keyword]
                    combined_results[docid] = item
                    
        # Convert dictionary back to list
        final_list = list(combined_results.values())
        
        # Sort by deadline (ascending, nearest first, but put empty/passed deadlines last or just regDt order)
        # Note: deadline format is usually "YYYY-MM-DD"
        # We will sort by deadline descending (or ascending based on preference)
        def sort_key(x):
            dl = x.get("deadline", "")
            return dl if dl else "9999-12-31" # Default empty deadline to end
            
        final_list.sort(key=sort_key)

        # Save to JSON file
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(final_list, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(final_list)} unique results to {self.data_file}")
        except Exception as e:
            logger.error(f"Failed to save results to file: {e}")

        self.progress.status = "완료"
        self.progress.end_time = time.time()
        self.progress.elapsed_time = self.progress.end_time - self.progress.start_time
        self.is_running = False
        logger.info("Scraping process complete.")
        
        # Force print final summary
        total_found = len(final_list)
        logger.info(f"Total Unique Items Collected: {total_found}")
        
    def load_last_results(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading {self.data_file}: {e}")
        return []
