from modules.embedding_manager import collection, generate_embedding, chunk_text
import os
import re
import numpy as np

def strip_embedded_images(md_content):
    """
    Remove base64 embedded images from markdown to reduce token count.
    Keeps image placeholders for structure but removes base64 data.
    
    Args:
        md_content: Markdown text with embedded images
        
    Returns:
        Cleaned markdown text without base64 image data
    """
    # Pattern to match: ![](data:image/...;base64,LONG_BASE64_STRING)
    # Replace with: ![](image)
    pattern = r'!\[\]\(data:image/[^;]+;base64,[A-Za-z0-9+/=]+\)'
    cleaned = re.sub(pattern, '![](image)', md_content)
    
    return cleaned

def generate_backlinks(current_doc, current_title, threshold=0.25, top_k=10):
    """
    Find semantically similar docs and return backlinks.
    Uses chunking + averaging strategy for long documents.
    
    Args:
        current_doc: The full text of the current document
        current_title: Title of the current document (to exclude self-references)
        threshold: Similarity threshold (distance-based, lower = more similar)
        top_k: Number of results to retrieve
    
    Returns:
        String containing backlinks in Obsidian format
    """
    # Strip embedded images before creating embedding
    cleaned_doc = strip_embedded_images(current_doc)
    
    # Check if document needs chunking
    chunks = chunk_text(cleaned_doc, max_tokens=6000, overlap=200)
    
    if len(chunks) == 1:
        # Single chunk - process normally
        current_embedding = generate_embedding(chunks[0])
    else:
        # Multiple chunks - average their embeddings
        print(f"    📊 Generating embedding from {len(chunks)} chunks...")
        chunk_embeddings = []
        for i, chunk in enumerate(chunks):
            chunk_emb = generate_embedding(chunk)
            chunk_embeddings.append(chunk_emb)
        
        # Average all chunk embeddings to get document-level embedding
        current_embedding = np.mean(chunk_embeddings, axis=0).tolist()

    results = collection.query(
        query_embeddings=[current_embedding],
        n_results=top_k
    )

    backlinks = []
    seen_docs = set()  # Track unique parent documents
    
    for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
        # Determine the document title (handle both chunks and full docs)
        if 'parent_doc' in meta:
            doc_title = meta['parent_doc']
        else:
            doc_title = meta['title']
        
        # Skip self-references
        if doc_title == current_title:
            continue
        
        # Skip duplicates (multiple chunks from same doc)
        if doc_title in seen_docs:
            continue
        
        # Check similarity threshold
        if dist < threshold:  # Lower distance = higher similarity
            backlinks.append(doc_title)
            seen_docs.add(doc_title)

    if backlinks:
        backlink_text = "\n\n---\n\n**Related Notes:**\n" + "\n".join([f"- [[{b}]]" for b in backlinks])
        return backlink_text
    return ""

def get_existing_backlinks(md_content):
    """
    Extract existing backlinks from markdown content.
    Returns list of note titles that are already linked.
    """
    backlinks = []
    in_backlinks_section = False
    
    for line in md_content.split('\n'):
        if '**Related Notes:**' in line or '**Backlinks:**' in line:
            in_backlinks_section = True
            continue
        
        if in_backlinks_section:
            if line.startswith('- [[') and line.endswith(']]'):
                # Extract title from [[Title]]
                title = line[4:-2]  # Remove '- [[' and ']]'
                backlinks.append(title)
            elif line.strip() and not line.startswith('-'):
                # End of backlinks section
                break
    
    return backlinks

def update_bidirectional_links(source_title, target_titles, output_dir):
    """
    Update target documents to include backlinks to source document.
    
    Args:
        source_title: Title of the document that links to targets
        target_titles: List of document titles that should link back
        output_dir: Directory containing markdown files
    """
    for target_title in target_titles:
        target_path = os.path.join(output_dir, f"{target_title}.md")
        
        # Skip if target file doesn't exist
        if not os.path.exists(target_path):
            continue
        
        # Read target file
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check if backlink already exists
        existing_backlinks = get_existing_backlinks(content)
        
        if source_title in existing_backlinks:
            # Already has this backlink
            continue
        
        # Add backlink to target
        if '**Related Notes:**' in content or '**Backlinks:**' in content:
            # Backlinks section exists, append to it
            lines = content.split('\n')
            insert_idx = None
            
            for i, line in enumerate(lines):
                if '**Related Notes:**' in line or '**Backlinks:**' in line:
                    # Find the end of the backlinks section
                    j = i + 1
                    while j < len(lines) and (lines[j].startswith('-') or not lines[j].strip()):
                        j += 1
                    insert_idx = j - 1
                    break
            
            if insert_idx is not None:
                lines.insert(insert_idx + 1, f"- [[{source_title}]]")
                content = '\n'.join(lines)
        else:
            # No backlinks section, create one
            content += f"\n\n---\n\n**Related Notes:**\n- [[{source_title}]]"
        
        # Write updated content
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)