#!/usr/bin/env python3
import base64
import os
import subprocess
import tempfile
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


MODEL_NAME = os.environ.get("FPBX_WHISPER_MODEL", "small").strip() or "small"
TMPDIR = os.environ.get("FPBX_STT_TMPDIR", "/dev/shm/fpbx-stt-vast")
MAX_UPLOAD = int(os.environ.get("FPBX_STT_MAX_UPLOAD", str(200 * 1024 * 1024)))

app = FastAPI(title="FreePBX STT Vast model server", docs_url=None, redoc_url=None)
model = None
device_name = "cuda"


class TranscribePayload(BaseModel):
    audio_b64: str
    filename: str = "recording.bin"
    duration: float = 0.0
    language: str = ""
    vad_filter: bool = True
    request_id: str = ""


def current_vast_instance_id():
    raw = (os.environ.get("CONTAINER_ID") or "").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def probe_duration(path):
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return max(0.0, float(proc.stdout.strip())) if proc.returncode == 0 else 0.0
    except Exception:
        return 0.0


@app.on_event("startup")
def load_model():
    global model, device_name
    try:
        import torch
        import whisper

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is not available")
        device_name = torch.cuda.get_device_name(0)
        started = time.time()
        print(
            f"FPBX_STT_MODEL_INFO loading Whisper {MODEL_NAME} on {device_name}",
            flush=True,
        )
        model = whisper.load_model(
            MODEL_NAME,
            device="cuda",
            download_root="/root/.cache/whisper",
        )
        print(
            f"FPBX_STT_MODEL_READY model={MODEL_NAME} gpu={device_name} "
            f"load_seconds={time.time() - started:.1f}",
            flush=True,
        )
    except Exception as exc:
        print(f"FPBX_STT_MODEL_ERROR {type(exc).__name__}: {exc}", flush=True)
        raise


@app.get("/health")
def health():
    return {"ok": model is not None, "model": MODEL_NAME, "gpu": device_name}


@app.post("/transcribe")
def transcribe(payload: TranscribePayload):
    if model is None:
        raise HTTPException(status_code=503, detail="Whisper model is not ready")

    try:
        raw = base64.b64decode(payload.audio_b64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="audio_b64 is invalid base64")
    if not raw:
        raise HTTPException(status_code=400, detail="recording is empty")
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail=f"recording exceeds {MAX_UPLOAD} bytes")

    os.makedirs(TMPDIR, mode=0o700, exist_ok=True)
    suffix = os.path.splitext(payload.filename or "recording.bin")[1][:12] or ".bin"
    fd, path = tempfile.mkstemp(prefix="audio-", suffix=suffix, dir=TMPDIR)
    os.close(fd)
    started = time.time()

    try:
        with open(path, "wb") as handle:
            handle.write(raw)
        del raw

        language = (payload.language or "").strip() or None
        duration = probe_duration(path) or float(payload.duration or 0.0)
        print(
            f"FPBX_STT_REQUEST request_id={payload.request_id[:160]} "
            f"duration={duration:.1f}s language={language or 'auto'} "
            f"instance_id={current_vast_instance_id() or 'missing'}",
            flush=True,
        )

        result = model.transcribe(
            path,
            language=language,
            verbose=False,
            temperature=0,
            fp16=True,
        )
        text = str(result.get("text") or "").strip()
        detected_language = str(result.get("language") or language or "")

        return {
            "text": text,
            "language": detected_language,
            "duration": duration,
            "processing_seconds": round(time.time() - started, 3),
            "model": MODEL_NAME,
            "gpu": device_name,
            "request_id": payload.request_id,
            "instance_id": current_vast_instance_id(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        import traceback

        print(
            f"FPBX_STT_MODEL_ERROR {type(exc).__name__}: {exc}\n"
            f"{traceback.format_exc()}",
            flush=True,
        )
        raise HTTPException(status_code=500, detail="remote transcription failed")
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass
