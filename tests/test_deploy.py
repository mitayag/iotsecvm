from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "scripts" / "deploy.sh"
ROLLBACK = ROOT / "scripts" / "rollback.sh"


def deploy(dest: Path, version: str) -> None:
    result = __import__("subprocess").run(
        [
            str(DEPLOY),
            "--source",
            str(ROOT),
            "--version",
            version,
            "--dest",
            str(dest),
            "--skip-verify",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def rollback(dest: Path, version: str = "") -> None:
    command = [str(ROLLBACK), "--dest", str(dest)]
    if version:
        command.append(version)
    result = __import__("subprocess").run(
        command, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_versioned_deploy_and_rollback(tmp_path: Path) -> None:
    dest = tmp_path / "iotlab"
    evidence = dest / "var" / "evidence" / "week01"
    evidence.mkdir(parents=True)
    (evidence / "student-note.txt").write_text("preserve me\n")

    deploy(dest, "1.0.0")
    assert (dest / "current").is_symlink()
    assert (dest / "current").resolve() == (dest / "releases" / "1.0.0").resolve()
    assert (dest / "current" / "var" / "evidence" / "week01" / "student-note.txt").is_file()

    deploy(dest, "1.0.1")
    assert (dest / "current").resolve() == (dest / "releases" / "1.0.1").resolve()
    assert (dest / "var" / "deploy" / "previous").read_text().strip() == "1.0.0"

    rollback(dest)
    assert (dest / "current").resolve() == (dest / "releases" / "1.0.0").resolve()
    assert (dest / "var" / "deploy" / "previous").read_text().strip() == "1.0.1"
    assert (dest / "current" / "var" / "evidence" / "week01" / "student-note.txt").is_file()

    history = (dest / "var" / "deploy" / "history.log").read_text()
    assert "deployed 1.0.0" in history
    assert "deployed 1.0.1" in history
    assert "rollback 1.0.1 -> 1.0.0" in history


def test_deploy_refuses_duplicate_without_force(tmp_path: Path) -> None:
    dest = tmp_path / "iotlab"
    deploy(dest, "2.0.0")
    result = __import__("subprocess").run(
        [
            str(DEPLOY),
            "--source",
            str(ROOT),
            "--version",
            "2.0.0",
            "--dest",
            str(dest),
            "--skip-verify",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "already exists" in result.stderr
