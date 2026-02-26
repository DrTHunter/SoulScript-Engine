# openedai-speech — Local Text-to-Speech (Docker + GPU)

**Required by:** Agent TTS voice output  
**Default URL:** `http://localhost:5050`  
**Connection ID:** `edge-tts-local`  
**Configured in:** Dashboard → Connections  
**Privacy:** 100% local — no data leaves your machine

---

## What is openedai-speech?

[openedai-speech](https://github.com/matatonic/openedai-speech) is a
fully local, OpenAI-compatible text-to-speech server. It bundles **two engines**:

| Engine | Model Param | Quality | Speed | Runs On | Voice Clone |
|--------|-------------|---------|-------|---------|-------------|
| **Piper** | `tts-1` | 7/10 | Very fast | CPU | No |
| **XTTS v2** (Coqui) | `tts-1-hd` | 8/10 | Real-time | GPU (NVIDIA) | Yes |

Both engines share the same voice names (`alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`).
The `model` parameter in the API request determines which engine processes it.

In the Dashboard chat, click the 🔊 toggle to cycle:
- **🔊 Piper** (green) — `tts-1` → fast, CPU-only
- **🔊 XTTS HD** (purple) — `tts-1-hd` → high quality, GPU-accelerated

---

## GPU Setup (RTX 3060)

The Docker Compose file is pre-configured for NVIDIA GPU acceleration:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

VRAM usage: ~2-4 GB during active speech generation, near-zero when idle.

---

## Quick Start (Docker Compose)

```bash
cd tools/openedai_speech
docker compose up -d
```

First startup downloads ~2GB of speech models. Wait ~30 seconds.

### Verify

```bash
curl http://localhost:5050/v1/models
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/audio/speech` | POST | Generate speech (OpenAI-compatible) |
| `/v1/models` | GET | List available models (tts-1, tts-1-hd) |

### Example — Generate Speech (Piper / CPU)

```bash
curl -X POST http://localhost:5050/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model": "tts-1", "input": "Hello!", "voice": "alloy"}' \
  --output speech.mp3
```

### Example — Generate Speech (XTTS HD / GPU)

```bash
curl -X POST http://localhost:5050/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model": "tts-1-hd", "input": "Hello!", "voice": "alloy"}' \
  --output speech_hd.mp3
```

---

## Available Voices

### tts-1 (Piper — CPU, fast)

| Voice | Model File |
|-------|-----------|
| `alloy` | en_US-libritts_r-medium.onnx (speaker 79) |
| `echo` | en_US-libritts_r-medium.onnx (speaker 134) |
| `echo-alt` | en_US-ryan-high.onnx |
| `fable` | en_GB-northern_english_male-medium.onnx |
| `onyx` | en_US-libritts_r-medium.onnx (speaker 159) |
| `nova` | en_US-libritts_r-medium.onnx (speaker 107) |
| `shimmer` | en_US-libritts_r-medium.onnx (speaker 163) |

### tts-1-hd (XTTS v2 — GPU, high quality)

| Voice | Reference Audio | Notes |
|-------|----------------|-------|
| `alloy` | voices/alloy.wav | |
| `alloy-alt` | voices/alloy-alt.wav | Alternative alloy |
| `echo` | voices/echo.wav | |
| `fable` | voices/fable.wav | |
| `onyx` | voices/onyx.wav | |
| `nova` | voices/nova.wav | |
| `shimmer` | voices/shimmer.wav | |

---

## Voice Cloning (XTTS)

To clone a voice, place a WAV reference file (1-30 seconds) in the
`speech_data` Docker volume under `/app/voices/`, then add an entry
to the voice config:

```yaml
tts-1-hd:
  my-voice:
    model: xtts
    speaker: voices/my-voice.wav
    language: auto
```

---

## Connection Settings

The runtime connects via `config/connections.json`:

```json
{
  "id": "edge-tts-local",
  "name": "openedai-speech (Local)",
  "type": "local",
  "provider": "edge-tts",
  "url": "http://localhost:5050",
  "api_key": "",
  "models": ["tts-1", "tts-1-hd"],
  "enabled": true
}
```

Manage from **Dashboard → Connections**.

---

## Stopping / Removing

```bash
docker compose -f tools/openedai_speech/docker-compose.yml down
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| TTS not working | Check `http://localhost:5050/v1/models` returns JSON |
| Container exits on start | Check logs: `docker logs openedai-speech` |
| Port 5050 in use | Change mapping in compose, update connection URL |
| Slow generation | Verify GPU: `docker exec openedai-speech python -c "import torch; print(torch.cuda.is_available())"` |
| No voices | Wait ~30s after start for model download |
