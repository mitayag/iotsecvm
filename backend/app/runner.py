import subprocess
import threading

from fastapi import HTTPException

from .labs import load_lab
from .settings import ACTION_TIMEOUT_SECONDS, ALLOW_MUTATIONS, ROOT, USE_SUDO

ACTION_SCRIPTS = {
    "start": "lab-start.sh",
    "stop": "lab-stop.sh",
    "reset": "lab-reset.sh",
}

_ACTION_LOCK = threading.Lock()


def run_action(lab_id: str, action: str) -> dict:
    if action not in ACTION_SCRIPTS:
        raise HTTPException(status_code=404, detail="unknown action")
    if not ALLOW_MUTATIONS:
        raise HTTPException(
            status_code=403,
            detail="lab actions are disabled; use the scripts on the student VM",
        )

    manifest = load_lab(lab_id)
    if manifest.get("status") != "implemented":
        raise HTTPException(status_code=409, detail="lab is planned, not implemented")

    script = ROOT / "scripts" / ACTION_SCRIPTS[action]
    if not script.is_file():
        raise HTTPException(status_code=500, detail="lifecycle script is missing")

    command = [str(script), lab_id]
    if action == "reset":
        command.append("--yes")
    if USE_SUDO:
        command = ["sudo", "-n", *command]

    if not _ACTION_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="another lab action is running")
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=ACTION_TIMEOUT_SECONDS,
            check=False,
            env=None,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="lab action timed out") from exc
    finally:
        _ACTION_LOCK.release()

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"{action} failed",
                "returncode": result.returncode,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:],
            },
        )

    return {
        "lab": lab_id,
        "action": action,
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }
