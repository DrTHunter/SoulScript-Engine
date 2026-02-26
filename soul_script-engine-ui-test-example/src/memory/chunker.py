"""Semantic chunker for Soul Scripts and long-form documents.

Splits documents by section headers while preserving hierarchy and context.
Each chunk is a complete section that can be retrieved as a whole unit.
"""

import re
from typing import Dict, List, Any, Optional


class SemanticChunker:
    """Chunks documents by semantic sections while preserving hierarchy."""
    
    def __init__(self, min_chunk_size: int = 100, max_chunk_size: int = 3000):
        """Initialize chunker.
        
        Args:
            min_chunk_size: Minimum characters per chunk (merge small sections)
            max_chunk_size: Maximum characters per chunk (split very long sections)
        """
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
    
    def chunk_by_headers(
        self,
        text: str,
        document_id: str,
        document_title: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Chunk text by markdown headers (### H3 sections).
        
        Args:
            text: Full document text
            document_id: Unique document identifier
            document_title: Document title (for hierarchical context)
            metadata: Additional metadata to attach to all chunks
            
        Returns:
            List of chunk dicts with text, metadata, and hierarchy info
        """
        chunks = []
        metadata = metadata or {}
        
        # Split by ### headers (H3)
        # Pattern: ### followed by optional emoji/symbols, then title
        section_pattern = r'^###\s+(.+?)$'
        
        lines = text.split('\n')
        current_section = {
            'title': document_title,
            'content': [],
            'start_line': 0,
        }
        
        for i, line in enumerate(lines):
            match = re.match(section_pattern, line, re.MULTILINE)
            
            if match:
                # Save previous section
                if current_section['content']:
                    chunks.append(self._build_chunk(
                        current_section,
                        document_id,
                        document_title,
                        metadata,
                    ))
                
                # Start new section
                section_title = match.group(1).strip()
                current_section = {
                    'title': section_title,
                    'content': [line],  # Include the header
                    'start_line': i,
                }
            else:
                current_section['content'].append(line)
        
        # Add final section
        if current_section['content']:
            chunks.append(self._build_chunk(
                current_section,
                document_id,
                document_title,
                metadata,
            ))
        
        # Post-process: merge small chunks, split large ones
        chunks = self._merge_small_chunks(chunks)
        chunks = self._split_large_chunks(chunks)
        
        # Add chunk indices
        for i, chunk in enumerate(chunks):
            chunk['metadata']['chunk_index'] = i
            chunk['metadata']['total_chunks'] = len(chunks)
        
        return chunks
    
    def _build_chunk(
        self,
        section: Dict,
        document_id: str,
        document_title: str,
        base_metadata: Dict,
    ) -> Dict[str, Any]:
        """Build a chunk dict from a section."""
        content = '\n'.join(section['content']).strip()
        section_title = section['title']
        
        # Build hierarchical path
        if section_title == document_title:
            section_path = document_title
        else:
            section_path = f"{document_title} > {section_title}"
        
        return {
            'text': content,  # VERBATIM section content
            'metadata': {
                **base_metadata,
                'document_id': document_id,
                'document_title': document_title,
                'section_title': section_title,
                'section_path': section_path,
                'char_count': len(content),
                'start_line': section['start_line'],
            }
        }
    
    def _merge_small_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """Merge chunks smaller than min_chunk_size with adjacent chunks."""
        if not chunks:
            return chunks
        
        merged = []
        i = 0
        
        while i < len(chunks):
            current = chunks[i]
            
            # If chunk is too small and not the last one, try to merge
            if (current['metadata']['char_count'] < self.min_chunk_size 
                and i < len(chunks) - 1):
                next_chunk = chunks[i + 1]
                
                # Merge content
                merged_text = current['text'] + '\n\n' + next_chunk['text']
                merged_title = f"{current['metadata']['section_title']} + {next_chunk['metadata']['section_title']}"
                
                merged_chunk = {
                    'text': merged_text,
                    'metadata': {
                        **current['metadata'],
                        'section_title': merged_title,
                        'section_path': f"{current['metadata']['document_title']} > {merged_title}",
                        'char_count': len(merged_text),
                        'merged': True,
                    }
                }
                merged.append(merged_chunk)
                i += 2  # Skip next chunk
            else:
                merged.append(current)
                i += 1
        
        return merged
    
    def _split_large_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """Split chunks larger than max_chunk_size at paragraph boundaries."""
        split_chunks = []
        
        for chunk in chunks:
            if chunk['metadata']['char_count'] <= self.max_chunk_size:
                split_chunks.append(chunk)
                continue
            
            # Split at double newlines (paragraphs)
            text = chunk['text']
            paragraphs = re.split(r'\n\n+', text)
            
            current_part = []
            current_size = 0
            part_index = 0
            
            for para in paragraphs:
                para_size = len(para)
                
                if current_size + para_size > self.max_chunk_size and current_part:
                    # Save current part
                    part_text = '\n\n'.join(current_part)
                    split_chunks.append({
                        'text': part_text,
                        'metadata': {
                            **chunk['metadata'],
                            'section_title': f"{chunk['metadata']['section_title']} (part {part_index + 1})",
                            'char_count': len(part_text),
                            'split': True,
                            'split_index': part_index,
                        }
                    })
                    current_part = [para]
                    current_size = para_size
                    part_index += 1
                else:
                    current_part.append(para)
                    current_size += para_size + 2  # +2 for \n\n
            
            # Add remaining content
            if current_part:
                part_text = '\n\n'.join(current_part)
                split_chunks.append({
                    'text': part_text,
                    'metadata': {
                        **chunk['metadata'],
                        'section_title': f"{chunk['metadata']['section_title']}" + (f" (part {part_index + 1})" if part_index > 0 else ""),
                        'char_count': len(part_text),
                        'split': part_index > 0,
                        'split_index': part_index if part_index > 0 else None,
                    }
                })
        
        return split_chunks
    
    def chunk_vault_memory(self, memory: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Chunk a vault memory (usually keeps as single chunk since they're small).
        
        Args:
            memory: Vault memory dict with text, metadata, etc.
            
        Returns:
            List with single chunk (vault memories are already small)
        """
        # Vault memories are typically small (< 1200 chars)
        # Keep as single chunks
        return [{
            'text': memory['text'],
            'metadata': {
                **memory.get('metadata', {}),
                'document_id': memory['id'],
                'document_title': f"[{memory['metadata'].get('tier', 'N/A')}] {memory['metadata'].get('category', 'N/A')}",
                'section_title': memory['text'][:50] + '...' if len(memory['text']) > 50 else memory['text'],
                'section_path': f"Vault > {memory['metadata'].get('scope', 'N/A')} > {memory['metadata'].get('category', 'N/A')}",
                'char_count': len(memory['text']),
            }
        }]


def chunk_soul_script(
    text: str,
    note_id: str,
    title: str,
    emoji: str,
    metadata: Optional[Dict] = None,
) -> List[Dict[str, Any]]:
    """Convenience function to chunk a Soul Script note.
    
    Args:
        text: Full Soul Script text
        note_id: Note ID
        title: Note title
        emoji: Note emoji
        metadata: Additional metadata
        
    Returns:
        List of chunk dicts ready for FAISS ingestion
    """
    chunker = SemanticChunker(min_chunk_size=200, max_chunk_size=2500)
    
    base_metadata = {
        'emoji': emoji,
        'is_canon': True,  # Soul Scripts are canon
        'immutable': True,  # Cannot be modified
        **(metadata or {}),
    }
    
    return chunker.chunk_by_headers(
        text=text,
        document_id=note_id,
        document_title=f"{emoji} {title}",
        metadata=base_metadata,
    )
