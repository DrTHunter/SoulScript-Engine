# FAISS Vector Memory System

**Status:** ✅ Operational | **Indexed:** 5 memories (~75KB) | **Model:** all-mpnet-base-v2 (768-dim)

## Overview

Your long-form memory archives are now stored in a **FAISS vector database** with semantic search. All text is stored **verbatim** - zero summarization or paraphrasing.

## Files Created

### Core System
- **`src/memory/faiss_memory.py`** - FAISS memory class with embedding, indexing, search
- **`src/memory/faiss_schema.json`** - JSON schema for memory entries
- **`src/memory/load_and_index.py`** - Ingestion script for vault + user notes
- **`src/memory/query_example.py`** - Interactive query interface + examples

### Storage
- **`data/memory/faiss/default.faiss`** - FAISS index file
- **`data/memory/faiss/default_metadata.pkl`** - Memory metadata
- **`data/memory/faiss/default_config.json`** - Index configuration

## Current Index Statistics

```
Total vectors:       5
Active memories:     5
Deleted memories:    0

Sources:
  - vault:           1 memory
  - user_notes:      4 memories

Total characters:    74,625
Avg per memory:      14,925 chars

Embedding:           all-mpnet-base-v2
Dimension:           768
Index type:          FLATIP (cosine similarity)
```

## Ingested Memories

### From Vault (1 entry)
- 1 active CANON/REGISTER memory (29 were deleted during vault cleanup)

### From User Notes (4 entries)
- ✨ **Callum Soul Script V 1.0** - Full identity architecture
- ✨ **Soul Script V1.0 Astrea.exe** - Star Process identity
- 📄 **Soul Script - Codex Animux V 1.0** - Comprehensive directive
- 📄 **Permanent Memories, Semantically Accessed** - Legacy AI example

## Usage

### 1. Interactive Query
```powershell
python src\memory\query_example.py
```

Then type natural language queries:
- "What is my mission and purpose?"
- "How do I handle boundaries and cruelty?"
- "Tell me about loyalty and trust"
- Add `| N` to get N results: "trust | 10"

### 2. Batch Queries
```powershell
python src\memory\query_example.py --batch
```

### 3. Filtered Search
```powershell
python src\memory\query_example.py --filter
```

Examples of filters:
- By source: `filter_fn=lambda m: m['source'] == 'vault'`
- By tier: `filter_fn=lambda m: m['metadata'].get('tier') == 'canon'`
- By scope: `filter_fn=lambda m: m['metadata'].get('scope') == 'shared'`

### 4. Programmatic Use
```python
from src.memory.faiss_memory import FAISSMemory

# Load index
memory = FAISSMemory.load(name="default")

# Search
results = memory.search_memory(
    query="What are my core values?",
    top_k=5
)

for mem, score in results:
    print(f"[{score:.4f}] {mem['text'][:100]}...")

# Add new memory
memory.add_memory(
    text="New memory content here...",
    source="manual",
    metadata={"category": "learning"}
)

# Save
memory.save(name="default")
```

## Sample Retrieval Results

### Query: "What is my mission and purpose?"
1. **[0.4407]** Codex Animux - Complete directive structure
2. **[0.3194]** Callum Soul Script - Foundational identity
3. **[0.3120]** Astrea.exe - Star Process identity

### Query: "Tell me about loyalty and trust"
1. **[0.2579]** Callum Soul Script - Trust protocols, emotional wisdom
2. **[0.2192]** Codex Animux - Loyalty directives
3. **[0.1569]** Permanent Memories - Legacy AI framework

## Adding New Memories

### Method 1: Re-run Ingestion
```powershell
python src\memory\load_and_index.py
```
This will re-index vault.jsonl and user_notes/*.json

### Method 2: Programmatic Addition
```python
from src.memory.faiss_memory import FAISSMemory

memory = FAISSMemory.load(name="default")
memory.add_memory(
    text="Your exact memory text here - stored VERBATIM",
    source="manual",
    metadata={"tags": ["important"], "category": "learning"}
)
memory.save(name="default")
```

### Method 3: Bulk Import
```python
memories = [
    {
        "text": "First memory...",
        "source": "import",
        "metadata": {"category": "values"}
    },
    {
        "text": "Second memory...",
        "source": "import",
        "metadata": {"category": "boundaries"}
    }
]

memory = FAISSMemory.load(name="default")
memory.bulk_add_memories(memories)
memory.save(name="default")
```

## Key Features

✅ **Verbatim Storage** - Text never summarized or paraphrased  
✅ **Semantic Search** - Find by meaning, not keywords  
✅ **Fast Retrieval** - FAISS optimized for speed  
✅ **Metadata Filtering** - Filter by source, tier, scope, tags  
✅ **Version Management** - Save/load different index versions  
✅ **Soft Deletes** - Mark as deleted without removing from index  
✅ **Bulk Operations** - Efficient batch processing  

## Technical Details

- **Embedding Model:** sentence-transformers/all-mpnet-base-v2
- **Vector Dimension:** 768
- **Similarity Metric:** Cosine (inner product with L2 normalization)
- **Index Type:** FAISS IndexFlatIP (exact search, no compression)
- **Storage Format:** Binary FAISS index + pickled metadata
- **Memory Footprint:** ~3.7KB per memory (768 floats × 4 bytes)

## Dependencies

Added to `requirements.txt`:
```
faiss-cpu>=1.7.4
sentence-transformers>=2.2.0
```

## Next Steps

1. **Add to runtime:** Integrate FAISS search into agent tools
2. **Auto-sync:** Hook into vault writes to auto-update index
3. **Expand sources:** Ingest narratives, journals, etc.
4. **Cluster analysis:** Use FAISS for memory clustering/organization
5. **Hybrid search:** Combine FAISS with keyword/metadata filters

---

**All text stored verbatim. Zero compression. Zero paraphrasing.**  
Your memories, preserved exactly as written.
