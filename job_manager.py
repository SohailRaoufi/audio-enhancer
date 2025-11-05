import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import zipfile

import aiofiles

from enhance_all_audios import AudioEnhancer


def utc_now() -> str:
    """Return an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


class JobRecord:
    """In-memory representation of an audio enhancement job."""

    def __init__(
        self,
        job_id: str,
        options: Dict[str, Any],
        original_dir: Path,
        temp_dir: Path,
        output_dir: Path,
        output_zip: Path,
        input_files: List[str],
        archive_name: Optional[str] = None,
    ):
        self.job_id = job_id
        self.options = options
        self.status = "queued"
        self.created_at = utc_now()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.error: Optional[str] = None
        self.original_dir = Path(original_dir)
        self.temp_dir = Path(temp_dir)
        self.output_dir = Path(output_dir)
        self.output_zip = Path(output_zip)
        self.results: Dict[str, Any] = {"success": [], "failed": []}
        self.total_files = len(input_files)
        self.processed_files = 0
        self.file_statuses: Dict[str, Dict[str, Any]] = {}
        for rel_path in input_files:
            self.file_statuses[rel_path] = {
                "input": rel_path,
                "output": None,
                "status": "pending",
                "percent": 0,
                "stage": "queued",
                "message": None,
            }
        self.archive_name = archive_name or job_id
        self.listeners: List[asyncio.Queue] = []
        self.events: List[Dict[str, Any]] = []
        self._metadata_task: Optional[asyncio.Task] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize job info for persistence."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "options": self.options,
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "results": self.results,
            "files": [
                {
                    "input": info["input"],
                    "output": info.get("output"),
                    "status": info["status"],
                    "percent": info.get("percent", 0),
                    "stage": info.get("stage"),
                    "message": info.get("message"),
                }
                for info in self.file_statuses.values()
            ],
            "paths": {
                "original_dir": str(self.original_dir),
                "temp_dir": str(self.temp_dir),
                "output_dir": str(self.output_dir),
                "output_zip": str(self.output_zip),
                "uploads_dir": str(self.original_dir.parent),
            },
            "events": self.events,
            "archive_name": self.archive_name,
        }


class JobManager:
    """Coordinate job execution and progress broadcasting."""

    def __init__(self, base_dir: Optional[Path] = None, max_workers: int = 1):
        self.base_dir = Path(base_dir or Path.cwd())
        self.max_workers = max_workers
        self.jobs: Dict[str, JobRecord] = {}
        self.job_queue: asyncio.Queue[str] = asyncio.Queue()
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.workers: List[asyncio.Task] = []
        self.jobs_dir = self.base_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        """Start worker tasks."""
        if self.loop is not None:
            return
        self.loop = asyncio.get_running_loop()
        for _ in range(self.max_workers):
            self.workers.append(asyncio.create_task(self._worker()))

    async def shutdown(self) -> None:
        """Stop worker tasks."""
        for task in self.workers:
            task.cancel()
        self.workers.clear()
        self.loop = None

    async def submit_job(
        self,
        job_id: str,
        options: Dict[str, Any],
        original_dir: Path,
        temp_dir: Path,
        output_dir: Path,
        output_zip: Path,
        input_files: List[str],
        archive_name: Optional[str] = None,
    ) -> JobRecord:
        """Register a new job and enqueue it for processing."""
        job = JobRecord(
            job_id=job_id,
            options=options,
            original_dir=original_dir,
            temp_dir=temp_dir,
            output_dir=output_dir,
            output_zip=output_zip,
            input_files=input_files,
            archive_name=archive_name,
        )
        self.jobs[job_id] = job
        await self.save_metadata(job)
        await self.job_queue.put(job_id)
        return job

    async def _worker(self) -> None:
        """Process jobs sequentially."""
        while True:
            job_id = await self.job_queue.get()
            job = self.jobs.get(job_id)
            if job is None:
                self.job_queue.task_done()
                continue

            job.status = "running"
            job.started_at = utc_now()
            await self.save_metadata(job)
            self._publish_event(job, {"type": "job_started"})

            try:
                results = await asyncio.to_thread(self._execute_job, job)
                job.results = results or {"success": [], "failed": []}
                success_count = len(job.results.get("success", []))
                failed_count = len(job.results.get("failed", []))
                if success_count == 0 and failed_count > 0:
                    job.status = "failed"
                else:
                    job.status = "completed"
            except Exception as exc:  # pragma: no cover - defensive logging
                job.status = "failed"
                job.error = str(exc)
                self._publish_event(job, {
                    "type": "job_failed",
                    "reason": job.error,
                })
            finally:
                job.completed_at = utc_now()
                await self._finalize_job(job)
                self.job_queue.task_done()

    def _execute_job(self, job: JobRecord) -> Dict[str, Any]:
        """Run AudioEnhancer synchronously inside a worker thread."""
        enhancer = AudioEnhancer(
            model_name=job.options.get("model", "dns64"),
            temp_dir=str(job.temp_dir),
        )

        def progress(event: Dict[str, Any]) -> None:
            event = dict(event)  # ensure mutable copy
            event.setdefault("job_id", job.job_id)
            event.setdefault("timestamp", utc_now())
            if self.loop is not None:
                self.loop.call_soon_threadsafe(self._handle_progress_event, job.job_id, event)

        return enhancer.process_all(
            input_dir=str(job.original_dir),
            output_dir=str(job.output_dir),
            high_bitrate=not job.options.get("low_bitrate", False),
            suffix=job.options.get("suffix", ""),
            apply_loudnorm=not job.options.get("no_loudnorm", False),
            recursive=job.options.get("recursive", False),
            progress_callback=progress,
        )

    def _handle_progress_event(self, job_id: str, event: Dict[str, Any]) -> None:
        """Update in-memory state and broadcast progress events."""
        job = self.jobs.get(job_id)
        if job is None:
            return

        event = dict(event)
        event.setdefault("timestamp", utc_now())
        event.setdefault("job_id", job_id)
        job.events.append(event)

        filename = event.get("filename")
        if event["type"] == "file_started" and filename:
            info = job.file_statuses.get(filename)
            if info:
                info["status"] = "processing"
                info["stage"] = "started"
                info["message"] = None
        elif event["type"] == "file_progress" and filename:
            info = job.file_statuses.get(filename)
            if info:
                info["percent"] = event.get("percent", info.get("percent", 0))
                info["stage"] = event.get("stage", info.get("stage"))
                if info["status"] == "pending":
                    info["status"] = "processing"
        elif event["type"] == "file_completed" and filename:
            info = job.file_statuses.get(filename)
            if info:
                info["status"] = "completed" if event.get("success") else "failed"
                if event.get("success"):
                    info["percent"] = 100
                info["message"] = event.get("reason")
                info["output"] = event.get("output_file")
                info["stage"] = "completed"
                job.processed_files = min(job.total_files, job.processed_files + 1)
                job_percent = (job.processed_files / job.total_files) * 100 if job.total_files else 100.0
                percent_event = {
                    "type": "job_progress",
                    "job_id": job_id,
                    "percent": job_percent,
                    "completed": job.processed_files,
                    "total": job.total_files,
                    "timestamp": utc_now(),
                }
                job.events.append(percent_event)
                self._broadcast(job, percent_event)
                self._schedule_metadata_save(job)

        self._broadcast(job, event)

    async def _finalize_job(self, job: JobRecord) -> None:
        """Persist metadata, package outputs, and send completion event."""
        if job.output_dir.exists():
            audio_files = [p for p in job.output_dir.rglob("*") if p.is_file()]
            if audio_files:
                await asyncio.to_thread(self._create_output_zip, job.output_dir, job.output_zip)

        await self.save_metadata(job)
        final_event_type = "job_completed" if job.status == "completed" else "job_failed"
        summary_event = {
            "type": final_event_type,
            "job_id": job.job_id,
            "status": job.status,
            "timestamp": utc_now(),
            "summary": {
                "processed": job.processed_files,
                "total": job.total_files,
                "success": len(job.results.get("success", [])),
                "failed": len(job.results.get("failed", [])),
                "error": job.error,
            },
        }
        job.events.append(summary_event)
        self._broadcast(job, summary_event)
        await self.save_metadata(job)

    def _create_output_zip(self, output_dir: Path, zip_path: Path) -> None:
        """Create (or overwrite) the output zip archive."""
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(output_dir)
                    zipf.write(file_path, arcname)

    async def ensure_output_zip(self, output_dir: Path, zip_path: Path) -> None:
        """Ensure a zip archive exists by building it if necessary."""
        await asyncio.to_thread(self._create_output_zip, output_dir, zip_path)

    def _publish_event(self, job: JobRecord, event: Dict[str, Any]) -> None:
        """Record and broadcast a job-level event."""
        payload = dict(event)
        payload.setdefault("job_id", job.job_id)
        payload.setdefault("timestamp", utc_now())
        job.events.append(payload)
        self._broadcast(job, payload)

    def _broadcast(self, job: JobRecord, event: Dict[str, Any]) -> None:
        """Send an event to all connected listeners."""
        for queue in list(job.listeners):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                queue.put_nowait(event)

    def _schedule_metadata_save(self, job: JobRecord) -> None:
        """Debounce metadata persistence to avoid excessive writes."""
        if self.loop is None:
            return

        async def writer() -> None:
            await asyncio.sleep(0.1)
            await self.save_metadata(job)
            job._metadata_task = None

        if job._metadata_task is None or job._metadata_task.done():
            job._metadata_task = self.loop.create_task(writer())

    async def save_metadata(self, job: JobRecord) -> None:
        """Persist job metadata to disk atomically."""
        data = json.dumps(job.to_dict(), indent=2)
        path = self.jobs_dir / f"{job.job_id}.json"
        tmp_path = path.with_suffix(".json.tmp")
        async with aiofiles.open(tmp_path, "w") as f:
            await f.write(data)
        os.replace(tmp_path, path)

    async def get_metadata(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Return metadata for a job, loading from disk if necessary."""
        job = self.jobs.get(job_id)
        if job:
            return job.to_dict()

        path = self.jobs_dir / f"{job_id}.json"
        if not path.exists():
            return None

        async with aiofiles.open(path, "r") as f:
            data = await f.read()
        return json.loads(data)

    async def subscribe(self, job_id: str) -> Tuple[asyncio.Queue, List[Dict[str, Any]], Optional[JobRecord]]:
        """
        Register a listener for job events.

        Returns a tuple of (queue, history, job). If job is None, the job has already
        completed and no new events will be emitted.
        """
        job = self.jobs.get(job_id)
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        if job:
            job.listeners.append(queue)
            history = list(job.events)
            return queue, history, job

        metadata = await self.get_metadata(job_id)
        if metadata is None:
            raise KeyError(job_id)

        history = metadata.get("events", [])
        return queue, history, None

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        """Remove a listener from a job."""
        job = self.jobs.get(job_id)
        if not job:
            return
        if queue in job.listeners:
            job.listeners.remove(queue)
