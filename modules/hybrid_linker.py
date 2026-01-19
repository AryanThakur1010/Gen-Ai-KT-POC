from typing import List, Set
from modules.embedding_manager import collection, generate_embedding, query_by_tags
from config import SIMILARITY_THRESHOLD


class HybridLinker:
    """Multi-strategy linker."""
    
    def __init__(self, chunk_map, all_chunks):
        self.chunk_map = chunk_map
        self.all_chunks = all_chunks
        self.heading_index = {
            chunk.heading.lower(): chunk.chunk_id 
            for chunk in all_chunks
        }
        
    def find_links(self, chunk, tags, max_links=10) -> List[str]:
        """Find links using 3-tier strategy."""
        linked_ids = set()
        
        # Tier 1: Deterministic
        deterministic = self._deterministic_links(chunk)
        linked_ids.update(deterministic)
        
        if len(linked_ids) >= max_links:
            return list(linked_ids)[:max_links]
        
        # Tier 2: Tag-filtered
        if len(linked_ids) < max_links:
            tag_filtered = self._tag_filtered_links(chunk, tags, max_links - len(linked_ids))
            linked_ids.update(tag_filtered)
        
        if len(linked_ids) >= max_links // 2:
            return list(linked_ids)[:max_links]
        
        # Tier 3: Full semantic
        if len(linked_ids) < max_links // 2:
            semantic = self._semantic_links(chunk, max_links - len(linked_ids))
            linked_ids.update(semantic)
        
        linked_ids.discard(chunk.chunk_id)
        return list(linked_ids)[:max_links]
    
    def _deterministic_links(self, chunk) -> Set[str]:
        """Tier 1: Structural links."""
        links = set()
        
        if chunk.parent_id:
            links.add(chunk.parent_id)
        
        links.update(chunk.siblings[:3])
        links.update(chunk.children[:3])
        
        # Exact heading matches
        content_lower = chunk.get_text_without_images().lower()
        for heading, chunk_id in self.heading_index.items():
            if heading in content_lower and chunk_id != chunk.chunk_id:
                links.add(chunk_id)
                if len(links) >= 8:
                    break
        
        return links
    
    def _tag_filtered_links(self, chunk, tags, limit) -> Set[str]:
        """Tier 2: Tag-filtered semantic."""
        if not tags:
            return set()
        
        try:
            tag_results = query_by_tags(tags, n_results=30)
            if not tag_results or not tag_results.get('ids'):
                return set()
            
            text = chunk.get_text_without_images()
            if not text.strip():
                return set()
            
            embedding = generate_embedding(text)
            if not embedding:
                return set()
            
            results = collection.query(
                query_embeddings=[embedding],
                n_results=limit * 2,
                where={"chunk_id": {"$in": tag_results['ids']}}
            )
            
            links = set()
            for chunk_id, distance in zip(results['ids'][0], results['distances'][0]):
                if distance < SIMILARITY_THRESHOLD and chunk_id != chunk.chunk_id:
                    links.add(chunk_id)
                    if len(links) >= limit:
                        break
            
            return links
        except:
            return set()
    
    def _semantic_links(self, chunk, limit) -> Set[str]:
        """Tier 3: Full semantic search."""
        try:
            text = chunk.get_text_without_images()
            if not text.strip():
                return set()
            
            embedding = generate_embedding(text)
            if not embedding:
                return set()
            
            results = collection.query(
                query_embeddings=[embedding],
                n_results=limit * 2
            )
            
            links = set()
            for chunk_id, distance in zip(results['ids'][0], results['distances'][0]):
                if distance < SIMILARITY_THRESHOLD and chunk_id != chunk.chunk_id:
                    links.add(chunk_id)
                    if len(links) >= limit:
                        break
            
            return links
        except:
            return set()
    
    def get_chunk_title(self, chunk_id):
        """Get title for chunk ID."""
        chunk = self.chunk_map.get(chunk_id)
        return chunk.heading if chunk else chunk_id


def generate_backlinks_section(linked_chunk_ids, linker):
    """Generate backlinks section."""
    if not linked_chunk_ids:
        return ""
    
    backlinks = [f"- [[{linker.get_chunk_title(cid)}]]" for cid in linked_chunk_ids]
    return "\n\n---\n\n**Related Notes:**\n" + "\n".join(backlinks)
