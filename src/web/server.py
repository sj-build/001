"""FastAPI web server for SJ Home Agent."""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.app.config import get_settings
from src.app.paths import ensure_dirs
from src.storage.db import init_db
from src.storage.dao import ConversationDAO, SourceItemDAO, SourceItem, BundleDAO
from src.search.bm25 import search as bm25_search
from src.search.bundle import create_bundle
from src.morning.digest import build_digest
from src.thinking.agent import think, ThinkingInput
from src.tagging.classifier import classify
from src.ingest.dedupe import make_source_item_id

logger = logging.getLogger("sj_home_agent.web")

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="SJ Home Agent")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


@app.on_event("startup")
async def startup():
    ensure_dirs()
    init_db()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    dao = ConversationDAO()
    recent = dao.find_all(limit=5)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "recent_conversations": recent,
        "now": datetime.now().isoformat()[:10],
    })


@app.get("/morning", response_class=HTMLResponse)
async def morning_view(request: Request):
    dao = SourceItemDAO()
    items = dao.find_all(limit=50)

    # Rank and split
    from src.morning.rank import rank_items
    ranked = rank_items(items)
    top3 = ranked[:3]
    rest = ranked[3:]

    # Categorize rest
    categories: dict[str, list] = {}
    for item in rest:
        cat, _ = classify(item.title, item.summary or "")
        group = categories.get(cat, [])
        categories[cat] = [*group, item]

    return templates.TemplateResponse("morning.html", {
        "request": request,
        "top3": top3,
        "categories": categories,
        "total": len(ranked),
        "date": datetime.now().isoformat()[:10],
    })


@app.post("/morning/build", response_class=HTMLResponse)
async def morning_build(request: Request):
    markdown = build_digest()
    return templates.TemplateResponse("morning.html", {
        "request": request,
        "top3": [],
        "categories": {},
        "total": 0,
        "date": datetime.now().isoformat()[:10],
        "flash": "Morning digest built and saved to Obsidian.",
        "digest_preview": markdown[:1000],
    })


@app.post("/morning/add", response_class=HTMLResponse)
async def morning_add_item(
    request: Request,
    title: str = Form(...),
    url: str = Form(""),
    text: str = Form(""),
):
    """Manually add an item to the morning sources."""
    dao = SourceItemDAO()
    now = datetime.now().isoformat()
    item_id = make_source_item_id("manual", url or title)

    category, tags = classify(title, text)
    importance = 1.0 if category.startswith("Work/") else 0.5

    item = SourceItem(
        id=item_id,
        source="manual",
        title=title,
        url=url,
        published_at=now,
        fetched_at=now,
        summary=text[:500] if text else None,
        tags=",".join(tags),
        importance=importance,
        status="new",
    )
    dao.upsert(item)

    return RedirectResponse(url="/morning", status_code=303)


@app.get("/search", response_class=HTMLResponse)
async def search_view(
    request: Request,
    tag: Optional[str] = None,
    q: Optional[str] = None,
    days: Optional[int] = None,
):
    results = []
    query = ""

    if tag or q:
        query_parts = []
        if tag:
            query_parts.append(tag)
        if q:
            query_parts.append(q)
        query = " ".join(query_parts)
        results = bm25_search(query, days=days)

    return templates.TemplateResponse("search.html", {
        "request": request,
        "results": results,
        "query": query,
        "tag": tag or "",
        "q": q or "",
        "days": days or "",
    })


@app.post("/bundle", response_class=HTMLResponse)
async def bundle_create(
    request: Request,
    query: str = Form(...),
    top: int = Form(7),
):
    bundle = create_bundle(query, top_n=top)
    return templates.TemplateResponse("bundles.html", {
        "request": request,
        "bundle": bundle,
    })


@app.get("/bundles", response_class=HTMLResponse)
async def bundles_list(request: Request):
    dao = BundleDAO()
    bundles = dao.find_all(limit=20)
    return templates.TemplateResponse("bundles.html", {
        "request": request,
        "bundles": bundles,
        "bundle": None,
    })


@app.get("/ask", response_class=HTMLResponse)
async def ask_view(request: Request):
    return templates.TemplateResponse("ask.html", {
        "request": request,
        "result": None,
    })


@app.post("/ask", response_class=HTMLResponse)
async def ask_submit(
    request: Request,
    url: str = Form(""),
    text: str = Form(""),
    question: str = Form(""),
):
    input_data = ThinkingInput(
        url=url if url else None,
        text=text if text else None,
        question=question,
    )
    result = think(input_data)

    return templates.TemplateResponse("ask.html", {
        "request": request,
        "result": result,
        "input_url": url,
        "input_text": text,
        "input_question": question,
    })
