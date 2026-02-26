# SearXNG — Web Search Engine (Docker)

**Required by:** `web_search` tool  
**Default URL:** `http://localhost:3000/search`  
**Configurable in:** Dashboard → Tools → web_search → SearXNG URL

---

## What is SearXNG?

[SearXNG](https://github.com/searxng/searxng) is a free, privacy-respecting
meta-search engine. The `web_search` tool sends queries to a local SearXNG
instance, retrieves results, then scrapes page content for the agent.

---

## Quick Start (Docker)

### 1. Pull the image

```bash
docker pull searxng/searxng:latest
```

### 2. Run the container

```bash
docker run -d \
  --name searxng \
  --restart unless-stopped \
  -p 3000:8080 \
  -e SEARXNG_BASE_URL=http://localhost:3000/ \
  searxng/searxng:latest
```

> **Windows PowerShell** — use backticks instead of backslashes:
> ```powershell
> docker run -d `
>   --name searxng `
>   --restart unless-stopped `
>   -p 3000:8080 `
>   -e SEARXNG_BASE_URL=http://localhost:3000/ `
>   searxng/searxng:latest
> ```

### 3. Verify

Open `http://localhost:3000` in your browser — you should see the SearXNG
search page.

---

## Docker Compose (Alternative)

Use the included `docker-compose.yml`:

```bash
cd tools/searxng
docker-compose up -d
```

---

## Configuration

### Enable JSON API output

SearXNG needs to have JSON output enabled for the tool to work.

1. Open `http://localhost:3000/preferences` in your browser
2. Under **Output format**, enable **JSON**
3. Click **Save**

Alternatively, mount a custom `settings.yml` that sets:

```yaml
search:
  formats:
    - html
    - json
```

The `docker-compose.yml` in this folder already does this via a
mounted `settings.yml`.

### Runtime URL Override

- **Dashboard:** Tools → web_search → SearXNG URL
- **Environment variable:** `SEARXNG_URL=http://localhost:3000/search`
- **settings.json:** `tool_config.web_search.searxng_url`

---

## Stopping / Removing

```bash
docker stop searxng
docker rm searxng
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `web_search` returns "SearXNG request failed" | Verify `http://localhost:3000` loads in browser |
| Container exits immediately | Check logs: `docker logs searxng` |
| No JSON results | Enable JSON format in SearXNG preferences |
| Port 3000 in use | Change the `-p` mapping, e.g. `-p 3001:8080`, then update SearXNG URL in dashboard |
