import os
from tqdm import tqdm
from modules.docx_extractor import extract_text_and_images
from modules.obsidian_generator import convert_to_lyt_markdown
from modules.embedding_manager import store_in_chroma
from modules.backlinker import generate_backlinks, update_bidirectional_links

INPUT_DIR = "data/input_docs"
OUTPUT_MD_DIR = "output/markdown"

os.makedirs(OUTPUT_MD_DIR, exist_ok=True)

# Note: No OUTPUT_IMG_DIR needed - images embedded in markdown!

# ---- PASS 1: Convert DOCX → Markdown + Store Embeddings ----
print("\n Step 1: Converting Word files and storing embeddings...\n")
print("ℹ  Images will be embedded directly in markdown files (no separate image files)\n")

# Debug: List all files in directory
all_files = os.listdir(INPUT_DIR)
print(f" Files found in {INPUT_DIR}:")
for f in all_files:
    print(f"   - {f} (ends with .docx: {f.endswith('.docx')})")
print()

processed_count = 0
for file in tqdm(os.listdir(INPUT_DIR), desc="Processing Word files"):
    if file.endswith(".docx") or file.endswith(".doc"):
        try:
            doc_path = os.path.join(INPUT_DIR, file)
            title = os.path.splitext(file)[0]
            
            print(f"\n  Processing: {title}")

            # Extract text and images (images as base64 data URLs)
            text, embedded_images = extract_text_and_images(doc_path)
            print(f"    ✓ Extracted {len(text)} characters, {len(embedded_images)} images (embedded)")
            
            # Convert to markdown with embedded images
            md_content = convert_to_lyt_markdown(text, title)
            print(f"    ✓ Converted to markdown ({len(md_content)} characters)")

            # Save Markdown (contains embedded images!)
            output_path = os.path.join(OUTPUT_MD_DIR, f"{title}.md")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"    ✓ Saved to {output_path}")

            # Store in Chroma (with automatic chunking)
            store_in_chroma(
                doc_id=title,
                text=md_content,
                metadata={"title": title, "source": file}
            )
            print(f"    ✓ Stored embeddings")
            
            processed_count += 1
            
        except Exception as e:
            print(f"    ✗ ERROR processing {file}: {str(e)}")
            import traceback
            traceback.print_exc()

print("\n Step 1 complete: All Markdown files created and embedded.\n")
print(f"   Successfully processed: {processed_count} documents\n")

# ---- PASS 2: Generate Backlinks (with bidirectional linking) ----
print(" Step 2: Generating semantic backlinks...\n")

# Track all backlink relationships for bidirectional updates
backlink_map = {}  # {source_title: [target_titles]}

for file in tqdm(os.listdir(OUTPUT_MD_DIR), desc="Linking Markdown files"):
    if file.endswith(".md"):
        title = os.path.splitext(file)[0]
        md_path = os.path.join(OUTPUT_MD_DIR, file)
        
        with open(md_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        # Generate backlinks (excluding self-references)
        backlinks_text = generate_backlinks(md_content, current_title=title, threshold=0.25, top_k=10)
        
        # Extract linked titles for bidirectional updating
        if backlinks_text:
            linked_titles = []
            for line in backlinks_text.split('\n'):
                if line.startswith('- [[') and line.endswith(']]'):
                    linked_titles.append(line[4:-2])
            
            backlink_map[title] = linked_titles
            
            # Append backlinks to file
            with open(md_path, "a", encoding="utf-8") as f:
                f.write(backlinks_text)

print("\n Step 3: Creating bidirectional links...\n")

# Update all target documents to link back to source
for source_title, target_titles in tqdm(backlink_map.items(), desc="Updating bidirectional links"):
    update_bidirectional_links(source_title, target_titles, OUTPUT_MD_DIR)

print("\n All documents processed with semantic bidirectional linking!")
print(f"\nSummary:")
print(f"   - Documents processed: {len([f for f in os.listdir(OUTPUT_MD_DIR) if f.endswith('.md')])}")
print(f"   - Bidirectional link pairs created: {sum(len(v) for v in backlink_map.values())}")
print(f"\n Note: Images are embedded directly in markdown files")
