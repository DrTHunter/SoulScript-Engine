"""Build the Notes FAISS index — soul scripts and user notes.

This is SEPARATE from the Memory Vault FAISS (which auto-builds from
vault.jsonl inside FAISSMemory.__init__).  This index covers only
user-created notes and soul scripts, chunked by section for precise
semantic retrieval.

The index is rebuilt via:
  - ``python -m src.memory.load_and_index``
  - ``/api/faiss/reindex`` web route

Agents CANNOT write to or erase this index.
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.memory.notes_faiss import NotesFAISS
from src.storage.user_notes_loader import strip_html
from src.memory.chunker import chunk_soul_script


def load_user_notes(notes_dir: str, use_chunking: bool = True) -> list:
    """Load notes from user_notes JSON files and chunk them.

    Args:
        notes_dir: Path to user_notes directory
        use_chunking: If True, chunk by ### sections (recommended)

    Returns:
        List of chunk dicts ready for NotesFAISS.build_index()
    """
    index_path = os.path.join(notes_dir, "index.json")

    if not os.path.isfile(index_path):
        print(f"User notes index not found: {index_path}")
        return []

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    all_chunks = []
    total_notes = 0

    for entry in index:
        if entry.get("trashed"):
            continue

        note_id = entry.get("id")
        if not note_id:
            continue

        note_path = os.path.join(notes_dir, f"{note_id}.json")
        if not os.path.isfile(note_path):
            continue

        with open(note_path, "r", encoding="utf-8") as f:
            note_data = json.load(f)

        content_html = note_data.get("content_html", "")
        if not content_html:
            continue

        text = strip_html(content_html)
        if not text:
            continue

        title = note_data.get("title", "Untitled")
        emoji = note_data.get("emoji", "📝")

        total_notes += 1

        if use_chunking:
            chunks = chunk_soul_script(
                text=text,
                note_id=note_id,
                title=title,
                emoji=emoji,
                metadata={
                    "section": note_data.get("section"),
                    "created": note_data.get("created"),
                    "updated": note_data.get("updated"),
                },
            )
            for chunk in chunks:
                all_chunks.append({
                    "text": chunk["text"],
                    "metadata": chunk["metadata"],
                })
        else:
            all_chunks.append({
                "text": text,
                "metadata": {
                    "document_id": note_id,
                    "document_title": f"{emoji} {title}",
                    "section_title": title,
                    "section_path": f"{emoji} {title}",
                    "is_canon": True,
                    "immutable": True,
                    "section": note_data.get("section"),
                    "updated": note_data.get("updated"),
                },
            })

    if use_chunking:
        print(f"Loaded {total_notes} user notes, chunked into {len(all_chunks)} sections")
    else:
        print(f"Loaded {len(all_chunks)} user notes (unchunked)")

    return all_chunks


def load_builtin_notes(notes_dir: str) -> list:
    """Load built-in .md notes from the notes/ directory and chunk them.

    Returns list of chunk dicts.
    """
    if not os.path.isdir(notes_dir):
        return []

    all_chunks = []
    for fn in sorted(os.listdir(notes_dir)):
        if not fn.endswith(".md"):
            continue
        path = os.path.join(notes_dir, fn)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()
        # Strip HTML comments
        lines = [ln for ln in text.splitlines()
                 if not ln.strip().startswith("<!--")]
        text = "\n".join(lines).strip()
        if not text:
            continue

        chunks = chunk_soul_script(
            text=text,
            note_id=fn,
            title=fn,
            emoji="📄",
            metadata={"source_type": "builtin"},
        )
        for chunk in chunks:
            all_chunks.append({
                "text": chunk["text"],
                "metadata": chunk["metadata"],
            })

    if all_chunks:
        print(f"Loaded built-in notes, chunked into {len(all_chunks)} sections")
    return all_chunks


def main():
    """Build the Notes FAISS index (soul scripts + user notes).

    The Memory Vault FAISS is separate — it auto-builds from vault.jsonl
    inside FAISSMemory.__init__.
    """
    print("=" * 70)
    print("Notes FAISS Index Builder")
    print("=" * 70)

    if PROJECT_ROOT.name == "SoulScript-Engine":
        base_dir = PROJECT_ROOT
    else:
        base_dir = PROJECT_ROOT / "SoulScript-Engine"

    notes_dir = base_dir / "data" / "user_notes"
    builtin_dir = base_dir / "notes"
    faiss_dir = base_dir / "data" / "memory" / "faiss"

    # 1. Load user notes (soul scripts, etc.)
    print("\n1. Loading user notes...")
    user_chunks = load_user_notes(str(notes_dir), use_chunking=True)

    # 2. Load built-in .md notes
    print("\n2. Loading built-in notes...")
    builtin_chunks = load_builtin_notes(str(builtin_dir))

    all_chunks = user_chunks + builtin_chunks
    print(f"\nTotal chunks to index: {len(all_chunks)}")
    print(f"  - User note chunks: {len(user_chunks)}")
    print(f"  - Built-in note chunks: {len(builtin_chunks)}")

    if not all_chunks:
        print("No notes found to index!")
        return

    # 3. Build NotesFAISS index
    print("\n3. Building Notes FAISS index...")
    nf = NotesFAISS(str(faiss_dir))
    count = nf.build_index(all_chunks)

    # 4. Stats
    print("\n" + "=" * 70)
    print("NOTES INDEX COMPLETE")
    print("=" * 70)
    stats = nf.stats()
    print(f"\nTotal chunks indexed: {stats['total_chunks']}")
    print(f"Unique documents:    {stats['unique_documents']}")
    print(f"Embedding model:     {stats['model_name']}")
    print(f"Index file:          {stats['index_file']}")

    # 5. Sample retrieval
    print("\n" + "=" * 70)
    print("SAMPLE RETRIEVAL TEST")
    print("=" * 70)

    test_queries = [
        "What is my mission and purpose?",
        "How do I handle boundaries and manipulation?",
        "Tell me about loyalty and trust",
    ]

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        results = nf.search(query, top_k=3)

        for i, (chunk, score) in enumerate(results, 1):
            meta = chunk.get("metadata", {})
            path = meta.get("section_path", meta.get("document_title", ""))
            preview = chunk["text"][:100].replace("\n", " ")
            print(f"  {i}. {path}")
            print(f"     Score: {score:.4f} | {len(chunk['text'])} chars")
            print(f"     Preview: {preview}...")
            print()

    print(f"\n✓ Notes FAISS index ready for semantic search!")
    print(f"✓ Saved to: {faiss_dir}")
    print(f"✓ Soul Scripts chunked by section for precise retrieval")
    print(f"\nNote: Memory Vault FAISS is separate and auto-builds from vault.jsonl.")


if __name__ == "__main__":
    main()
