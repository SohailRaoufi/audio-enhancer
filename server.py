import asyncio
import json
import shutil
import stat
import uuid
from pathlib import Path
from typing import Any, Dict, List
import zipfile
import uvicorn


import aiofiles
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from enhance_all_audios import AudioEnhancer
from job_manager import JobManager

app = FastAPI(title="Audio Enhancer Service")
job_manager = JobManager(base_dir=Path.cwd(), max_workers=1)

INDEX_PATH = Path(__file__).parent / "static" / "index.html"


def parse_bool(value: str) -> bool:
    """Interpret common truthy string values."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


async def save_upload_file(upload_file: UploadFile, destination: Path) -> None:
    """Persist an uploaded file to disk."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(destination, "wb") as out_file:
        while True:
            chunk = await upload_file.read(1024 * 1024)
            if not chunk:
                break
            await out_file.write(chunk)


def safe_extract_zip(zip_path: Path, extract_to: Path) -> List[str]:
    """Extract zip contents safely, preventing path traversal."""
    extracted: List[str] = []
    extract_to.mkdir(parents=True, exist_ok=True)
    base_path = extract_to.resolve()

    root_segments: Dict[str, int] = {}

    with zipfile.ZipFile(zip_path, "r") as archive:
        if not archive.namelist():
            raise ValueError("The uploaded archive is empty.")

        for member in archive.infolist():
            member_path = Path(member.filename)
            if member_path.name == "":
                continue  # skip invalid entries

            # Disallow absolute paths and parent traversal
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"Unsafe filename in zip: {member.filename}")

            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError("Symlinks are not allowed in the uploaded archive.")

            target_path = (extract_to / member_path).resolve()
            if not str(target_path).startswith(str(base_path)):
                raise ValueError(f"Unsafe extraction path for {member.filename}")

            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, open(target_path, "wb") as dest:
                shutil.copyfileobj(source, dest)

            # Exclude macOS metadata files from root_segments
            if member_path.name.startswith("._") or member_path.name in {".DS_Store", "Thumbs.db"}:
                continue

            extracted.append(str(target_path.relative_to(extract_to)))

            top_segment = member_path.parts[0] if member_path.parts else None
            if top_segment:
                root_segments[top_segment] = root_segments.get(top_segment, 0) + 1

    if not root_segments:
        top_name = zip_path.stem
    else:
        top_name = max(root_segments.items(), key=lambda item: item[1])[0]

    metadata_path = extract_to / "_archive_info.json"
    with open(metadata_path, "w", encoding="utf-8") as meta_file:
        json.dump({"root_name": top_name}, meta_file)

    return extracted


@app.on_event("startup")
async def startup_event() -> None:
    await job_manager.start()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await job_manager.shutdown()


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    if not INDEX_PATH.exists():
        raise HTTPException(status_code=500, detail="UI not found.")
    content = INDEX_PATH.read_text(encoding="utf-8")
    return HTMLResponse(content)


