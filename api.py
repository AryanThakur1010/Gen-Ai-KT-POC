"""
KT Pipeline Dashboard — FastAPI Backend
Place this file at the ROOT of your GEN-AI-KT-POC project (same level as main.py)
Run: uvicorn api:app --reload --port 8000
"""

import asyncio
import json
import os
import re
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

# ─── Path setup ───────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    INPUT_DIR, OUTPUT_MD_DIR, CHROMA_PATH,
    MAX_CONTEXT_LEVELS, TAG_COUNT
)
from modules.docx_extractor import extract_structured_content
from modules.hierarchical_chunker import AdaptiveHierarchicalChunker
from modules.tree_manager import TreeManager
from modules.tag_extractor import extract_tags
from modules.obsidian_generator import generate_markdown_safe, create_frontmatter
from modules.embedding_manager import store_chunk
from modules.hybrid_linker import HybridLinker, generate_backlinks_section
from modules.utils.utils import strip_images

# ─── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="KT Pipeline Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Directories ──────────────────────────────────────────────────────────────
OBSIDIAN_VAULT_DIR = "output/obsidian_vault"
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_MD_DIR, exist_ok=True)
os.makedirs(OBSIDIAN_VAULT_DIR, exist_ok=True)

# ─── Global state (thread-safe) ───────────────────────────────────────────────
state_lock = threading.Lock()
pipeline_running = False

# doc_states: keyed by filename (e.g. "API-Guide.docx")
doc_states: Dict[str, Dict[str, Any]] = {}

# draft_decisions: keyed by filename → "pending" | "approved" | "rejected"
draft_decisions: Dict[str, str] = {}

# original texts saved during Phase 1
original_texts: Dict[str, str] = {}

# ─── WebSocket log broadcasting ───────────────────────────────────────────────
ws_clients: List[WebSocket] = []
ws_lock = threading.Lock()
_event_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_loop():
    global _event_loop
    if _event_loop is None or _event_loop.is_closed():
        try:
            _event_loop = asyncio.get_running_loop()
        except RuntimeError:
            _event_loop = asyncio.new_event_loop()
    return _event_loop


def push_log(level: str, message: str, phase: int = 0):
    """Broadcast a log entry to all connected WebSocket clients from any thread."""
    entry = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "level": level,
        "message": message,
        "phase": phase,
    }
    try:
        loop = _get_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(_broadcast(entry), loop)
    except Exception:
        pass


async def _broadcast(entry: dict):
    dead = []
    for ws in list(ws_clients):
        try:
            await ws.send_json(entry)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in ws_clients:
            ws_clients.remove(ws)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _set_state(name: str, **kwargs):
    with state_lock:
        if name not in doc_states:
            doc_states[name] = {"name": name}
        doc_states[name].update(kwargs)


def _discover_existing_docs():
    """Load state for files already in input dir and output dir on startup."""
    for f in os.listdir(INPUT_DIR):
        if f.endswith((".docx", ".doc")):
            path = os.path.join(INPUT_DIR, f)
            title = os.path.splitext(f)[0]
            md_path = os.path.join(OUTPUT_MD_DIR, f"{title}.md")
            exists = os.path.exists(md_path)
            size_mb = round(os.path.getsize(path) / 1024 / 1024, 2)

            with state_lock:
                if f not in doc_states:
                    doc_states[f] = {
                        "name": f,
                        "title": title,
                        "size_mb": size_mb,
                        "status": "done" if exists else "queued",
                        "phase": 3 if exists else 0,
                        "progress": 100 if exists else 0,
                        "error": None,
                        "blocks": 0,
                        "chunks": 0,
                        "tags": [],
                        "links": 0,
                        "unresolved_links": 0,
                        "draft_status": draft_decisions.get(f, "pending" if exists else "none"),
                        "uploaded_at": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M"),
                    }


_discover_existing_docs()


