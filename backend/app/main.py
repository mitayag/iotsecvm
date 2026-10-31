from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from .labs import list_labs, load_lab, summary
from .runner import run_action
from .settings import ALLOW_MUTATIONS, FRONTEND_DIR, version

app = FastAPI(
    title="HAU IoT Security Lab Manager",
    version=version(),
    docs_url="/api/docs",
    redoc_url=None,
)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": version(),
        "actions_enabled": ALLOW_MUTATIONS,
    }


@app.get("/api/labs")
def labs() -> dict:
    return {"labs": list_labs(), "actions_enabled": ALLOW_MUTATIONS}


@app.get("/api/labs/{lab_id}")
def lab_detail(lab_id: str) -> dict:
    manifest = load_lab(lab_id)
    detail = summary(manifest)
    detail["containers"] = manifest.get("containers", [])
    detail["networks"] = manifest.get("networks", {})
    detail["reset"] = manifest.get("reset", {})
    detail["safety"] = manifest.get("safety", {})
    return detail


@app.post("/api/labs/{lab_id}/actions/{action}")
def lab_action(lab_id: str, action: str) -> dict:
    return run_action(lab_id, action)


if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    @app.get("/")
    def missing_frontend() -> dict:
        raise HTTPException(status_code=404, detail="frontend not installed")
