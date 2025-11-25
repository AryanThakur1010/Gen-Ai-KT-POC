from openai import AzureOpenAI
from config import *
import json
import re
from modules.utils.utils import strip_images, truncate_text

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)


def extract_tags(text, title, max_tags=TAG_COUNT):
    """Extract tags using AI."""
    # Use only first 2000 characters
    text_sample = strip_images(text)[:2000]
    
    prompt = f"""Extract {max_tags} relevant tags from this document.

Title: {title}
Content preview: {text_sample}

Return ONLY a JSON array: ["tag1", "tag2", ...]
Tags should be lowercase with hyphens."""

    try:
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": "Extract tags. Return only JSON array."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=100
        )
        
        result = response.choices[0].message.content.strip()
        result = re.sub(r'^```json\s*|\s*```$', '', result)
        tags = json.loads(result)
        
        return [re.sub(r'[^a-z0-9-\s]', '', tag.lower().strip()).replace(' ', '-') 
                for tag in tags[:max_tags] if tag]
        
    except Exception as e:
        print(f"    ⚠️  Tag extraction failed: {e}")
        # Fallback
        return [re.sub(r'[^a-z0-9-]', '', word.lower()) 
                for word in title.split()[:max_tags]]
