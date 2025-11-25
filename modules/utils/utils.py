import re
import tiktoken

tokenizer = tiktoken.get_encoding("cl100k_base")


def count_tokens(text):
    """Count tokens in text."""
    if not text:
        return 0
    return len(tokenizer.encode(str(text)))


def truncate_text(text, max_tokens):
    """Truncate text to max tokens."""
    if not text:
        return ""
    tokens = tokenizer.encode(str(text))
    if len(tokens) <= max_tokens:
        return text
    return tokenizer.decode(tokens[:max_tokens]) + "..."


def strip_images(text):
    """Remove base64 embedded images from text."""
    if not text:
        return ""
    pattern = r'!\[.*?\]\(data:image/[^)]+\)'
    return re.sub(pattern, '[IMAGE_PLACEHOLDER]', text)


def extract_images(text):
    """Extract image markdown from text."""
    if not text:
        return []
    pattern = r'!\[.*?\]\(data:image/[^)]+\)'
    return re.findall(pattern, text)


def get_text_preview(text, max_length=200):
    """Get preview of text (first N characters)."""
    if not text:
        return ""
    text = strip_images(text)
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."