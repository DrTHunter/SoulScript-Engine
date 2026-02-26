"""Load JSON user notes from data/user_notes/ directory.

The web app allows users to create rich notes stored as JSON files.
This module loads non-trashed notes and extracts their content for
injection into agent prompts.
"""

import json
import os
import re
from typing import List, Optional


def strip_html(html_content: str) -> str:
    """Strip HTML tags from content, preserving text and structure."""
    if not html_content:
        return ""
    
    # Replace <br>, <hr>, </p>, </h2>, etc. with newlines
    text = re.sub(r'<(?:br|hr|/p|/h[1-6]|/li|/div)>', '\n', html_content)
    # Remove all remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode common HTML entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&amp;', '&')
    text = text.replace('&quot;', '"')
    # Clean up excessive whitespace
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    return text.strip()


def load_json_user_notes(notes_dir: str) -> str:
    """Load all non-trashed JSON user notes from the user_notes directory.
    
    Args:
        notes_dir: Path to data/user_notes directory
        
    Returns:
        Formatted markdown block with all note contents, or empty string if none found
    """
    index_path = os.path.join(notes_dir, "index.json")
    
    if not os.path.isfile(index_path):
        return ""
    
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    except (json.JSONDecodeError, IOError):
        return ""
    
    note_parts = []
    
    for entry in index:
        # Skip trashed notes
        if entry.get("trashed"):
            continue
            
        note_id = entry.get("id")
        if not note_id:
            continue
            
        note_path = os.path.join(notes_dir, f"{note_id}.json")
        if not os.path.isfile(note_path):
            continue
        
        try:
            with open(note_path, "r", encoding="utf-8") as f:
                note_data = json.load(f)
            
            content_html = note_data.get("content_html", "")
            if not content_html:
                continue
            
            # Strip HTML and get plain text
            content = strip_html(content_html)
            if not content:
                continue
            
            # Add title if available
            title = note_data.get("title", "Untitled Note")
            emoji = note_data.get("emoji", "📝")
            
            formatted = f"### {emoji} {title}\n\n{content}"
            note_parts.append(formatted)
            
        except (json.JSONDecodeError, IOError):
            # Skip problematic notes
            continue
    
    if not note_parts:
        return ""
    
    return "\n\n---\n\n".join(note_parts)
