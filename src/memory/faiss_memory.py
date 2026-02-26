"""FAISS Memory - semantic memory system backed by vault.jsonl storage.

Architecture
------------
- **vault.jsonl** is the single source of truth for all memory records.
  Each memory is an individual JSON line, manually deletable, versioned.
- **FAISS index** provides fast semantic (meaning-based) search over
  vault contents.  The index is an ephemeral cache rebuilt from the vault.
- On startup: load vault, embed active memories, build FAISS index.
- On write: write to vault first, then add embedding to FAISS index.
- On delete: soft-delete in vault, exclude from FAISS results.
- The index files (*.faiss) are saved to disk for fast reload, but the
  vault is always authoritative.  Lost index = just rebuild.

Usage
-----
    from src.memory.faiss_memory import FAISSMemory
    mem = FAISSMemory(vault_path, faiss_dir)
    mem.add("Creator likes coffee", scope="shared", category="preference")
    results = mem.search("what does Creator like?")
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from src.memory.vault import VaultStore
from src.memory.types import Memory

log = logging.getLogger(__name__)


class FAISSMemory:
    """Semantic memory system: vault.jsonl storage + FAISS vector search."""

    def __init__(
        self,
        vault_path: str,
        faiss_dir: str,
        model_name: str = "all-mpnet-base-v2",
    ):
        self.vault = VaultStore(vault_path)
        self.faiss_dir = Path(faiss_dir)
        self.faiss_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name

        # Lazy-loaded encoder
        self._encoder: Optional[SentenceTransformer] = None
        self._embedding_dim: Optional[int] = None

        # FAISS index + mapping
        self.index: Optional[faiss.IndexFlatIP] = None
        # Maps FAISS row position -> vault memory id
        self._idx_to_id: List[str] = []
        # Maps vault memory id -> FAISS row position
        self._id_to_idx: Dict[str, int] = {}
        # Set of deleted vault ids (excluded from results)
        self._deleted_ids: set = set()

        # Try to load cached index, otherwise build from vault
        self._load_or_build()

    # ------------------------------------------------------------------
    # Lazy encoder
    # ------------------------------------------------------------------

    @property
    def encoder(self) -> SentenceTransformer:
        if self._encoder is None:
            log.info("[faiss] Loading embedding model: %s", self.model_name)
            self._encoder = SentenceTransformer(self.model_name)
            self._embedding_dim = self._encoder.get_sentence_embedding_dimension()
            log.info("[faiss] Embedding dim: %d", self._embedding_dim)
        return self._encoder

    @property
    def embedding_dim(self) -> int:
        if self._embedding_dim is None:
            _ = self.encoder  # trigger load
        return self._embedding_dim

    # ------------------------------------------------------------------
    # Public API - Write
    # ------------------------------------------------------------------

    def add(
        self,
        text: str,
        scope: str = "shared",
        category: str = "other",
        tags: Optional[List[str]] = None,
        source: str = "manual",
        tier: str = "register",
        topic_id: Optional[str] = None,
    ) -> Memory:
        """Store a new memory in vault + FAISS index.

        Returns the Memory object.  Raises ValueError on validation failure.
        """
        mem = self.vault.create_memory(
            text=text, scope=scope, category=category,
            tags=tags, source=source, tier=tier, topic_id=topic_id,
        )
        self._embed_and_add(mem)
        self._save_index()
        return mem

    def remember(
        self,
        text: str,
        scope: str = "shared",
        category: str = "other",
        source: str = "chat",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """High-level 'remember this' convenience method.

        Returns a status dict.
        """
        tags = list(tags or [])
        if "remembered" not in tags:
            tags.append("remembered")
        try:
            mem = self.add(
                text=text, scope=scope, category=category,
                tags=tags, source=source, tier="register",
            )
            return {
                "status": "remembered",
                "id": mem.id,
                "scope": mem.scope,
                "category": mem.category,
            }
        except ValueError as exc:
            return {"status": "rejected", "reason": str(exc)}

    def update(
        self,
        memory_id: str,
        text: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Memory:
        """Update a memory in vault and re-embed if text changed.

        Returns the new Memory version.
        """
        new_ver = self.vault.update_memory(
            memory_id, text=text, category=category, tags=tags,
        )
        if text is not None:
            # Text changed -> need to re-embed
            # Mark old index entry as deleted, add new embedding
            self._deleted_ids.add(memory_id)
            self._embed_and_add(new_ver)
            self._save_index()
        return new_ver

    def delete(self, memory_id: str) -> bool:
        """Soft-delete a memory in vault and exclude from FAISS results."""
        ok = self.vault.delete_memory(memory_id)
        if ok:
            self._deleted_ids.add(memory_id)
            self._save_index()
        return ok

    def bulk_delete(self, memory_ids: List[str]) -> Dict[str, List[str]]:
        """Soft-delete multiple memories."""
        result = self.vault.bulk_delete(memory_ids)
        for mid in result["deleted"]:
            self._deleted_ids.add(mid)
        if result["deleted"]:
            self._save_index()
        return result

    # ------------------------------------------------------------------
    # Public API - Read / Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        scope: Optional[Union[str, List[str]]] = None,
        category: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Semantic search.  Returns list of dicts with memory fields + score.

        Results are sorted by cosine similarity (highest first).
        Deleted memories are excluded.  Scope/category filters applied.
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        # Embed query
        q_vec = self.encoder.encode([query], convert_to_numpy=True).astype("float32")
        faiss.normalize_L2(q_vec)

        # Search more than needed to account for filtered-out results
        search_k = min(top_k * 5, self.index.ntotal)
        distances, indices = self.index.search(q_vec, search_k)

        scope_set = _normalize_scopes(scope)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            if idx >= len(self._idx_to_id):
                continue
            vault_id = self._idx_to_id[idx]
            if vault_id in self._deleted_ids:
                continue

            # Look up from vault for current data
            mem = self.vault.get_memory(vault_id)
            if mem is None:
                continue

            if scope_set and mem.scope not in scope_set:
                continue
            if category and mem.category != category.lower():
                continue

            results.append({
                "id": mem.id,
                "text": mem.text,
                "scope": mem.scope,
                "category": mem.category,
                "tier": mem.tier,
                "tags": mem.tags,
                "topic_id": mem.topic_id,
                "source": mem.source,
                "created_at": mem.created_at,
                "score": round(float(dist), 4),
            })
            if len(results) >= top_k:
                break

        return results

    def recall(
        self,
        scope: Optional[Union[str, List[str]]] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[Memory]:
        """Return active memories from vault, newest first.

        This is a non-semantic list operation (no embedding needed).
        """
        active = self.vault.read_active()
        scope_set = _normalize_scopes(scope)
        results = []
        for m in active:
            if scope_set and m.scope not in scope_set:
                continue
            if category and m.category != category.lower():
                continue
            if tags and not set(tags) & set(m.tags):
                continue
            results.append(m)
        results.sort(key=lambda m: m.created_at, reverse=True)
        return results[:limit]

    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a single memory by id."""
        return self.vault.get_memory(memory_id)

    def list_all(
        self,
        scope: Optional[Union[str, List[str]]] = None,
    ) -> List[Memory]:
        """List all active memories, optionally filtered by scope."""
        active = self.vault.read_active()
        scope_set = _normalize_scopes(scope)
        if scope_set:
            active = [m for m in active if m.scope in scope_set]
        return sorted(active, key=lambda m: m.created_at, reverse=True)

    # ------------------------------------------------------------------
    # Stats & Maintenance
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """Combined vault + FAISS statistics."""
        vault_stats = self.vault.stats()
        active = vault_stats["active_count"]
        raw = vault_stats["raw_lines"]
        vault_stats["active_memories"] = active  # alias for clarity
        vault_stats["faiss_vectors"] = self.index.ntotal if self.index else 0
        vault_stats["faiss_deleted"] = len(self._deleted_ids)
        vault_stats["faiss_effective"] = (
            (self.index.ntotal if self.index else 0) - len(self._deleted_ids)
        )
        vault_stats["vault_total_lines"] = raw
        vault_stats["embedding_model"] = self.model_name
        vault_stats["faiss_dir"] = str(self.faiss_dir)
        # Backward-compat keys for web dashboard templates
        vault_stats["max_active"] = "∞"
        vault_stats["utilization_pct"] = 0
        vault_stats["compactable_lines"] = max(0, raw - active)
        vault_stats["bloat_ratio"] = round(raw / max(active, 1), 1)
        vault_stats["in_sync"] = vault_stats["faiss_effective"] == active
        return vault_stats

    def compact(self) -> Dict[str, Any]:
        """Compact vault (remove old versions/tombstones) and rebuild index."""
        result = self.vault.compact()
        rebuild_result = self.rebuild_index()
        result["faiss_vectors"] = rebuild_result["vectors"]
        return result

    def rebuild_index(self) -> Dict[str, Any]:
        """Rebuild the FAISS index from scratch using all active vault memories.

        Use after vault compaction, manual vault edits, or if the index
        file is lost/corrupted.
        """
        active = self.vault.read_active()
        if not active:
            dim = self.embedding_dim
            self.index = faiss.IndexFlatIP(dim)
            self._idx_to_id = []
            self._id_to_idx = {}
            self._deleted_ids = set()
            self._save_index()
            return {"status": "ok", "vectors": 0, "message": "No active memories"}

        texts = [m.text for m in active]
        ids = [m.id for m in active]

        log.info("[faiss] Rebuilding index from %d vault memories...", len(active))
        embeddings = self.encoder.encode(
            texts, batch_size=32, show_progress_bar=False,
            convert_to_numpy=True,
        ).astype("float32")
        faiss.normalize_L2(embeddings)

        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings)

        self._idx_to_id = list(ids)
        self._id_to_idx = {vid: i for i, vid in enumerate(ids)}
        self._deleted_ids = set()

        self._save_index()
        log.info("[faiss] Index rebuilt: %d vectors", len(active))
        return {"status": "ok", "vectors": len(active)}

    # ------------------------------------------------------------------
    # Index persistence
    # ------------------------------------------------------------------

    def _save_index(self) -> None:
        """Save FAISS index + mapping to disk."""
        if self.index is None:
            return
        index_path = self.faiss_dir / "index.faiss"
        meta_path = self.faiss_dir / "index_meta.json"

        faiss.write_index(self.index, str(index_path))

        meta = {
            "model_name": self.model_name,
            "idx_to_id": self._idx_to_id,
            "deleted_ids": list(self._deleted_ids),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f)

    def _load_or_build(self) -> None:
        """Try loading cached FAISS index, otherwise build from vault."""
        index_path = self.faiss_dir / "index.faiss"
        meta_path = self.faiss_dir / "index_meta.json"

        if index_path.exists() and meta_path.exists():
            try:
                self.index = faiss.read_index(str(index_path))
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                self._idx_to_id = meta.get("idx_to_id", [])
                self._id_to_idx = {vid: i for i, vid in enumerate(self._idx_to_id)}
                self._deleted_ids = set(meta.get("deleted_ids", []))

                # Validate: check the model matches
                if meta.get("model_name") != self.model_name:
                    log.warning("[faiss] Model mismatch, rebuilding index")
                    self.rebuild_index()
                    return

                # Sync: check for vault memories not in index
                active_ids = {m.id for m in self.vault.read_active()}
                indexed_ids = set(self._idx_to_id) - self._deleted_ids
                missing = active_ids - indexed_ids
                if missing:
                    log.info("[faiss] %d new vault memories to index", len(missing))
                    for mid in missing:
                        mem = self.vault.get_memory(mid)
                        if mem:
                            self._embed_and_add(mem)
                    self._save_index()

                # Mark any vault-deleted memories as deleted in index
                for vid in list(indexed_ids):
                    if vid not in active_ids:
                        self._deleted_ids.add(vid)

                log.info(
                    "[faiss] Loaded index: %d vectors (%d active)",
                    self.index.ntotal,
                    self.index.ntotal - len(self._deleted_ids),
                )
                return
            except Exception as exc:
                log.warning("[faiss] Failed to load index (%s), rebuilding", exc)

        # No cached index or load failed -> build from vault
        active = self.vault.read_active()
        if active:
            self.rebuild_index()
        else:
            # Empty vault -> empty index
            dim = self.embedding_dim
            self.index = faiss.IndexFlatIP(dim)
            self._idx_to_id = []
            self._id_to_idx = {}
            self._deleted_ids = set()

    def _embed_and_add(self, mem: Memory) -> None:
        """Embed a single memory and add to the FAISS index."""
        vec = self.encoder.encode([mem.text], convert_to_numpy=True).astype("float32")
        faiss.normalize_L2(vec)

        if self.index is None:
            dim = vec.shape[1]
            self.index = faiss.IndexFlatIP(dim)

        self.index.add(vec)
        idx = self.index.ntotal - 1
        # Extend the mapping
        while len(self._idx_to_id) <= idx:
            self._idx_to_id.append("")
        self._idx_to_id[idx] = mem.id
        self._id_to_idx[mem.id] = idx


def _normalize_scopes(scope) -> set:
    if scope is None:
        return set()
    if isinstance(scope, str):
        return {scope.lower()}
    return {s.lower() for s in scope}
