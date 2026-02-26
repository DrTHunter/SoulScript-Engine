"""Seed the memory vault with randomized test memories.

Categories: computer hardware, project state, biographical facts,
preferences, and miscellaneous technical details.
Run once from the repo root:
    python scripts/seed_memories.py
"""

import sys, os

# Ensure repo root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.memory.vault import VaultStore

vault = VaultStore("data/memory/vault.jsonl")

MEMORIES = [
    # â”€â”€ Computer Hardware â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    dict(
        text="User runs a desktop workstation with a Ryzen 9 7950X CPU (16 cores / 32 threads), 64 GB DDR5-5600 RAM, and an NVIDIA RTX 4090 (24 GB VRAM) â€” primary dev and local-LLM inference rig.",
        scope="shared", category="bio",
        tags=["hardware", "workstation", "gpu", "cpu"],
        source="operator", tier="canon",
    ),
    dict(
        text="Secondary machine is a 2023 Framework Laptop 16 with a Ryzen 7 7840HS, 32 GB DDR5, and a discrete RX 7700S module â€” used for mobile dev and travel.",
        scope="shared", category="bio",
        tags=["hardware", "laptop", "framework", "mobile"],
        source="operator", tier="canon",
    ),
    dict(
        text="Primary storage layout: 2 TB Samsung 990 Pro NVMe for OS and projects, 4 TB WD Black SN850X for datasets and model weights, plus a Synology DS923+ NAS with 4x 16 TB drives in SHR-2 for backups.",
        scope="shared", category="bio",
        tags=["hardware", "storage", "nas", "nvme"],
        source="operator", tier="canon",
    ),
    dict(
        text="Networking: Ubiquiti UniFi Dream Machine Pro as the gateway/router, two U6-Pro access points for Wi-Fi 6E, and a USW-Pro-24-PoE managed switch; ISP is AT&T Fiber 2 Gbps symmetric.",
        scope="shared", category="bio",
        tags=["hardware", "networking", "unifi", "isp"],
        source="operator", tier="canon",
    ),
    dict(
        text="Peripherals: Logitech MX Master 3S mouse, Keychron Q1 Pro mechanical keyboard (Gateron Jupiter Banana switches), LG 27GP950-B 4K 144Hz monitor, and a Blue Yeti X microphone.",
        scope="shared", category="bio",
        tags=["hardware", "peripherals", "keyboard", "monitor"],
        source="operator", tier="canon",
    ),

    # â”€â”€ Project State â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    dict(
        text="SoulScript Engine is currently in pre-alpha; core subsystems include FAISS memory vault, directive injector, governance layer, and a FastAPI web dashboard on port 8585.",
        scope="shared", category="project",
        tags=["soulscript", "status", "pre_alpha", "architecture"],
        source="operator", tier="register", topic_id="project_status",
    ),
    dict(
        text="Active development branches: main (stable), feature/web-chat (dashboard streaming chat UI), and experiment/local-llm (Ollama integration trial for cost reduction).",
        scope="shared", category="project",
        tags=["soulscript", "git", "branches", "development"],
        source="operator", tier="register", topic_id="git_branches",
    ),
    dict(
        text="Known open issues: port 8585 occasionally held by zombie uvicorn processes after crash; FAISS index rebuild is slow on >10k vectors.",
        scope="shared", category="project",
        tags=["soulscript", "bugs", "known_issues", "uvicorn"],
        source="operator", tier="register", topic_id="known_issues",
    ),
    dict(
        text="Tech stack: Python 3.11, FastAPI/Uvicorn (web), FAISS-cpu (vector search), SentenceTransformers (embeddings), PyYAML (config), Jinja2 (templates), and OpenAI/Anthropic SDKs (LLM clients).",
        scope="shared", category="project",
        tags=["soulscript", "tech_stack", "python", "faiss", "fastapi"],
        source="operator", tier="canon",
    ),

    # â”€â”€ Biographical Facts (User) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    dict(
        text="User is a software engineer and creator of the SoulScript Engine; based in the Dallas-Fort Worth metroplex, Texas. Prefers working late nights (10 PM - 4 AM).",
        scope="shared", category="bio",
        tags=["User", "creator", "location", "schedule"],
        source="operator", tier="canon",
    ),
    dict(
        text="User has a background in full-stack web development, DevOps, and systems programming; languages include Python, TypeScript, Rust, C#, and PowerShell.",
        scope="shared", category="bio",
        tags=["User", "skills", "languages", "background"],
        source="operator", tier="canon",
    ),
    dict(
        text="User drinks black coffee (no sugar, no cream) and keeps a strict no-energy-drink policy. Favorite food is smoked brisket, Texas-style.",
        scope="shared", category="bio",
        tags=["User", "preferences", "food", "coffee"],
        source="operator", tier="canon",
    ),
    dict(
        text="Music preference: lo-fi hip hop and ambient electronica while coding; metal and post-rock for focus sprints. Dislikes pop country.",
        scope="shared", category="preference",
        tags=["User", "music", "coding", "focus"],
        source="operator", tier="canon",
    ),
    dict(
        text="User has two cats named Pixel and Byte, both domestic shorthairs adopted from a local rescue in 2024.",
        scope="shared", category="bio",
        tags=["User", "pets", "cats", "personal"],
        source="operator", tier="canon",
    ),

    # â”€â”€ Technical / Infrastructure â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    dict(
        text="The FAISS vector index uses the IVF4096,Flat quantizer with 128-dimensional embeddings from all-MiniLM-L6-v2; nprobe is set to 64 for a recall-speed tradeoff.",
        scope="shared", category="capability",
        tags=["faiss", "embeddings", "vector_search", "config"],
        source="operator", tier="canon",
    ),
    dict(
        text="Backup strategy: nightly rsync of data/ and config/ to Synology NAS, weekly encrypted tarball to Backblaze B2 bucket, and git push to private GitHub repo for code.",
        scope="shared", category="constraint",
        tags=["backup", "nas", "b2", "github", "strategy"],
        source="operator", tier="canon",
    ),
    dict(
        text="The Orion Forge workspace on the desktop is the canonical development directory for SoulScript Engine; all paths and scripts assume this location.",
        scope="shared", category="meta",
        tags=["workspace", "paths", "canonical", "convention"],
        source="operator", tier="canon",
    ),
    dict(
        text="Python virtual environment is NOT used; system Python 3.11 is the runtime. Dependencies are pinned in requirements.txt and installed globally under the user profile.",
        scope="shared", category="meta",
        tags=["python", "environment", "dependencies", "convention"],
        source="operator", tier="canon",
    ),
    dict(
        text="GPU inference tested with llama.cpp (GGUF Q4_K_M) and text-generation-webui; RTX 4090 handles up to 70B-class models at ~15 tok/s with 4-bit quantization.",
        scope="shared", category="capability",
        tags=["hardware", "gpu", "inference", "llama_cpp", "benchmarks"],
        source="operator", tier="canon",
    ),
]


def main():
    count = 0
    for m in MEMORIES:
        mem = vault.create_memory(**m)
        print(f"  + [{mem.tier:8s}] {mem.id}: {mem.text[:70]}...")
        count += 1
    print(f"\nDone â€” {count} memories seeded into vault.")


if __name__ == "__main__":
    main()
