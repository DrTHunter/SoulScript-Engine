# Whisper STT — Speech-to-Text (Docker)

**Required by:** Voice transcription in chat  
**Default URL:** `http://localhost:8060`  
**Connection ID:** `whisper-stt-local`  
**Configured in:** Dashboard → Connections → Whisper STT (Local)

---

## What is Whisper?

[Whisper](https://github.com/openai/whisper) is OpenAI's open-source automatic
speech recognition model. This setup uses a Whisper-compatible server that
exposes an OpenAI-compatible `/v1/audio/transcriptions` endpoint, so the
runtime can send audio and receive text transcriptions locally.

A popular choice is [faster-whisper-server](https://github.com/fedirz/faster-whisper-server)
which provides GPU-accelerated Whisper inference with an OpenAI-compatible API.

---

## Quick Start (Docker)

### 1. Pull the image

```bash
docker pull fedirz/faster-whisper-server:latest-cpu
```

For GPU (NVIDIA CUDA):
```bash
docker pull fedirz/faster-whisper-server:latest-cuda
```

### 2. Run the container (CPU)

```bash
docker run -d \
  --name whisper-stt \
  --restart unless-stopped \
  -p 8060:8000 \
  -e WHISPER__MODEL=base \
  fedirz/faster-whisper-server:latest-cpu
```

> **Windows PowerShell:**
> ```powershell
> docker run -d `
>   --name whisper-stt `
>   --restart unless-stopped `
>   -p 8060:8000 `
>   -e WHISPER__MODEL=base `
>   fedirz/faster-whisper-server:latest-cpu
> ```

### 2b. Run with GPU (Recommended for large models)

```bash
docker run -d \
  --name whisper-stt \
  --restart unless-stopped \
  --gpus all \
  -p 8060:8000 \
  -e WHISPER__MODEL=large-v3 \
  fedirz/faster-whisper-server:latest-cuda
```

### 3. Verify

```bash
curl http://localhost:8060/health
```

---

## Docker Compose (Alternative)

Use the included `docker-compose.yml`:

```bash
cd tools/whisper_stt
docker-compose up -d
```

---

## Available Models

| Model | Size | Speed | Quality | VRAM (GPU) |
|-------|------|-------|---------|------------|
| `tiny` | 39 MB | Fastest | Low | ~1 GB |
| `base` | 74 MB | Fast | Fair | ~1 GB |
| `small` | 244 MB | Moderate | Good | ~2 GB |
| `medium` | 769 MB | Slow | Better | ~5 GB |
| `large-v3` | 1.5 GB | Slowest | Best | ~10 GB |

> For CPU-only use, `base` or `small` is recommended.  
> For GPU, `large-v3` provides the best accuracy.

Set the model via the `WHISPER__MODEL` environment variable.

---

## API Endpoint

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/audio/transcriptions` | POST | Transcribe audio file (OpenAI-compatible) |

### Example — Transcribe Audio

```bash
curl -X POST http://localhost:8060/v1/audio/transcriptions \
  -F file=@recording.wav \
  -F model=base
```

Response:
```json
{
  "text": "Hello, this is a test recording."
}
```

---

## Connection Settings

The runtime connects via `config/connections.json`:

```json
{
  "id": "whisper-stt-local",
  "name": "Whisper STT (Local)",
  "type": "local",
  "provider": "whisper",
  "url": "http://localhost:8060",
  "api_key": "",
  "models": ["tiny", "base", "small", "medium", "large-v3"],
  "enabled": true
}
```

You can also manage this from **Dashboard → Connections**.

---

## Stopping / Removing

```bash
docker stop whisper-stt
docker rm whisper-stt
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Transcription not working | Verify `http://localhost:8060/health` returns OK |
| Container exits on start | Check logs: `docker logs whisper-stt` |
| Port 8060 in use | Change mapping, e.g. `-p 8061:8000`, then update connection URL |
| Slow transcription on CPU | Use a smaller model (`tiny` or `base`) |
| Out of GPU memory | Use a smaller model or switch to CPU image |