@app.post("/api/upload")
async def upload_zip(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form("dns64"),
    low_bitrate: str = Form("false"),
    suffix: str = Form(""),
    recursive: str = Form("false"),
    temp_dir: str = Form("tmp"),
    no_loudnorm: str = Form("false"),
) -> JSONResponse:
    allowed_models = {"dns48", "dns64", "master64"}
    if model not in allowed_models:
        raise HTTPException(status_code=400, detail=f"Unsupported model '{model}'.")

    low_bitrate_flag = parse_bool(low_bitrate)
    recursive_flag = parse_bool(recursive)
    no_loudnorm_flag = parse_bool(no_loudnorm)

    job_id = uuid.uuid4().hex
    base_dir = Path.cwd()
    uploads_dir = base_dir / "uploads" / job_id
    original_dir = uploads_dir / "original-audios"
    tmp_dir = uploads_dir / "tmp"
    outputs_dir = base_dir / "outputs" / job_id / "enhanced-audios"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    original_dir.mkdir(parents=True, exist_ok=True)
    upload_zip_path = uploads_dir / "input.zip"

    archive_info: Dict[str, Any] = {}
    try:
        await save_upload_file(file, upload_zip_path)
        await asyncio.to_thread(safe_extract_zip, upload_zip_path, original_dir)
        info_path = original_dir / "_archive_info.json"
        if info_path.exists():
            archive_info = json.loads(info_path.read_text(encoding="utf-8"))
    except zipfile.BadZipFile as exc:
        shutil.rmtree(uploads_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Invalid ZIP archive.") from exc
    except ValueError as exc:
        shutil.rmtree(uploads_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if upload_zip_path.exists():
            upload_zip_path.unlink(missing_ok=True)

    enhancer = AudioEnhancer(model_name=model, temp_dir=str(tmp_dir))
    audio_files = enhancer.find_audio_files(original_dir, recursive=recursive_flag)

    if not audio_files and not recursive_flag:
        audio_files = enhancer.find_audio_files(original_dir, recursive=True)
        if audio_files:
            recursive_flag = True

    if not audio_files:
        shutil.rmtree(uploads_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="No supported audio files found in archive.")

    relative_files = [
        str(Path(audio_file).relative_to(original_dir)) for audio_file in audio_files
    ]

    options: Dict[str, object] = {
        "model": model,
        "low_bitrate": low_bitrate_flag,
        "suffix": suffix,
        "recursive": recursive_flag,
        "requested_temp_dir": temp_dir,
        "no_loudnorm": no_loudnorm_flag,
    }

    output_zip = outputs_dir.parent / "enhanced-audios.zip"
    job = await job_manager.submit_job(
        job_id=job_id,
        options=options,
        original_dir=original_dir,
        temp_dir=tmp_dir,
        output_dir=outputs_dir,
        output_zip=output_zip,
        input_files=relative_files,
        archive_name=archive_info.get("root_name") or file.filename or job_id,
    )

    metadata = job.to_dict()
    scheme = "wss" if request.url.scheme == "https" else "ws"
    host = request.url.hostname or "localhost"
    if request.url.port and request.url.port not in (80, 443):
        host = f"{host}:{request.url.port}"
    ws_url = f"{scheme}://{host}/ws/{job_id}"

    response_payload = {
        "job_id": job_id,
        "status": metadata["status"],
        "ws_url": ws_url,
        "status_url": f"/api/jobs/{job_id}/status",
        "files_url": f"/api/jobs/{job_id}/files",
        "download_url": f"/api/jobs/{job_id}/download",
    }
    return JSONResponse(response_payload)


@app.get("/api/jobs/{job_id}/status")
async def job_status(job_id: str) -> JSONResponse:
    metadata = await job_manager.get_metadata(job_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JSONResponse(metadata)


@app.get("/api/jobs")
async def list_jobs() -> JSONResponse:
    jobs_dir = job_manager.jobs_dir
    if not jobs_dir.exists():
        return JSONResponse({"jobs": []})

    job_files = sorted(
        jobs_dir.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    jobs: List[Dict[str, Any]] = []
    for job_file in job_files:
        job_id = job_file.stem
        metadata = await job_manager.get_metadata(job_id)
        if not metadata:
            continue
        paths = metadata.get("paths", {})
        jobs.append({
            "job_id": job_id,
            "status": metadata.get("status"),
            "created_at": metadata.get("created_at"),
            "completed_at": metadata.get("completed_at"),
            "error": metadata.get("error"),
            "total_files": metadata.get("total_files"),
            "processed_files": metadata.get("processed_files"),
            "archive_name": metadata.get("archive_name", job_id),
            "download_url": f"/api/jobs/{job_id}/download",
            "output_dir": paths.get("output_dir"),
        })

    return JSONResponse({"jobs": jobs})


@app.get("/api/jobs/{job_id}/files")
async def job_files(job_id: str) -> JSONResponse:
    metadata = await job_manager.get_metadata(job_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    payload = {
        "job_id": job_id,
        "files": metadata.get("files", []),
        "results": metadata.get("results", {}),
        "status": metadata.get("status"),
    }
    return JSONResponse(payload)


@app.get("/api/jobs/{job_id}/download")
async def job_download(job_id: str) -> FileResponse:
    metadata = await job_manager.get_metadata(job_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    paths = metadata.get("paths", {})
    output_dir = Path(paths.get("output_dir", Path.cwd() / "outputs" / job_id))
    zip_path = Path(paths.get("output_zip", output_dir.parent / "enhanced-audios.zip"))

    if not zip_path.exists():
        files_exist = output_dir.exists() and any(output_dir.iterdir())
        if not files_exist:
            raise HTTPException(status_code=404, detail="No processed outputs available yet.")
        await job_manager.ensure_output_zip(output_dir, zip_path)

    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Output archive not available.")

    archive_name = metadata.get("archive_name") or job_id
    safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in archive_name)
    suggested_name = f"{safe_name or job_id}-enhanced.zip"

    return FileResponse(
        path=zip_path,
        filename=suggested_name,
        media_type="application/zip",
    )


@app.websocket("/ws/{job_id}")
async def job_progress_ws(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()
    try:
        queue, history, job = await job_manager.subscribe(job_id)
    except KeyError:
        await websocket.send_json({
            "type": "error",
            "job_id": job_id,
            "message": "job_not_found",
        })
        await websocket.close()
        return

    try:
        for event in history:
            await websocket.send_json(event)

        if job is None:
            await websocket.close()
            return

        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        if job is not None:
            job_manager.unsubscribe(job_id, queue)
    except Exception:
        if job is not None:
            job_manager.unsubscribe(job_id, queue)
        raise


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000)