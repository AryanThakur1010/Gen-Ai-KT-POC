from typing import List
import hashlib
from modules.utils.utils import count_tokens, strip_images
from config import *


class DocumentChunk:
    """Represents a chunk of document content."""
    
    def __init__(self, heading, level, content, parent_id=None, doc_title=""):
        self.heading = heading
        self.level = level
        self.content = content
        self.parent_id = parent_id
        self.doc_title = doc_title
        self.chunk_id = self._generate_id()
        self.children = []
        self.siblings = []
        
    def _generate_id(self):
        """Generate unique ID."""
        text = f"{self.doc_title}_{self.heading}_{self.level}"
        return hashlib.md5(text.encode()).hexdigest()[:12]
    
    def get_text_content(self, include_images=True):
        """Get text content."""
        texts = []
        for item in self.content:
            if item.type in ['paragraph', 'table']:
                texts.append(item.text)
            elif item.type == 'image' and item.image_data and include_images:
                texts.append(f"\n![Image]({item.image_data})\n")
        return "\n\n".join(texts)
    
    def get_text_without_images(self):
        """Get text without images."""
        return strip_images(self.get_text_content())
    
    def get_token_count(self):
        """Count tokens (without images)."""
        return count_tokens(self.get_text_without_images())
    
    def __repr__(self):
        return f"Chunk(H{self.level}: {self.heading[:30]})"


class AdaptiveHierarchicalChunker:
    """Adaptive chunker that splits by headings intelligently."""
    
    def __init__(self, structured_content, document_title):
        self.content = structured_content
        self.document_title = document_title
        self.chunks = []
        self.chunk_map = {}
        
    def create_chunks(self) -> List[DocumentChunk]:
        """Create chunks using adaptive strategy."""
        print(f"     Starting adaptive chunking...")
        
        # Start with H1 chunking
        h1_sections = self._group_by_heading_level(PRIMARY_HEADING_LEVEL)
        
        for section in h1_sections:
            self._process_section(section, level=PRIMARY_HEADING_LEVEL, parent_id=None)
        
        # Set siblings
        self._set_siblings()
        
        print(f"    ✓ Created {len(self.chunks)} adaptive chunks")
        return self.chunks
    
    def _group_by_heading_level(self, target_level):
        """Group content by heading level."""
        sections = []
        current_section = {'heading': None, 'content': [], 'level': target_level}
        
        for item in self.content:
            if item.type == 'heading' and item.level == target_level:
                # Save previous section
                if current_section['heading'] or current_section['content']:
                    sections.append(current_section)
                # Start new section
                current_section = {'heading': item.text, 'content': [], 'level': target_level}
            else:
                current_section['content'].append(item)
        
        # Save last section
        if current_section['heading'] or current_section['content']:
            sections.append(current_section)
        
        return sections
    
    def _process_section(self, section, level, parent_id):
        """Process a section, splitting if needed."""
        heading = section['heading'] or f"Section {len(self.chunks)+1}"
        content = section['content']
        
        # Calculate token count
        temp_chunk = DocumentChunk(heading, level, content, parent_id, self.document_title)
        token_count = temp_chunk.get_token_count()
        
        # If within limit, create chunk
        if token_count <= MAX_CHUNK_CONTENT_TOKENS:
            chunk = DocumentChunk(heading, level, content, parent_id, self.document_title)
            self.chunks.append(chunk)
            self.chunk_map[chunk.chunk_id] = chunk
            return chunk.chunk_id
        
        # Too large - need to split
        print(f"        Splitting '{heading[:50]}' ({token_count} tokens)")
        
        # Try splitting by next heading level
        next_level = level + 1
        
        if next_level <= MAX_HEADING_LEVEL:
            # Check if there are sub-headings
            has_subheadings = any(item.type == 'heading' and item.level == next_level for item in content)
            
            if has_subheadings:
                # Create parent chunk (empty content, just structure)
                parent_chunk = DocumentChunk(heading, level, [], parent_id, self.document_title)
                self.chunks.append(parent_chunk)
                self.chunk_map[parent_chunk.chunk_id] = parent_chunk
                
                # Split by sub-headings
                sub_sections = self._split_by_heading_level(content, next_level)
                for sub_section in sub_sections:
                    child_id = self._process_section(sub_section, next_level, parent_chunk.chunk_id)
                    if child_id:
                        parent_chunk.children.append(child_id)
                
                return parent_chunk.chunk_id
        
        # Last resort: split by paragraph count
        return self._split_by_paragraphs(heading, level, content, parent_id)
    
    def _split_by_heading_level(self, content, target_level):
        """Split content by specific heading level."""
        sections = []
        current_section = {'heading': None, 'content': [], 'level': target_level}
        
        for item in content:
            if item.type == 'heading' and item.level == target_level:
                if current_section['heading'] or current_section['content']:
                    sections.append(current_section)
                current_section = {'heading': item.text, 'content': [], 'level': target_level}
            else:
                current_section['content'].append(item)
        
        if current_section['heading'] or current_section['content']:
            sections.append(current_section)
        
        return sections
    
    def _split_by_paragraphs(self, heading, level, content, parent_id):
        """Split by paragraph groups as last resort."""
        print(f"        → Splitting '{heading[:40]}' by paragraphs")
        
        # Create parent
        parent_chunk = DocumentChunk(heading, level, [], parent_id, self.document_title)
        self.chunks.append(parent_chunk)
        self.chunk_map[parent_chunk.chunk_id] = parent_chunk
        
        # Group paragraphs
        current_group = []
        current_tokens = 0
        part_num = 1
        
        for item in content:
            item_tokens = count_tokens(strip_images(item.text)) if item.type != 'image' else 50
            
            if current_tokens + item_tokens > MAX_CHUNK_CONTENT_TOKENS and current_group:
                # Save current group
                sub_chunk = DocumentChunk(
                    f"{heading} (Part {part_num})",
                    level + 1,
                    current_group,
                    parent_chunk.chunk_id,
                    self.document_title
                )
                self.chunks.append(sub_chunk)
                self.chunk_map[sub_chunk.chunk_id] = sub_chunk
                parent_chunk.children.append(sub_chunk.chunk_id)
                
                # Reset
                current_group = [item]
                current_tokens = item_tokens
                part_num += 1
            else:
                current_group.append(item)
                current_tokens += item_tokens
        
        # Save last group
        if current_group:
            sub_chunk = DocumentChunk(
                f"{heading} (Part {part_num})",
                level + 1,
                current_group,
                parent_chunk.chunk_id,
                self.document_title
            )
            self.chunks.append(sub_chunk)
            self.chunk_map[sub_chunk.chunk_id] = sub_chunk
            parent_chunk.children.append(sub_chunk.chunk_id)
        
        return parent_chunk.chunk_id
    
    def _set_siblings(self):
        """Set sibling relationships."""
        for chunk in self.chunks:
            if chunk.parent_id:
                parent = self.chunk_map.get(chunk.parent_id)
                if parent:
                    chunk.siblings = [
                        cid for cid in parent.children
                        if cid != chunk.chunk_id
                    ]