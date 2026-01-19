from typing import Dict
from modules.utils.utils import get_text_preview, strip_images, truncate_text, count_tokens
from config import *


class TreeManager:
    """Manages document tree with minimal context."""
    
    def __init__(self, chunks, max_levels=2):
        self.chunks = chunks
        self.chunk_map = {c.chunk_id: c for c in chunks}
        self.max_levels = max_levels
        
    def get_minimal_context(self, chunk_id: str) -> Dict:
        """Get lightweight context - TITLES ONLY, no full text."""
        chunk = self.chunk_map.get(chunk_id)
        if not chunk:
            return {}
        
        # Only return titles/headings, never full content
        context = {
            'breadcrumb': self._get_breadcrumb(chunk),
            'parent_title': self._get_parent_title(chunk),
            'sibling_titles': self._get_sibling_titles(chunk),
            'child_titles': self._get_child_titles(chunk)
        }
        
        return context
    
    def _get_breadcrumb(self, chunk):
        """Get breadcrumb trail."""
        chain = []
        current = chunk
        
        while current.parent_id and len(chain) < 5:
            parent = self.chunk_map.get(current.parent_id)
            if parent:
                chain.insert(0, parent.heading)
                current = parent
            else:
                break
        
        chain.append(chunk.heading)
        return " > ".join(chain)
    
    def _get_parent_title(self, chunk):
        """Get parent title only."""
        if chunk.parent_id:
            parent = self.chunk_map.get(chunk.parent_id)
            return parent.heading if parent else None
        return None
    
    def _get_sibling_titles(self, chunk):
        """Get sibling titles only."""
        return [
            self.chunk_map[sid].heading 
            for sid in chunk.siblings[:5] 
            if sid in self.chunk_map
        ]
    
    def _get_child_titles(self, chunk):
        """Get child titles only."""
        return [
            self.chunk_map[cid].heading 
            for cid in chunk.children[:5] 
            if cid in self.chunk_map
        ]
    
    def get_all_headings(self):
        """Get all headings (limited)."""
        return [c.heading for c in self.chunks if c.level > 0][:MAX_AVAILABLE_HEADINGS]
