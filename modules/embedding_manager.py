from openai import AzureOpenAI
from config import *
import chromadb
from modules.utils.utils import strip_images, truncate_text

chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(name="confluence_notes_v3")

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)


def generate_embedding(text):
    """Generate embedding."""
    text_clean = strip_images(text)
    text_clean = truncate_text(text_clean, 7000)  # Safe limit for embeddings
    
    if not text_clean.strip():
        return None
    
    response = client.embeddings.create(
        input=text_clean,
        model=EMBED_MODEL
    )
    return response.data[0].embedding


def store_chunk(chunk, document_title, tags, breadcrumb=""):
    """Store chunk in ChromaDB."""
    text = chunk.get_text_without_images()
    
    if not text.strip():
        return
    
    embedding = generate_embedding(text)
    if not embedding:
        return
    
    metadata = {
        "title": chunk.heading,
        "document": document_title,
        "level": chunk.level,
        "chunk_id": chunk.chunk_id,
        "parent_id": chunk.parent_id or "",
        "tags": ",".join(tags),
        "breadcrumb": breadcrumb,
        "has_children": len(chunk.children) > 0
    }
    
    collection.add(
        ids=[chunk.chunk_id],
        embeddings=[embedding],
        metadatas=[metadata],
        documents=[text[:1000]]  # Store preview only
    )


def query_by_tags(tags, n_results=10):
    """Query by tags."""
    tag_filters = [{"tags": {"$contains": tag}} for tag in tags]
    
    if tag_filters:
        try:
            results = collection.get(
                where={"$or": tag_filters},
                limit=n_results
            )
            return results
        except:
            return None
    return None