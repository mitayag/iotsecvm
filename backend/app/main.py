from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from backend.helper.client import HelperClient, HelperError

from .deps import get_helper
from .labs import detail, instructions, list_labs, load_lab
from .operations import get_evidence, get_status, read_evidence, run_action
from .settings import Settings, get_settings

settings = get_settings()

app = FastAPI(
    title="HAU IoT Security Lab Manager",
    version=settings.version,
    docs_url="/api/docs",
    redoc_url=None,
)


def _helper_state(settings: Settings) -> dict:
    if settings.helper_socket is None:
        return {
            "helper_available": False,
            "helper_version": None,
            "helper_error": "helper socket is not configured",
        }
    try:
        payload = HelperClient(settings.helper_socket, timeout=2).health()
    except HelperError as exc:
        return {
            "helper_available": False,
            "helper_version": None,
            "helper_error": exc.message,
        }
    return {
        "helper_available": True,
        "helper_version": payload.get("helper_version"),
        "helper_error": None,
    }


@app.get("/api/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    helper_state = _helper_state(settings)
    return {
        "status": "ok",
        "version": settings.version,
        "actions_enabled": settings.enable_actions
        and helper_state["helper_available"],
        "helper": helper_state,
    }


@app.get("/api/labs")
def labs(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "labs": list_labs(settings),
        "actions_enabled": settings.enable_actions,
    }


@app.get("/api/labs/{lab_id}")
def lab_detail(lab_id: str, settings: Settings = Depends(get_settings)) -> dict:
    return detail(settings, load_lab(settings, lab_id))


@app.get("/api/labs/{lab_id}/instructions")
def lab_instructions(
    lab_id: str, settings: Settings = Depends(get_settings)
) -> dict:
    return instructions(settings, lab_id)


@app.get("/api/labs/{lab_id}/status")
def lab_status(
    lab_id: str,
    settings: Settings = Depends(get_settings),
    helper: HelperClient | None = Depends(get_helper),
) -> dict:
    return get_status(helper, settings, lab_id)


@app.post("/api/labs/{lab_id}/actions/{action}")
def lab_action(
    lab_id: str,
    action: str,
    settings: Settings = Depends(get_settings),
    helper: HelperClient | None = Depends(get_helper),
) -> dict:
    return run_action(helper, settings, lab_id, action)


@app.get("/api/labs/{lab_id}/evidence")
def lab_evidence(
    lab_id: str, settings: Settings = Depends(get_settings)
) -> dict:
    return get_evidence(settings, lab_id)


@app.get("/api/labs/{lab_id}/evidence/{filename}")
def lab_evidence_file(
    lab_id: str, filename: str, settings: Settings = Depends(get_settings)
) -> dict:
    return read_evidence(settings, lab_id, filename)


if settings.frontend_dir.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(settings.frontend_dir), html=True),
        name="frontend",
    )
else:
    @app.get("/")
    def missing_frontend() -> dict:
        raise HTTPException(status_code=404, detail="frontend not installed")
