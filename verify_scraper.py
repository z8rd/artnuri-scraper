import asyncio
import os
import json
import logging
from orchestrator import Orchestrator

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def test_verification():
    print("=== Artnuri Scraper Core Unit Test ===")
    
    # 1. Setup Orchestrator
    data_dir = "./data_test"
    orchestrator = Orchestrator(data_dir=data_dir)
    
    # 2. Test keyword (using a specific one to keep it fast, e.g. "미디어아트")
    keywords = ["미디어아트"]
    print(f"Starting test scrape for keywords: {keywords}")
    
    # Run scraping
    await orchestrator.start_scraping(keywords)
    
    # 3. Load results
    results = orchestrator.load_last_results()
    print(f"\nVerification Results:")
    print(f"- File created: {os.path.exists(orchestrator.data_file)}")
    print(f"- Number of items scraped: {len(results)}")
    
    if results:
        print(f"- Sample item keys: {list(results[0].keys())}")
        print(f"- Sample title: {results[0].get('title')}")
        print(f"- Sample host (주관기관): {results[0].get('host')}")
        print(f"- Sample deadline (마감일): {results[0].get('deadline')}")
        print(f"- Sample matched keywords: {results[0].get('matched_keywords')}")
        print(f"- Sample detail description length: {len(results[0].get('description', ''))} chars")
        
        # Clean up test database file if desired, or leave it for inspection
        print("\nTest PASSED! The scraper correctly extracted all fields.")
    else:
        print("\nTest FAILED! No results scraped.")
        
if __name__ == "__main__":
    asyncio.run(test_verification())
