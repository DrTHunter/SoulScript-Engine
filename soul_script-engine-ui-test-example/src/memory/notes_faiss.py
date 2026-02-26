"""Notes FAISS — read-only semantic index for Soul Scripts and directive notes.

This is a SEPARATE system from the vault-backed FAISSMemory.  It indexes
chunked soul scripts and user notes set to "directive" mode, providing
semantic retrieval of the most relevant behavioral-pattern sections per
query.  The notes themselves are immutable (cannot be written/erased by
agents).

Architecture
------------
- Notes and Soul Scripts are chunked by ``src.memory.chunker`` into
  ``### header``-delimited sections.
- Chunks are embedded with sentence-transformers and stored in a FAISS
  IndexFlatIP (cosine similarity).
- A metadata sidecar (``notes_meta.json``) tracks chunk→note mappings.
- The index is rebuilt via ``build_index()`` or the ``/api/faiss/reindex``
  web route.  It is never modified by agents.

Usage
-----
    idx = NotesFAISS.load(faiss_dir)          # load cached
    results = idx.search("loyalty", top_k=5)  # semantic search
    results = idx.search("loyalty", top_k=5,  # filtered to specific notes
                          note_ids={"abc123"})
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

log = logging.getLogger(__name__)

_INDEX_FILE = "notes_index.faiss"
_META_FILE = "notes_meta.json"


class NotesFAISS:
    """Read-only FAISS index over chunked soul scripts / directive notes."""

    def __init__(
        self,
        faiss_dir: str,
        model_name: str = "all-mpnet-base-v2",
    ):
        self.faiss_dir = Path(faiss_dir)
        self.faiss_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name

        self._encoder: Optional[SentenceTransformer] = None
        self._embedding_dim: Optional[int] = None

        # FAISS index + chunk metadata
        self.index: Optional[faiss.IndexFlatIP] = None
        self._chunks: List[Dict[str, Any]] = []  # ordered by FAISS row

    # ------------------------------------------------------------------
    # Lazy encoder (shared model with FAISSMemory if same process)
    # ------------------------------------------------------------------

    @property
    def encoder(self) -> SentenceTransformer:
        if self._encoder is None:
            log.info("[notes_faiss] Loading embedding model: %s", self.model_name)
            self._encoder = SentenceTransformer(self.model_name)
            self._embedding_dim = self._encoder.get_sentence_embedding_dimension()
        return self._encoder

    @property
    def embedding_dim(self) -> int:
        if self._embedding_dim is None:
            _ = self.encoder
        return self._embedding_dim

    # ------------------------------------------------------------------
    # Build index from chunks
    # ------------------------------------------------------------------

    def build_index(self, chunks: List[Dict[str, Any]]) -> int:
        """Build (or rebuild) the FAISS index from a list of chunk dicts.

        Each chunk dict must have:
            - ``text``:     the chunk text to embed
            - ``metadata``: dict with at least ``document_id``

        Returns the number of vectors indexed.
        """
        if not chunks:
            self.index = faiss.IndexFlatIP(self.embedding_dim)
            self._chunks = []
            self._save()
            return 0

        texts = [c["text"] for c in chunks]
        vecs = self.encoder.encode(texts, normalize_embeddings=True,
                                   show_progress_bar=True, batch_size=32)
        vecs = np.ascontiguousarray(vecs, dtype="float32")

        dim = vecs.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(vecs)
        self._chunks = chunks
        self._save()
        log.info("[notes_faiss] Indexed %d chunks (%d dims)", len(chunks), dim)
        return len(chunks)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
        note_ids: Optional[Set[str]] = None,
        builtin_filenames: Optional[Set[str]] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Semantic search over indexed note chunks.

        Args:
            query:     natural-language search query
            top_k:     max results to return
            note_ids:  if given, only return chunks whose ``document_id``
                       is in this set (user note IDs)
            builtin_filenames: if given, also include chunks whose
                       ``document_id`` is in this set (.md note filenames)

        Returns:
            List of (chunk_dict, score) tuples, highest score first.
        """
        if self.index is None or self.index.ntotal == 0:
            return []
        if not query or not query.strip():
            return []

        vec = self.encoder.encode([query], normalize_embeddings=True)
        vec = np.ascontiguousarray(vec, dtype="float32")

        # When filtering by note_ids, search ALL chunks (index is small, ~100-300 chunks)
        # to ensure we never miss relevant results due to filtered items filling search_k
        search_k = self.index.ntotal if (note_ids or builtin_filenames) else min(self.index.ntotal, top_k * 2)
        scores, idxs = self.index.search(vec, search_k)

        results: List[Tuple[Dict[str, Any], float]] = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < 0:
                continue
            chunk = self._chunks[idx]
            doc_id = chunk.get("metadata", {}).get("document_id", "")

            # Apply filter if requested
            if note_ids is not None or builtin_filenames is not None:
                ids = note_ids or set()
                builtins = builtin_filenames or set()
                if doc_id not in ids and doc_id not in builtins:
                    continue

            results.append((chunk, float(score)))
            if len(results) >= top_k:
                break

        return results

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self):
        """Save index + metadata to disk."""
        idx_path = self.faiss_dir / _INDEX_FILE
        meta_path = self.faiss_dir / _META_FILE

        if self.index is not None:
            faiss.write_index(self.index, str(idx_path))

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "model_name": self.model_name,
                "total_chunks": len(self._chunks),
                "chunks": self._chunks,
            }, f, indent=2, default=str)

        log.info("[notes_faiss] Saved to %s (%d chunks)", self.faiss_dir, len(self._chunks))

    @classmethod
    def load(cls, faiss_dir: str, model_name: str = "all-mpnet-base-v2") -> Optional["NotesFAISS"]:
        """Load a cached notes index from disk.  Returns None if not found."""
        d = Path(faiss_dir)
        idx_path = d / _INDEX_FILE
        meta_path = d / _META_FILE

        if not idx_path.exists() or not meta_path.exists():
            return None

        try:
            obj = cls(faiss_dir, model_name=model_name)
            obj.index = faiss.read_index(str(idx_path))
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            obj._chunks = data.get("chunks", [])
            log.info("[notes_faiss] Loaded %d chunks from %s", len(obj._chunks), faiss_dir)
            return obj
        except Exception as exc:
            log.error("[notes_faiss] Failed to load: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """Return summary statistics."""
        total = self.index.ntotal if self.index else 0
        doc_ids = set()
        for c in self._chunks:
            doc_ids.add(c.get("metadata", {}).get("document_id", ""))
        return {
            "total_chunks": total,
            "unique_documents": len(doc_ids),
            "model_name": self.model_name,
            "index_file": str(self.faiss_dir / _INDEX_FILE),
        }
