from fastapi import FastAPI, BackgroundTasks, Query, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import pandas as pd
import io
from typing import List, Optional
from orchestrator import Orchestrator

app = FastAPI(title="아트누리 병렬 크롤링 서비스", description="FastAPI + Orchestrator/Sub-Agent 기반 지원사업 수집 API")

# Allow CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DATA_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize Orchestrator
orchestrator = Orchestrator(data_dir=DATA_DIR)

# Background task wrapper
async def run_orchestrator_task(keywords: List[str]):
    await orchestrator.start_scraping(keywords)

@app.post("/api/scrape")
async def start_scrape(background_tasks: BackgroundTasks, keywords: Optional[List[str]] = Query(None)):
    if orchestrator.is_running:
        raise HTTPException(status_code=400, detail="이미 크롤링이 진행 중입니다.")
    
    if not keywords:
        keywords = ["음악", "클래식", "작곡", "미디어아트"]
        
    background_tasks.add_task(run_orchestrator_task, keywords)
    return {"status": "started", "keywords": keywords}

@app.get("/api/status")
async def get_status():
    return orchestrator.get_status()

@app.get("/api/results")
async def get_results(
    keyword: Optional[str] = None,
    state: Optional[str] = None,
    host: Optional[str] = None,
    search: Optional[str] = None
):
    results = orchestrator.load_last_results()
    if not results:
        return []
        
    filtered = results
    
    # Filter by keyword
    if keyword:
        filtered = [x for x in filtered if keyword in x.get("matched_keywords", [])]
        
    # Filter by state
    if state:
        filtered = [x for x in filtered if x.get("state") == state]
        
    # Filter by host
    if host:
        filtered = [x for x in filtered if host.lower() in x.get("host", "").lower()]
        
    # General text search
    if search:
        search_lower = search.lower()
        filtered = [
            x for x in filtered 
            if search_lower in x.get("title", "").lower() 
            or search_lower in x.get("description", "").lower()
            or search_lower in x.get("host", "").lower()
        ]
        
    return filtered

@app.get("/api/export")
async def export_results(format: str = "csv"):
    results = orchestrator.load_last_results()
    if not results:
        raise HTTPException(status_code=404, detail="내보낼 데이터가 없습니다. 먼저 수집을 진행해 주세요.")
        
    # Flatten matched keywords list to string
    flat_results = []
    for item in results:
        item_copy = item.copy()
        item_copy["matched_keywords"] = ", ".join(item_copy.get("matched_keywords", []))
        
        # Remove nested structures or formats
        files_list = item_copy.get("files", [])
        item_copy["files"] = ", ".join([f"{f['name']}({f['url']})" for f in files_list]) if files_list else ""
        flat_results.append(item_copy)
        
    df = pd.DataFrame(flat_results)
    
    if format == "csv":
        # Stream CSV in UTF-8-sig for Excel compatibility in Korean Windows
        stream = io.StringIO()
        df.to_csv(stream, index=False, encoding="utf-8-sig")
        response = StreamingResponse(
            iter([stream.getvalue()]),
            media_type="text/csv"
        )
        response.headers["Content-Disposition"] = "attachment; filename=artnuri_scraped_results.csv"
        return response
        
    elif format == "json":
        # Stream JSON file
        stream = io.BytesIO()
        json_str = json.dumps(results, ensure_ascii=False, indent=2)
        stream.write(json_str.encode('utf-8'))
        stream.seek(0)
        response = StreamingResponse(
            stream,
            media_type="application/json"
        )
        response.headers["Content-Disposition"] = "attachment; filename=artnuri_scraped_results.json"
        return response
        
    else:
        raise HTTPException(status_code=400, detail="지원하지 않는 형식입니다. (csv, json만 지원)")

# Serve index.html directly on root
@app.get("/")
async def read_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Artnuri Scraper Service backend is running. Frontend static/index.html is missing."}

# Mount static directory for CSS/JS
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
