# STT Vast PyWorker

This repository runs the template-backed GPU side of the standalone FreePBX
transcription service. Publish these files at the root of a public Git
repository, then put that repository URL in the Vast template's
`PYWORKER_REPO` environment variable.

The template must expose TCP port 3000. The Vast PyWorker owns port 3000 and
proxies `/transcribe` to the private model server on `127.0.0.1:18000`.

Recommended template:

- Name: `FreePBX Whisper STT Serverless`
- Image: `vastai/whisper:1.0.8-cuda-12.9-py312`
- Launch mode: SSH
- Disk: 64 GB
- Docker/environment options:
  `-p 3000:3000 -e WORKER_PORT=3000 -e PYWORKER_REPO=https://github.com/YOUR-ORG/fpbx-stt-vast-pyworker.git -e FPBX_WHISPER_MODEL=small`
- On-start script: the complete contents of `template-onstart.sh`

Worker logs:

- `/var/log/fpbx-stt-bootstrap.log`
- `/var/log/fpbx-stt-model.log`

A healthy worker logs `FPBX_STT_MODEL_READY`, completes its benchmark, and has
listeners on `0.0.0.0:3000` and `127.0.0.1:18000`.
