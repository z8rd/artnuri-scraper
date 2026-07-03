from fastapi import FastAPI, BackgroundTasks, Query, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import re
import pandas as pd
import io
import shutil
from typing import List, Optional, Dict
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

# Active orchestrators keyed by client_id (Session Isolation)
client_orchestrators: Dict[str, Orchestrator] = {}

def get_orchestrator(client_id: str) -> Orchestrator:
    # Strict Regex Validation for Client ID to prevent Path Traversal
    if not client_id or not re.match(r"^[a-zA-Z0-9_-]{1,100}$", client_id):
        raise HTTPException(status_code=400, detail="올바르지 않은 클라이언트 세션 ID 형식입니다.")
    
    if client_id not in client_orchestrators:
        # Create client-specific data directory
        client_dir = os.path.join(DATA_DIR, client_id)
        os.makedirs(client_dir, exist_ok=True)
        client_orchestrators[client_id] = Orchestrator(data_dir=client_dir)
        
    return client_orchestrators[client_id]

# Background task wrapper
async def run_orchestrator_task(client_id: str, keywords: List[str]):
    try:
        orch = get_orchestrator(client_id)
        await orch.start_scraping(keywords)
    except Exception as e:
        print(f"Orchestrator task error: {e}")

@app.post("/api/scrape")
async def start_scrape(
    background_tasks: BackgroundTasks, 
    client_id: str = "default",
    keywords: Optional[List[str]] = Query(None)
):
    orch = get_orchestrator(client_id)
    if orch.is_running:
        raise HTTPException(status_code=400, detail="이미 크롤링이 진행 중입니다.")
    
    # Sanitize keywords to prevent any command injection or scripts
    clean_keywords = []
    if keywords:
        for kw in keywords:
            clean_kw = re.sub(r"[^\w\s가-힣-]", "", kw).strip()
            if clean_kw:
                clean_keywords.append(clean_kw)
    
    if not clean_keywords:
        clean_keywords = ["음악", "클래식", "작곡", "미디어아트"]
        
    background_tasks.add_task(run_orchestrator_task, client_id, clean_keywords)
    return {"status": "started", "keywords": clean_keywords}

@app.get("/api/status")
async def get_status(client_id: str = "default"):
    orch = get_orchestrator(client_id)
    return orch.get_status()

@app.get("/api/results")
async def get_results(
    client_id: str = "default",
    keyword: Optional[str] = None,
    state: Optional[str] = None,
    host: Optional[str] = None,
    search: Optional[str] = None
):
    orch = get_orchestrator(client_id)
    results = orch.load_last_results()
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
        
    # General text search (Sanitized query search)
    if search:
        search_lower = re.sub(r"[^\w\s가-힣-]", "", search).lower()
        filtered = [
            x for x in filtered 
            if search_lower in x.get("title", "").lower() 
            or search_lower in x.get("description", "").lower()
            or search_lower in x.get("host", "").lower()
        ]
        
    return filtered

@app.get("/api/export")
async def export_results(format: str = "csv", client_id: str = "default"):
    orch = get_orchestrator(client_id)
    results = orch.load_last_results()
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

@app.delete("/api/results")
async def delete_results(client_id: str = "default"):
    orch = get_orchestrator(client_id)
    if orch.is_running:
        raise HTTPException(status_code=400, detail="수집이 진행 중일 때는 데이터를 삭제할 수 없습니다.")
    
    client_dir = os.path.join(DATA_DIR, client_id)
    if os.path.exists(client_dir):
        shutil.rmtree(client_dir)
        
    # Reset in-memory results for this client
    if client_id in client_orchestrators:
        del client_orchestrators[client_id]
        
    return {"status": "deleted"}

# Serve index.html directly on root
@app.get("/")
async def read_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Artnuri Scraper Service backend is running. Frontend static/index.html is missing."}

# Mount static directory for CSS/JS
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