# ─── Quality calculation ───────────────────────────────────────────────────────
def calculate_quality(md_content: str, tags: List[str]) -> Dict[str, Any]:
    """Parse generated markdown and produce quality scores (total out of 100)."""
    lines = md_content.split("\n")

    # Frontmatter (10 pts)
    has_frontmatter = md_content.startswith("---")
    fm_score = 10 if has_frontmatter else 0

    # Headings (20 pts)
    headings = [l for l in lines if re.match(r"^#{1,6} ", l)]
    h2_plus = [l for l in headings if re.match(r"^#{2,6} ", l)]
    heading_score = min(20, len(h2_plus) * 4)

    # Wiki links (25 pts)
    wiki_links = re.findall(r"\[\[.+?\]\]", md_content)
    unresolved = [l for l in wiki_links if "unresolved" in l.lower() or "missing" in l.lower()]
    link_score = min(25, len(wiki_links) * 2)
    link_score = max(0, link_score - len(unresolved) * 3)

    # Content depth (20 pts)
    body = re.sub(r"^---[\s\S]+?---\n", "", md_content)
    words = len(body.split())
    content_score = min(20, words // 50)

    # Tags (10 pts)
    tag_score = min(10, len(tags) * 3)

    # Rich elements: code blocks, tables, blockquotes (15 pts)
    code_blocks = len(re.findall(r"```", md_content)) // 2
    tables = len([l for l in lines if l.strip().startswith("|")])
    blockquotes = len([l for l in lines if l.strip().startswith(">")])
    structure_score = min(15, code_blocks * 4 + (1 if tables > 0 else 0) * 4 + (1 if blockquotes > 0 else 0) * 3)

    total = fm_score + heading_score + link_score + content_score + tag_score + structure_score

    return {
        "total": min(100, round(total)),
        "breakdown": {
            "frontmatter": fm_score,
            "headings": round(heading_score),
            "links": round(link_score),
            "content_depth": round(content_score),
            "tags": round(tag_score),
            "rich_elements": round(structure_score),
        },
        "stats": {
            "word_count": words,
            "heading_count": len(headings),
            "link_count": len(wiki_links),
            "unresolved_count": len(unresolved),
            "code_blocks": code_blocks,
            "has_tables": tables > 0,
            "has_blockquotes": blockquotes > 0,
        },
    }


# ─── Pipeline execution (runs in background thread) ───────────────────────────
def _run_pipeline_for_doc(filename: str):
    """Execute all 3 phases for a single document, updating state throughout."""
    global pipeline_running
    title = os.path.splitext(filename)[0]
    doc_path = os.path.join(INPUT_DIR, filename)

    try:
        # ── Phase 1: Extract & Chunk ──────────────────────────────────────────
        push_log("info", f"[{filename}] Phase 1 started — extracting structure", 1)
        _set_state(filename, status="processing", phase=1, progress=5, error=None)

        structured_content = extract_structured_content(doc_path)
        blocks = len(structured_content)
        push_log("ok", f"[{filename}] Extracted {blocks} content blocks", 1)
        _set_state(filename, blocks=blocks, progress=20)

        # Save original text for draft panel
        original = "\n\n".join(
            item.text for item in structured_content
            if item.type in ("heading", "paragraph", "table") and item.text.strip()
        )
        original_texts[filename] = original

        chunker = AdaptiveHierarchicalChunker(structured_content, title)
        chunks = chunker.create_chunks()
        push_log("ok", f"[{filename}] Created {len(chunks)} adaptive chunks", 1)
        _set_state(filename, progress=35)

        full_text = " ".join(strip_images(c.get_text_without_images()) for c in chunks[:5])
        tags = extract_tags(full_text[:5000], title)
        push_log("ok", f"[{filename}] Tags extracted: {', '.join(tags)}", 1)
        _set_state(filename, tags=tags, chunks=len(chunks), progress=45)

        # ── Phase 2: Markdown Generation & Embedding ──────────────────────────
        push_log("info", f"[{filename}] Phase 2 started — generating markdown + embeddings", 2)
        _set_state(filename, phase=2, progress=50)

        tree_manager = TreeManager(chunks, max_levels=MAX_CONTEXT_LEVELS)
        all_headings = tree_manager.get_all_headings()
        markdown_sections = []

        total_chunks = sum(1 for c in chunks if c.level > 0)
        processed = 0

        for chunk in chunks:
            if chunk.level == 0:
                continue
            context = tree_manager.get_minimal_context(chunk.chunk_id)
            md = generate_markdown_safe(chunk, context, all_headings)
            markdown_sections.append(md)
            store_chunk(chunk, title, tags, context.get("breadcrumb", ""))
            processed += 1
            progress = 50 + int((processed / max(1, total_chunks)) * 30)
            _set_state(filename, progress=progress)

        frontmatter = create_frontmatter(title, tags, chunks[0].chunk_id if chunks else "root")
        full_markdown = frontmatter + "\n\n" + "\n\n".join(markdown_sections)

        md_path = os.path.join(OUTPUT_MD_DIR, f"{title}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(full_markdown)

        push_log("ok", f"[{filename}] Saved {len(markdown_sections)} sections → {md_path}", 2)
        _set_state(filename, phase=2, progress=80)

        # ── Phase 3: Intelligent Linking ──────────────────────────────────────
        push_log("info", f"[{filename}] Phase 3 started — semantic link generation", 3)
        _set_state(filename, phase=3, progress=82)

        all_chunks_flat = [c for c in chunks if c.level > 0]
        chunk_map = {c.chunk_id: c for c in all_chunks_flat}
        linker = HybridLinker(chunk_map, all_chunks_flat)

        all_links: set = set()
        for chunk in all_chunks_flat:
            links = linker.find_links(chunk, tags, max_links=8)
            all_links.update(links)

        backlinks_md = generate_backlinks_section(list(all_links), linker)
        if backlinks_md:
            with open(md_path, "a", encoding="utf-8") as f:
                f.write(backlinks_md)

        push_log("ok", f"[{filename}] Generated {len(all_links)} semantic links (Tier 1+2+3)", 3)

        # ── Quality calculation ───────────────────────────────────────────────
        with open(md_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        quality = calculate_quality(md_content, tags)
        unresolved = quality["stats"]["unresolved_count"]

        _set_state(
            filename,
            status="done",
            phase=3,
            progress=100,
            links=len(all_links),
            unresolved_links=unresolved,
            quality=quality,
            draft_status="pending",
        )
        draft_decisions[filename] = "pending"
        push_log("ok", f"[{filename}] ✓ Complete — quality score: {quality['total']}/100", 3)

    except Exception as exc:
        import traceback
        push_log("error", f"[{filename}] FAILED: {exc}", 0)
        traceback.print_exc()
        _set_state(filename, status="failed", error=str(exc), progress=0)
    finally:
        with state_lock:
            global pipeline_running
            pipeline_running = False


def _run_pipeline_background(filenames: List[str]):
    """Run pipeline for multiple files sequentially in a background thread."""
    global pipeline_running
    for f in filenames:
        _run_pipeline_for_doc(f)
    pipeline_running = False


# ─── WebSocket endpoint ────────────────────────────────────────────────────────
@app.websocket("/ws/logs")
async def ws_logs(ws: WebSocket):
    global _event_loop
    _event_loop = asyncio.get_running_loop()
    await ws.accept()
    ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        if ws in ws_clients:
            ws_clients.remove(ws)


# ─── Document endpoints ────────────────────────────────────────────────────────
@app.get("/api/documents")
def get_documents():
    _discover_existing_docs()
    with state_lock:
        return list(doc_states.values())


@app.post("/api/documents/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    uploaded = []
    for file in files:
        if not (file.filename.endswith(".docx") or file.filename.endswith(".doc")):
            raise HTTPException(400, f"Only .docx/.doc supported: {file.filename}")

        dest = os.path.join(INPUT_DIR, file.filename)
        content = await file.read()
        with open(dest, "wb") as f:
            f.write(content)

        size_mb = round(len(content) / 1024 / 1024, 2)
        title = os.path.splitext(file.filename)[0]
        _set_state(
            name=file.filename,
            title=title,
            size_mb=size_mb,
            status="queued",
            phase=0,
            progress=0,
            error=None,
            blocks=0,
            chunks=0,
            tags=[],
            links=0,
            unresolved_links=0,
            draft_status="none",
            uploaded_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        push_log("info", f"Uploaded: {file.filename} ({size_mb} MB)", 0)
        uploaded.append(file.filename)

    return {"uploaded": uploaded}


@app.delete("/api/documents/{filename}")
def delete_document(filename: str):
    path = os.path.join(INPUT_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
    md_path = os.path.join(OUTPUT_MD_DIR, f"{os.path.splitext(filename)[0]}.md")
    if os.path.exists(md_path):
        os.remove(md_path)
    with state_lock:
        doc_states.pop(filename, None)
    push_log("warn", f"Removed: {filename}", 0)
    return {"deleted": filename}


# ─── Pipeline endpoints ────────────────────────────────────────────────────────
@app.post("/api/pipeline/run")
def run_pipeline():
    global pipeline_running
    if pipeline_running:
        raise HTTPException(409, "Pipeline already running")

    with state_lock:
        queued = [name for name, s in doc_states.items() if s.get("status") in ("queued", "failed")]

    if not queued:
        raise HTTPException(400, "No queued documents")

    pipeline_running = True
    push_log("info", f"Pipeline started — {len(queued)} document(s) queued", 0)
    t = threading.Thread(target=_run_pipeline_background, args=(queued,), daemon=True)
    t.start()
    return {"started": queued}


@app.post("/api/pipeline/reprocess/{filename}")
def reprocess_document(filename: str):
    global pipeline_running
    if pipeline_running:
        raise HTTPException(409, "Pipeline already running")

    path = os.path.join(INPUT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "Document not found in input directory")

    _set_state(filename, status="queued", phase=0, progress=0, error=None,
               draft_status="none", links=0, unresolved_links=0)
    pipeline_running = True
    push_log("warn", f"Reprocess requested: {filename}", 0)
    t = threading.Thread(target=_run_pipeline_for_doc, args=(filename,), daemon=True)
    t.start()
    return {"reprocessing": filename}


@app.get("/api/pipeline/status")
def pipeline_status():
    with state_lock:
        docs = list(doc_states.values())
    processing = next((d for d in docs if d.get("status") == "processing"), None)
    return {
        "running": pipeline_running,
        "active_document": processing.get("name") if processing else None,
        "active_phase": processing.get("phase") if processing else None,
        "queued": sum(1 for d in docs if d.get("status") == "queued"),
        "processing": sum(1 for d in docs if d.get("status") == "processing"),
        "done": sum(1 for d in docs if d.get("status") == "done"),
        "failed": sum(1 for d in docs if d.get("status") == "failed"),
    }


# ─── Cache endpoint ────────────────────────────────────────────────────────────
@app.delete("/api/cache")
def clear_cache():
    if pipeline_running:
        raise HTTPException(409, "Stop pipeline before clearing cache")
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        client.delete_collection("confluence_notes_v3")
        push_log("warn", "ChromaDB cache cleared — all embeddings removed", 0)
        return {"cleared": True, "path": CHROMA_PATH}
    except Exception as e:
        push_log("error", f"Cache clear failed: {e}", 0)
        raise HTTPException(500, str(e))


# ─── Obsidian endpoint ─────────────────────────────────────────────────────────
@app.get("/api/obsidian/open/{filename}")
def open_in_obsidian(filename: str):
    title = os.path.splitext(filename)[0]
    vault_name = "KT-Vault"
    obsidian_url = f"obsidian://open?vault={vault_name}&file={title}"
    push_log("info", f"Open in Obsidian → {obsidian_url}", 0)
    return {"url": obsidian_url, "vault": vault_name, "file": title}


# ─── Export endpoint ───────────────────────────────────────────────────────────
@app.get("/api/export/unresolved")
def export_unresolved():
    results = []
    for name, state in doc_states.items():
        if state.get("unresolved_links", 0) > 0:
            md_path = os.path.join(OUTPUT_MD_DIR, f"{os.path.splitext(name)[0]}.md")
            unresolved_refs = []
            if os.path.exists(md_path):
                with open(md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                unresolved_refs = re.findall(r"\[\[([^\]]+)\]\]", content)[:20]
            results.append({
                "document": name,
                "unresolved_count": state.get("unresolved_links", 0),
                "references": unresolved_refs,
            })
    push_log("ok", f"Exported unresolved links — {len(results)} documents affected", 0)
    return {"documents": results, "exported_at": datetime.now().isoformat()}


# ─── Draft endpoints ───────────────────────────────────────────────────────────
@app.get("/api/drafts")
def get_drafts():
    drafts = []
    for name, state in doc_states.items():
        if state.get("draft_status") in ("pending", "approved", "rejected"):
            title = os.path.splitext(name)[0]
            md_path = os.path.join(OUTPUT_MD_DIR, f"{title}.md")
            drafts.append({
                "filename": name,
                "title": title,
                "draft_status": state.get("draft_status", "pending"),
                "tags": state.get("tags", []),
                "quality": state.get("quality", {}),
                "links": state.get("links", 0),
                "has_markdown": os.path.exists(md_path),
                "in_vault": os.path.exists(os.path.join(OBSIDIAN_VAULT_DIR, f"{title}.md")),
            })
    return drafts


@app.get("/api/drafts/{filename}/original")
def get_draft_original(filename: str):
    if filename not in original_texts:
        # Try to re-extract if not in memory
        path = os.path.join(INPUT_DIR, filename)
        if not os.path.exists(path):
            raise HTTPException(404, "Source document not found")
        try:
            structured = extract_structured_content(path)
            text = "\n\n".join(
                item.text for item in structured
                if item.type in ("heading", "paragraph", "table") and item.text.strip()
            )
            original_texts[filename] = text
        except Exception as e:
            raise HTTPException(500, f"Could not extract text: {e}")
    return {"filename": filename, "content": original_texts[filename]}


@app.get("/api/drafts/{filename}/markdown")
def get_draft_markdown(filename: str):
    title = os.path.splitext(filename)[0]
    md_path = os.path.join(OUTPUT_MD_DIR, f"{title}.md")
    if not os.path.exists(md_path):
        raise HTTPException(404, "Markdown not generated yet")
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"filename": filename, "title": title, "content": content}


@app.post("/api/drafts/{filename}/approve")
def approve_draft(filename: str):
    title = os.path.splitext(filename)[0]
    md_path = os.path.join(OUTPUT_MD_DIR, f"{title}.md")
    if not os.path.exists(md_path):
        raise HTTPException(404, "Markdown not found")

    dest = os.path.join(OBSIDIAN_VAULT_DIR, f"{title}.md")
    shutil.copy2(md_path, dest)
    _set_state(filename, draft_status="approved")
    draft_decisions[filename] = "approved"
    push_log("ok", f"Draft approved: {filename} → {dest}", 0)
    return {"approved": filename, "vault_path": dest}


@app.post("/api/drafts/{filename}/reject")
def reject_draft(filename: str):
    _set_state(filename, draft_status="rejected")
    draft_decisions[filename] = "rejected"
    push_log("warn", f"Draft rejected: {filename}", 0)
    return {"rejected": filename}


@app.post("/api/drafts/{filename}/save-edit")
async def save_draft_edit(filename: str, body: dict):
    """Save user edits to the generated markdown."""
    title = os.path.splitext(filename)[0]
    md_path = os.path.join(OUTPUT_MD_DIR, f"{title}.md")
    content = body.get("content", "")
    if not content:
        raise HTTPException(400, "Content cannot be empty")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)
    push_log("info", f"Draft edited and saved: {filename}", 0)
    return {"saved": filename}


# ─── Quality endpoints ─────────────────────────────────────────────────────────
@app.get("/api/quality")
def get_all_quality():
    results = []
    for name, state in doc_states.items():
        if state.get("status") == "done":
            title = os.path.splitext(name)[0]
            md_path = os.path.join(OUTPUT_MD_DIR, f"{title}.md")
            if os.path.exists(md_path):
                with open(md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                quality = calculate_quality(content, state.get("tags", []))
                _set_state(name, quality=quality)
                results.append({
                    **state,
                    "quality": quality,
                })
    return results


@app.get("/api/quality/{filename}")
def get_quality(filename: str):
    title = os.path.splitext(filename)[0]
    md_path = os.path.join(OUTPUT_MD_DIR, f"{title}.md")
    if not os.path.exists(md_path):
        raise HTTPException(404, "Markdown not found — process the document first")
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    state = doc_states.get(filename, {})
    quality = calculate_quality(content, state.get("tags", []))
    return {"filename": filename, "title": title, "quality": quality, **state}


@app.get("/api/stats")
def get_stats():
    with state_lock:
        docs = list(doc_states.values())
    done = [d for d in docs if d.get("status") == "done"]
    qualities = [d.get("quality", {}).get("total", 0) for d in done if d.get("quality")]
    avg_quality = round(sum(qualities) / len(qualities)) if qualities else 0
    return {
        "total_documents": len(docs),
        "done": len(done),
        "processing": sum(1 for d in docs if d.get("status") == "processing"),
        "queued": sum(1 for d in docs if d.get("status") == "queued"),
        "failed": sum(1 for d in docs if d.get("status") == "failed"),
        "total_chunks": sum(d.get("chunks", 0) for d in docs),
        "total_links": sum(d.get("links", 0) for d in docs),
        "unresolved_links": sum(d.get("unresolved_links", 0) for d in docs),
        "avg_quality": avg_quality,
        "pending_drafts": sum(1 for d in docs if d.get("draft_status") == "pending"),
        "pipeline_running": pipeline_running,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)