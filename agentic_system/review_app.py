from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .orchestrator import WorkflowOrchestrator


class ReviewRunRequest(BaseModel):
    requirement: str = Field(min_length=3, max_length=10_000)
    approved: bool = False
    repository_path: str | None = None


def create_review_app(output_directory: Path = Path("generated")) -> FastAPI:
    """Serve a local reviewer page for runs, assumptions, and validation evidence."""
    app = FastAPI(title="Agentic Engineering Review", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    def review_page() -> str:
        return REVIEW_PAGE

    @app.get("/api/run")
    def latest_run() -> dict:
        run_file = output_directory / "run.json"
        if not run_file.is_file():
            raise HTTPException(status_code=404, detail="No workflow run has been created yet.")
        return json.loads(run_file.read_text(encoding="utf-8"))

    @app.post("/api/runs")
    def create_run(request: ReviewRunRequest) -> dict:
        repository = Path(request.repository_path) if request.repository_path else None
        result = WorkflowOrchestrator(approved=request.approved).run(
            request.requirement,
            output_directory,
            repository,
        )
        output_directory.mkdir(parents=True, exist_ok=True)
        payload = result.to_dict()
        (output_directory / "run.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    return app


REVIEW_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Agentic Engineering Review</title>
<style>body{font-family:system-ui;max-width:900px;margin:2rem auto;padding:0 1rem;color:#172033}textarea{width:100%;height:7rem}button{padding:.55rem .8rem;margin:.5rem 0}pre{background:#f4f6f8;padding:1rem;white-space:pre-wrap;overflow:auto}label{display:block;margin:.5rem 0}</style>
</head><body><h1>Agentic Engineering Review</h1><p>Run a requirement, review assumptions and validation evidence, then approve before implementation artifacts are produced.</p>
<textarea id="requirement">Build a scalable URL shortener service with APIs, persistence, and analytics.</textarea>
<label><input id="approved" type="checkbox"> I approve the assumptions and plan</label><button onclick="run()">Run workflow</button><button onclick="loadRun()">Refresh latest run</button><pre id="result">No run loaded.</pre>
<script>const result=document.getElementById('result');async function loadRun(){const r=await fetch('/api/run');result.textContent=r.ok?JSON.stringify(await r.json(),null,2):await r.text()}async function run(){const r=await fetch('/api/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({requirement:document.getElementById('requirement').value,approved:document.getElementById('approved').checked})});result.textContent=JSON.stringify(await r.json(),null,2)}loadRun()</script>
</body></html>"""


app = create_review_app()
