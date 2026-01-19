from openai import AzureOpenAI
from config import *
import re
from modules.utils.utils import count_tokens, strip_images, truncate_text

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)


def generate_markdown_safe(chunk, context, all_headings):
    """Generate markdown with STRICT token limits."""
    
    # Get chunk content WITHOUT images first
    content_no_images = chunk.get_text_without_images()
    content_tokens = count_tokens(content_no_images)
    
    # If chunk itself is too large, truncate it
    if content_tokens > MAX_CHUNK_CONTENT_TOKENS:
        print(f"        Truncating chunk content ({content_tokens} -> {MAX_CHUNK_CONTENT_TOKENS} tokens)")
        content_no_images = truncate_text(content_no_images, MAX_CHUNK_CONTENT_TOKENS)
        content_tokens = MAX_CHUNK_CONTENT_TOKENS
    
    # Build minimal context string
    context_parts = []
    
    if context.get('parent_title'):
        context_parts.append(f"Parent: {context['parent_title']}")
    
    if context.get('sibling_titles'):
        siblings = ", ".join(context['sibling_titles'][:3])
        context_parts.append(f"Siblings: {siblings}")
    
    if context.get('child_titles'):
        children = ", ".join(context['child_titles'][:3])
        context_parts.append(f"Subsections: {children}")
    
    context_str = " | ".join(context_parts) if context_parts else "Root section"
    
    # Limit available headings
    headings_str = ", ".join(all_headings[:10])
    
    # Build prompt with token counting
    prompt = f"""Convert this section to Obsidian markdown.

CONTEXT: {context_str}
HEADING: {chunk.heading}
AVAILABLE LINKS: {headings_str}

CONTENT:
{content_no_images}

RULES:
1. Output ONLY markdown
2. Use ## for heading
3. Add [[links]] to related topics from available links
4. Be concise

Markdown:"""

    # Check total prompt size
    total_tokens = count_tokens(prompt) + 500  # Buffer for system message
    
    if total_tokens > MAX_TOTAL_PROMPT_TOKENS:
        print(f"        Prompt too large ({total_tokens} tokens), using fallback")
        return generate_fallback_markdown(chunk)
    
    try:
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": "Convert to markdown. Output ONLY markdown."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=3000
        )
        
        markdown = response.choices[0].message.content.strip()
        markdown = re.sub(r'^(Sure|Here is).*?\n', '', markdown, flags=re.IGNORECASE)
        markdown = re.sub(r'^```markdown\s*|\s*```$', '', markdown)
        
        # Re-add images from original chunk
        images = chunk.get_text_content().split('\n')
        image_lines = [line for line in images if line.strip().startswith('![Image](data:image')]
        
        if image_lines:
            markdown += "\n\n" + "\n\n".join(image_lines)
        
        return markdown
        
    except Exception as e:
        print(f"        Generation failed: {e}")
        return generate_fallback_markdown(chunk)


def generate_fallback_markdown(chunk):
    """Fallback: basic markdown without AI."""
    content = chunk.get_text_content()
    return f"## {chunk.heading}\n\n{content}"


def create_frontmatter(title, tags, chunk_id, parent_id=None):
    """Create YAML frontmatter."""
    fm = ["---"]
    fm.append(f'title: "{title}"')
    fm.append(f'tags: [{", ".join(tags)}]')
    fm.append(f'chunk_id: "{chunk_id}"')
    if parent_id:
        fm.append(f'parent: "{parent_id}"')
    fm.append("---")
    fm.append("")
    return "\n".join(fm)
