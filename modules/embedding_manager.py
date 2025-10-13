from openai import AzureOpenAI
from config import *
import chromadb
import os
import tiktoken

chroma_client = chromadb.PersistentClient(path="./chroma_store/chroma_data")
collection = chroma_client.get_or_create_collection(name="confluence_notes")

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

# Initialize tokenizer for chunking
tokenizer = tiktoken.get_encoding("cl100k_base")

def chunk_text(text, max_tokens=6000, overlap=200):
    """
    Split text into chunks that fit within embedding model limits.
    
    Args:
        text: Full document text
        max_tokens: Maximum tokens per chunk (default 6000, safe for 8k limit)
        overlap: Token overlap between chunks for context continuity
    
    Returns:
        List of text chunks
    """
    tokens = tokenizer.encode(text)
    chunks = []
    
    start = 0
    while start < len(tokens):
        end = start + max_tokens
        chunk_tokens = tokens[start:end]
        chunk_text = tokenizer.decode(chunk_tokens)
        chunks.append(chunk_text)
        
        # Move start forward, accounting for overlap
        start = end - overlap
    
    return chunks

def generate_embedding(text):
    """Generate embedding for a single text chunk."""
    response = client.embeddings.create(
        input=text,
        model=EMBED_MODEL
    )
    return response.data[0].embedding

def store_in_chroma(doc_id, text, metadata):
    """
    Store document in ChromaDB with automatic chunking for long documents.
    
    Args:
        doc_id: Unique identifier for the document
        text: Full markdown text
        metadata: Document metadata (title, source, etc.)
    """
    # Check token count
    token_count = len(tokenizer.encode(text))
    
    if token_count > 6000:
        # Chunk the document
        chunks = chunk_text(text)
        print(f"  └─ Document '{doc_id}' split into {len(chunks)} chunks ({token_count} tokens)")
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            embedding = generate_embedding(chunk)
            
            # Add chunk index to metadata
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = i
            chunk_metadata["total_chunks"] = len(chunks)
            chunk_metadata["parent_doc"] = doc_id
            
            collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                metadatas=[chunk_metadata],
                documents=[chunk]
            )
    else:
        # Store as single document
        embedding = generate_embedding(text)
        collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            metadatas=[metadata],
            documents=[text]
        )

def get_all_documents():
    """
    Retrieve all unique document titles from ChromaDB.
    Returns set of parent document IDs (not chunk IDs).
    """
    all_data = collection.get()
    doc_ids = set()
    
    for metadata in all_data['metadatas']:
        # Check if this is a chunk or a full document
        if 'parent_doc' in metadata:
            doc_ids.add(metadata['parent_doc'])
        else:
            doc_ids.add(metadata['title'])
    
    return doc_ids
