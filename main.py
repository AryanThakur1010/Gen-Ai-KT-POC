import os
from tqdm import tqdm
from modules.docx_extractor import extract_structured_content
from modules.hierarchical_chunker import AdaptiveHierarchicalChunker
from modules.tree_manager import TreeManager
from modules.tag_extractor import extract_tags
from modules.obsidian_generator import generate_markdown_safe, create_frontmatter
from modules.embedding_manager import store_chunk
from modules.hybrid_linker import HybridLinker, generate_backlinks_section
from config import *
from modules.utils.utils import strip_images

os.makedirs(OUTPUT_MD_DIR, exist_ok=True)

print("\n" + "="*70)
print("   TOKEN-SAFE DOCUMENT PROCESSING PIPELINE")
print("="*70 + "\n")

all_documents = []


# PHASE 1: EXTRACTION & ADAPTIVE CHUNKING

print(" PHASE 1: Extraction & Adaptive Chunking\n")

doc_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(('.docx', '.doc'))]

for file in tqdm(doc_files, desc="Extracting documents"):
    try:
        doc_path = os.path.join(INPUT_DIR, file)
        title = os.path.splitext(file)[0]
        
        print(f"\n  Processing: {title}")
        
        # Extract
        structured_content = extract_structured_content(doc_path)
        print(f"     Extracted {len(structured_content)} blocks")
        
        # Adaptive chunking
        chunker = AdaptiveHierarchicalChunker(structured_content, title)
        chunks = chunker.create_chunks()
        
        # Extract tags
        full_text = " ".join([strip_images(c.get_text_without_images()) for c in chunks[:5]])
        tags = extract_tags(full_text[:5000], title)
        print(f"     Tags: {', '.join(tags)}")
        
        all_documents.append({
            'title': title,
            'chunks': chunks,
            'tags': tags,
            'file': file
        })
        
    except Exception as e:
        print(f"     ERROR: {e}")

print(f"\n Phase 1 Complete: {len(all_documents)} documents\n")


# PHASE 2: MARKDOWN GENERATION & EMBEDDING

print(" PHASE 2: Token-Safe Markdown Generation\n")

for doc_data in tqdm(all_documents, desc="Generating markdown"):
    try:
        title = doc_data['title']
        chunks = doc_data['chunks']
        tags = doc_data['tags']
        
        print(f"\n  Processing: {title}")
        
        tree_manager = TreeManager(chunks, max_levels=MAX_CONTEXT_LEVELS)
        all_headings = tree_manager.get_all_headings()
        
        markdown_chunks = []
        
        for chunk in chunks:
            if chunk.level == 0:
                continue
            
            context = tree_manager.get_minimal_context(chunk.chunk_id)
            markdown = generate_markdown_safe(chunk, context, all_headings)
            markdown_chunks.append(markdown)
            
            breadcrumb = context.get('breadcrumb', '')
            store_chunk(chunk, title, tags, breadcrumb)
        
        # Combine
        frontmatter = create_frontmatter(title, tags, chunks[0].chunk_id if chunks else "root")
        full_markdown = frontmatter + "\n\n".join(markdown_chunks)
        
        # Save
        output_path = os.path.join(OUTPUT_MD_DIR, f"{title}.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_markdown)
        
        print(f"     Generated {len(markdown_chunks)} sections")
        
    except Exception as e:
        print(f"     ERROR: {e}")
        import traceback
        traceback.print_exc()

print(f"\n Phase 2 Complete\n")


# PHASE 3: INTELLIGENT LINKING

print(" PHASE 3: Hybrid Linking\n")

all_chunks_flat = []
chunk_to_doc = {}

for doc_data in all_documents:
    for chunk in doc_data['chunks']:
        if chunk.level > 0:
            all_chunks_flat.append(chunk)
            chunk_to_doc[chunk.chunk_id] = doc_data

chunk_map = {c.chunk_id: c for c in all_chunks_flat}
linker = HybridLinker(chunk_map, all_chunks_flat)

for doc_data in tqdm(all_documents, desc="Creating links"):
    try:
        title = doc_data['title']
        chunks = doc_data['chunks']
        tags = doc_data['tags']
        
        print(f"\n  Linking: {title}")
        
        all_links = set()
        for chunk in chunks:
            if chunk.level == 0:
                continue
            links = linker.find_links(chunk, tags, max_links=8)
            all_links.update(links)
        
        backlinks_md = generate_backlinks_section(list(all_links), linker)
        
        if backlinks_md:
            output_path = os.path.join(OUTPUT_MD_DIR, f"{title}.md")
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(backlinks_md)
            print(f"     Added {len(all_links)} links")
        
    except Exception as e:
        print(f"     ERROR: {e}")

print(f"\n Phase 3 Complete\n")

print("\n" + "="*70)
print("    PROCESSING COMPLETE")
print("="*70)
print(f"\n Summary:")
print(f"   • Documents: {len(all_documents)}")
print(f"   • Total chunks: {len(all_chunks_flat)}")
print(f"   • Output: {OUTPUT_MD_DIR}")
print("\n")