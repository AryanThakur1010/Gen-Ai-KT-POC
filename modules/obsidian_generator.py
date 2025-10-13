from openai import AzureOpenAI
from config import *
import os
import textwrap
import re

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

def extract_images_from_text(text):
    """
    Extract embedded images from text and return text with placeholders.
    Returns: (text_without_images, image_list)
    """
    # Pattern to match embedded images
    image_pattern = r'!\[Image\]\(data:image/[^)]+\)'
    
    images = re.findall(image_pattern, text)
    
    # Replace images with numbered placeholders
    text_with_placeholders = text
    for i, img in enumerate(images):
        placeholder = f"<<<IMAGE_{i}>>>"
        text_with_placeholders = text_with_placeholders.replace(img, placeholder, 1)
    
    return text_with_placeholders, images

def reinsert_images(text, images):
    """
    Replace image placeholders with actual embedded images.
    """
    result = text
    for i, img in enumerate(images):
        placeholder = f"<<<IMAGE_{i}>>>"
        result = result.replace(placeholder, img)
    
    return result

def chunk_text(text, chunk_size=10000, overlap=200):
    """Split long text into overlapping chunks while preserving images."""
    # Extract images first
    text_no_images, images = extract_images_from_text(text)
    
    chunks = []
    start = 0
    while start < len(text_no_images):
        end = start + chunk_size
        chunk = text_no_images[start:end]
        chunks.append(chunk)
        start = end - overlap
    
    return chunks, images

def convert_to_lyt_markdown(content, title):
    """Convert long Word document content to LYT-style Markdown in chunks."""
    chunks, images = chunk_text(content)
    full_markdown_output = f"# {title}\n\n"

    print(f"🧩 Splitting '{title}' into {len(chunks)} chunks for processing...")

    for i, chunk in enumerate(chunks, 1):
        prompt = f"""Convert this text to clean Obsidian-compatible Markdown using LYT principles.

CRITICAL RULES:
1. Output ONLY the markdown - no preambles like "here is the conversion" or "sure"
2. DO NOT modify or remove <<<IMAGE_X>>> placeholders - keep them EXACTLY as they appear
3. Structure content with ## and ### headings
4. Use [[internal links]] for related concepts
5. Keep bullet points and formatting
6. Be concise and atomic

Text to convert:
{chunk}

Remember: Output the markdown directly with NO conversational text."""

        try:
            response = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": "You are a markdown converter. Output ONLY markdown with no commentary or explanations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3  # Lower temperature for more consistent output
            )
            md_chunk = response.choices[0].message.content.strip()
            
            # Remove any common AI preambles if they slip through
            md_chunk = re.sub(r'^(Sure[,!]?|Here is|Here\'s).*?(\n|:)', '', md_chunk, flags=re.IGNORECASE)
            md_chunk = re.sub(r'^```markdown\s*', '', md_chunk)
            md_chunk = re.sub(r'\s*```\s*$', '', md_chunk)
            
            full_markdown_output += md_chunk + "\n\n"

        except Exception as e:
            print(f"⚠️ Error in chunk {i}: {e}")
            # On error, include the original chunk
            full_markdown_output += chunk + "\n\n"
            continue

    # Reinsert all images at their original positions
    full_markdown_output = reinsert_images(full_markdown_output, images)

    print(f"✅ Completed conversion for: {title}")
    return full_markdown_output
