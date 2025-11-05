## Task

You are given a Python project containing an `AudioEnhancer` class (from an audio enhancement script) that provides functionality to:

- find audio files in a directory,
- convert them to WAV,
- denoise using a denoiser model,
- apply ffmpeg filters and re-encode at high quality,
- write outputs to disk.

Extend this project by building a production-quality **FastAPI** service and a minimal single-page HTML UI that:

1. Accepts a **ZIP** upload containing audio files. The server unzips into an `uploads/<job_id>/original-audios/` folder in the current working directory.
2. Exposes a REST API to create a processing job with UI-specified options and returns a `job_id`.
3. Processes files using the existing `AudioEnhancer` logic, preserving all functionality and behavior. Do **NOT** remove or break any original features.
4. Hosts a **WebSocket** endpoint that streams live progress updates for each job (realtime and reliable).
5. Produces a downloadable ZIP of the processed outputs in `outputs/<job_id>/enhanced-audios.zip`.
6. Stores all files in the **current directory**, in well-organized subfolders:
   - `uploads/<job_id>/original-audios/`
   - `uploads/<job_id>/tmp/`
   - `outputs/<job_id>/enhanced-audios/`
   - `outputs/<job_id>/enhanced-audios.zip`
   - `jobs/<job_id>.json` (metadata & final job status)
7. Provides a minimal client HTML page to:
   - upload a ZIP,
   - display all CLI options (model, low-bitrate, suffix, recursive, temp-dir path, no-loudnorm),
   - start processing,
   - open a WebSocket to receive progress events and show a progress bar and per-file status,
   - show download links for the output ZIP and a listing of output files when done.

## Non-Functional & Implementation Constraints

- Use FastAPI + Uvicorn.
- Use WebSocket for real-time progress updates (Starlette/WebSocket).
- Use `asyncio.to_thread` or `concurrent.futures.ThreadPoolExecutor` to run CPU-bound, blocking enhancement tasks (torch/ffmpeg) so the event loop is not blocked.
- Do NOT attempt to GPU-accelerate or change denoiser logic; call the existing `AudioEnhancer` methods. If the existing class is blocking or synchronous, run it in a worker thread.
- The denoiser model should be loaded once per worker process to avoid reloading per file. Reuse `AudioEnhancer.load_model()`.
- Implement a job queue that can run multiple jobs sequentially or concurrently with a safe default (e.g., configurable max concurrent jobs). For simplicity implement a single-worker queue but structure code to be extendable.
- Track per-file and total progress. Provide frequent updates to the WebSocket client (per-file start, per-file percent, per-file complete, job percent).
- Save a `jobs/<job_id>.json` metadata file with job options, timestamps, status, and list of input/output files.
- Implement robust error handling and cleanup of temporary files, but keep processed outputs even if some files fail.
- Keep usage of external dependencies minimal. Allowed libraries: fastapi, uvicorn, aiofiles, python-multipart, websockets (if needed), zipfile, aiohttp (optional), python-standard libs. Use `pip` names in a `requirements.txt`.
- Use `ffmpeg` and `ffprobe` from PATH as the original script does.

## API Design

Implement the following endpoints (HTTP + WebSocket):

1. `GET  /`

   - Return the HTML UI page (single-file, minimal CSS and JS).

2. `POST /api/upload`

   - Accepts `multipart/form-data` with:
     - `file`: uploaded ZIP file (required)
     - `model`: dns48|dns64|master64 (default dns64)
     - `low_bitrate`: boolean (default false)
     - `suffix`: string (default "")
     - `recursive`: boolean (default false)
     - `temp_dir`: string (default "tmp")
     - `no_loudnorm`: boolean (default false)
   - Server:
     - Validate ZIP.
     - Generate `job_id` as UUID4.
     - Create folders: `uploads/<job_id>/original-audios/`, `uploads/<job_id>/tmp/`, `outputs/<job_id>/enhanced-audios/`.
     - Extract worker-uploaded zip into `uploads/<job_id>/original-audios/`.
     - Create `jobs/<job_id>.json` with metadata, status `queued`.
   - Response: JSON `{ "job_id": "<job_id>", "ws_url": "ws://.../ws/<job_id>" }`

3. `GET /api/jobs/{job_id}/status`

   - Return the job metadata and status (queued, running, completed, failed).

4. `GET /api/jobs/{job_id}/download`

   - If completed (or partially completed but outputs exist), return the ZIP of `outputs/<job_id>/enhanced-audios.zip` as an attachment. If zip not present but output folder exists, create zip on-the-fly.

5. `GET /api/jobs/{job_id}/files`

   - Return a JSON listing of input and output filenames and statuses.

6. `WebSocket /ws/{job_id}`
   - Clients can connect and will receive progress messages as JSON in the following schema:
     - Event types:
       - `job_started`: `{type:"job_started", job_id, timestamp}`
       - `file_started`: `{type:"file_started", job_id, filename}`
       - `file_progress`: `{type:"file_progress", job_id, filename, percent}` # percent 0-100
       - `file_completed`: `{type:"file_completed", job_id, filename, success: true/false, reason?: "error message"}`
       - `job_progress`: `{type:"job_progress", job_id, percent}` # overall percent
       - `job_complete`: `{type:"job_complete", job_id, success: true/false, output_zip_url: "...", summary: {...}}`
       - `log`: `{type:"log", message: "...", level: "info|warn|error"}`
   - WebSocket must be resilient: if client disconnects, server continues job; when client reconnects, server can replay last state from `jobs/<job_id>.json`.

