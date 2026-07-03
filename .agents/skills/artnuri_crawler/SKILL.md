---
name: artnuri-scraper-control
description: Controls and executes the Artnuri support project parallel scraper service, including crawling list pages, scraping details, and launching the FastAPI service.
---

# Artnuri Scraper Control Skill

This skill allows you to control and troubleshoot the Artnuri crawler and scraper service. The service is written in Python using `FastAPI`, `aiohttp`, and `BeautifulSoup`. It implements an Orchestrator and Sub-Agent parallel scraper architecture.

## Setup Requirements

Before running, make sure the dependencies are installed:
- `fastapi`
- `uvicorn`
- `aiohttp`
- `beautifulsoup4`
- `pandas`

You can use the local `uv` package manager to automatically manage the virtual environment and run the service without manual setup.

## Running the Service

Use the following command to start the FastAPI server with the front-end dashboard:

```powershell
# From the project root directory
C:\Users\김현진\.local\bin\uv.exe run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Once running, access the dashboard at:
`http://localhost:8000/`

## Core Code Architecture

1.  **[sub_agent.py](file:///C:/Users/김현진/.gemini/antigravity/scratch/artnuri_scraper/sub_agent.py)**:
    - Runs a `SubAgent` class targeting a single search keyword.
    - Paginates through list pages (`/crawler/info/search.do?sw={keyword}&pageIndex={p}&recordCountPerPage=50`).
    - Concurrently scrapes all details page parameters (`/crawler/info/view.do?docid={docid}...`) using an async HTTP client (`aiohttp.ClientSession`).
    - Reports detailed progress through a callback.

2.  **[orchestrator.py](file:///C:/Users/김현진/.gemini/antigravity/scratch/artnuri_scraper/orchestrator.py)**:
    - Manages multiple concurrent `SubAgent` instances.
    - Triggers execution in parallel using `asyncio.gather`.
    - Combines results, deduplicates items (handling items that matched multiple search terms), sorts them by deadline, and saves the final list to `data/scraped_results.json`.

3.  **[main.py](file:///C:/Users/김현진/.gemini/antigravity/scratch/artnuri_scraper/main.py)**:
    - Serves API routes: `/api/scrape`, `/api/status`, `/api/results`, `/api/export`.
    - Serves the frontend static files from `static/`.

4.  **[static/index.html](file:///C:/Users/김현진/.gemini/antigravity/scratch/artnuri_scraper/static/index.html)**:
    - A modern dark-themed dashboard featuring glassmorphism cards, status grid, progress meters, interactive data explorer, filter controls, CSV/JSON exporters, and a detailed project view modal.