## Processing Behavior

- When upload completes, the server should enqueue the job and respond with `job_id`. Processing should start automatically (if a worker is free).
- The server should create an `AudioEnhancer` instance per job (or reuse an instance across jobs if safe), call `setup_temp_dir()` with the job's temp_dir, call `load_model()` once, then call `process_all(...)`. Extend `AudioEnhancer` or wrap it so you can pass a `progress_callback(event_dict)` which your wrapper calls at these points:
  - when a file starts processing,
  - periodically for per-file progress (if that isn’t possible per-file, at least send start/complete plus reasonable job-level progress),
  - when a file finishes (success/fail),
  - when entire job completes.
- If you must modify `AudioEnhancer` methods to accept an optional `progress_callback`, do so in a backward-compatible way (default `None`).
- Use `asyncio.to_thread` to run the blocking processing function and send updates to the WebSocket from the event loop.

## UI Behavior

- Single-page HTML served at `/` with an upload form and options matching CLI:
  - file input to upload .zip
  - model selector (dns48|dns64|master64)
  - low-bitrate checkbox
  - suffix input
  - recursive checkbox
  - temp-dir path input (default "tmp")
  - no-loudnorm checkbox
  - "Start" button
- After upload, show:
  - `job_id`
  - Connect to `ws://.../ws/<job_id>` and show a text log area and progress bar.
  - Show per-file statuses and a final download button linking to `/api/jobs/<job_id>/download`.
  - If user refreshes or reconnects, they can re-open WS and resume receiving updates (server must allow replay from job JSON file).

## Security & Validation

- Limit upload size to a reasonable default (e.g., 2 GB) and reject larger files with an error JSON.
- Validate ZIP contents: only allow files with known audio extensions (.wav, .mp3, .m4a, .flac, .ogg, .aac, .mp4) inside the zip; ignore others.
- For local testing it's fine to allow all origins. But the prompt should instruct to enable CORS only if necessary (e.g., FastAPI CORSMiddleware with allowed origins ['*'] for dev).
- Do not enable arbitrary command execution. Use only ffmpeg/ffprobe subprocess calls used in the original script.

## Background/Concurrency

- Implement a small job manager that:
  - keeps an in-memory map of running/queued jobs and persists final status to `jobs/<job_id>.json`.
  - supports 1 or N worker threads (configurable).
  - ensures safe cleanup of `uploads/<job_id>/tmp/` after processing while preserving final outputs.

## Testing & Acceptance Criteria

The generated code must satisfy the following when run locally:

1. Starting the server and visiting `http://localhost:8000/` shows the upload UI.
2. Uploading a ZIP of mixed supported audio files returns a `job_id` and starts processing.
3. The UI connects to the WebSocket and receives progress events in the format specified.
4. The server writes:
   - inputs to `uploads/<job_id>/original-audios/`
   - outputs to `outputs/<job_id>/enhanced-audios/`
   - `outputs/<job_id>/enhanced-audios.zip` is available after job completion and downloadable via `/api/jobs/<job_id>/download`.
   - `jobs/<job_id>.json` contains job metadata and final result summary.
5. Processing uses the existing `AudioEnhancer` behavior (audio enhancement quality, filters, re-encoding), and the outputs are audio files comparable to the original CLI run.
6. Client can reconnect the WebSocket and receive current state (replay final summary and file list).
7. Reasonable errors are handled: invalid zip, empty job, ffmpeg errors per-file are reported in the websocket log and job summary.

## Deliverables

- A new file `server.py` (FastAPI app) with all endpoints and WebSocket handling.
- A `static/index.html` file implementing the UI with inline JS to:
  - upload zip via fetch,
  - receive the job_id,
  - open WebSocket and display progress, logs, and download link.
- A `requirements.txt` listing required packages.
- Any minimal helper modules (e.g., `job_manager.py`) required by `server.py`.
- Integration code that reuses/extends the existing `AudioEnhancer` class to add a `progress_callback` (backwards-compatible).
- A README snippet showing how to run:
  - `pip install -r requirements.txt`
  - `uvicorn server:app --host 0.0.0.0 --port 8000 --reload`
  - open `http://localhost:8000/`.

## Implementation Hints (for you to use)

- Use `uuid.uuid4().hex` for `job_id`.
- Use `zipfile.ZipFile` to extract uploaded zip safely (validate filenames).
- Use `aiofiles` to write job metadata JSON atomically.
- Use `asyncio.Queue` or a simple list for queued jobs and a `ThreadPoolExecutor` to run them.
- For progress emission:
  - If `AudioEnhancer` cannot provide fine-grained percent, compute job percent as `(completed_files / total_files) * 100` and emit incremental updates when each file completes.
  - Emit `file_started` and `file_completed` for each file. If you can hook into ffmpeg stdout/stderr to compute percent for the encoding stage, emit intermediate `file_progress` updates; otherwise, emit stage-based messages (e.g., started conversion, started denoise, started encoding) to the WebSocket as `log` events.
- On job completion, create a zip archive of `outputs/<job_id>/enhanced-audios/` and provide its URL.

## Finish

Write the code implementing all the above: `server.py`, `static/index.html`, `requirements.txt`, and any helper modules. The final result must be a runnable FastAPI app that preserves the `AudioEnhancer` features and adds the web UI + real-time progress via WebSocket, file storage in the current directory, and final downloadable zip outputs.
