# Confluence to Obsidian Knowledge Base Converter

A Python-based pipeline that transforms Confluence Word exports into a structured, interconnected Obsidian knowledge base with intelligent semantic linking and hierarchical organization.

## What This Does

This tool processes exported Confluence pages (in .docx format) and generates clean, well-structured Markdown files optimized for Obsidian. Instead of just converting documents one-by-one, it creates an intelligent knowledge graph where related content is automatically linked based on:

- Document structure and hierarchy
- Semantic similarity using AI embeddings
- Shared topics and tags
- Content relationships

The result is a fully navigable Obsidian vault where you can discover connections between documents that weren't explicitly linked in Confluence.

## Key Features

**Adaptive Hierarchical Chunking**  
Documents are intelligently split based on heading structure (H1, H2, H3...) rather than arbitrary token limits. This preserves logical content boundaries and creates atomic, reusable knowledge chunks.

**3-Tier Intelligent Linking**
1. Structural links (parent-child, siblings) - instant
2. Tag-filtered semantic search - searches within related categories first
3. Full semantic search - discovers deep connections across all content

**AI-Powered Organization**  
Uses Azure OpenAI GPT-4 to:
- Convert content to clean, LYT-style Markdown
- Generate relevant tags automatically
- Suggest internal links between related concepts
- Maintain context while processing large documents

**Token-Safe Processing**  
Handles documents of any size without hitting API limits through smart chunking, image handling, and context management.

**Embedded Images**  
Images from Word documents are preserved inline as base64 data URLs - no separate image folder needed.

**Vector Search Backend**  
ChromaDB stores embeddings of all content, enabling fast semantic similarity queries for link generation.

## Architecture

The system processes documents in three phases:

```
PHASE 1: EXTRACTION & CHUNKING
┌─────────────┐
│ Word Docs   │
│ (.docx)     │
└──────┬──────┘
       │
       ├─► Extract Structure (headings, paragraphs, images, tables)
       │
       ├─► Adaptive Chunking
       │   • Try H1 sections first
       │   • Split by H2, H3... if too large
       │   • Fallback to paragraph groups
       │
       └─► Extract Tags (AI-powered, 5 per document)

PHASE 2: MARKDOWN GENERATION & EMBEDDING
       │
       ├─► Convert chunks to Markdown (with context from ±2 levels)
       │
       ├─► Generate embeddings for each chunk
       │
       └─► Store in ChromaDB (metadata: tags, hierarchy, breadcrumbs)

PHASE 3: INTELLIGENT LINKING
       │
       ├─► Tier 1: Deterministic links (structure-based)
       │
       ├─► Tier 2: Tag-filtered semantic links
       │
       ├─► Tier 3: Full semantic search (if needed)
       │
       └─► Append backlinks to markdown files

OUTPUT: Obsidian Vault
┌─────────────┐
│ .md files   │
│ + backlinks │
└─────────────┘
```

## Prerequisites

### Software Requirements

- **Python 3.8 or higher**
- **Azure OpenAI API access** with deployed models:
  - GPT-4 (or GPT-4o) for text generation
  - text-embedding-ada-002 for embeddings
- **Obsidian** (free) to view the generated knowledge base

### Python Dependencies

```
python-docx
openai==2.3.0
chromadb==1.1.1
tiktoken
tqdm
python-dotenv
```

These will be installed automatically via `requirements.txt`.

## Installation & Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd confluence-obsidian-converter
```

### 2. Create Virtual Environment

It's recommended to use a virtual environment to avoid dependency conflicts.

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt after activation.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs all required packages listed in `requirements.txt`.

### 4. Configure Azure OpenAI Credentials

Create a `.env` file in the project root directory:

```bash
# .env
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002
API_VERSION=2024-12-01-preview
```

**Where to find these values:**

1. Log in to [Azure Portal](https://portal.azure.com)
2. Navigate to your Azure OpenAI resource
3. Go to **Keys and Endpoint**:
   - Copy **KEY 1** → `AZURE_OPENAI_API_KEY`
   - Copy **Endpoint** → `AZURE_OPENAI_ENDPOINT`
4. Go to **Model deployments**:
   - Note your GPT-4 deployment name → `AZURE_OPENAI_DEPLOYMENT`
   - Note your embedding deployment name → `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`

**Security Note:** Never commit `.env` to version control. It's already in `.gitignore`.


## Usage

### Step 1: Export Confluence Pages

1. Navigate to the Confluence page you want to convert
2. Click the **three dots (⋯)** in the upper right
3. Select **Export → Export to Word**
4. This downloads a `.doc` file
5. Open the file in Microsoft Word
6. **Save As** → choose `.docx` format

Repeat for all pages you want to process.

### Step 2: Add Documents to Input Folder

Place all `.docx` files in `data/input_docs/`:

```
data/input_docs/
├── Getting Started Guide.docx
├── API Documentation.docx
├── User Manual.docx
└── System Architecture.docx
```

### Step 3: Run the Pipeline

```bash
python main.py
```

## Configuration Options

You can adjust processing behavior in `config.py`:

```python
# Context depth for AI processing (±N levels in document tree)
MAX_CONTEXT_LEVELS = 2

# Number of AI-generated tags per document
TAG_COUNT = 5

# Similarity threshold for semantic linking (0.0-1.0, lower = more similar)
SIMILARITY_THRESHOLD = 0.25

# Maximum tokens per chunk (keeps chunks manageable)
MAX_CHUNK_CONTENT_TOKENS = 2000

# Maximum tokens in total prompt (prevents API errors)
MAX_TOTAL_PROMPT_TOKENS = 100000

# Maximum number of heading suggestions for internal links
MAX_AVAILABLE_HEADINGS = 15
```

Lower `MAX_CONTEXT_LEVELS` = faster processing, less context  
Higher `SIMILARITY_THRESHOLD` = fewer but more precise links  
Lower `MAX_CHUNK_CONTENT_TOKENS` = more chunks, smaller file sizes

## Output Structure

Each processed document becomes a single Markdown file:

```markdown
---
title: "Getting Started Guide"
tags: [getting-started, setup, tutorial, onboarding, guide]
chunk_id: "abc123def456"
---

## Welcome

This guide will help you get started with...

## Installation

To install the system, follow these steps...

### System Requirements

You'll need the following...

## Configuration

After installation, configure...

---

**Related Notes:**
- [[System Architecture]]
- [[API Documentation]]
- [[User Manual]]
- [[Troubleshooting Guide]]
```
## Module Overview

### Core Processing Modules

**`docx_extractor.py`**
- `extract_structured_content()` - Parses Word documents and extracts headings, paragraphs, tables, and images while preserving document hierarchy
- `extract_heading_level()` - Identifies heading levels (H1-H6) from Word paragraph styles
- Returns structured content objects with type information (heading/paragraph/image/table)

**`hierarchical_chunker.py`**
- `AdaptiveHierarchicalChunker.create_chunks()` - Splits documents by heading structure with fallback strategy (H1→H2→H3→paragraphs)
- `DocumentChunk` class - Represents a content chunk with metadata (heading, level, parent/child relationships)
- `_split_large_chunks()` - Recursively splits oversized sections to stay under token limits
- Builds parent-child-sibling relationships automatically

**`tree_manager.py`**
- `TreeManager.get_minimal_context()` - Provides contextual information for a chunk (parent, siblings, children, breadcrumb)
- `get_all_headings()` - Returns list of all document headings for link suggestion
- Manages document hierarchy and provides ±N level context windows

**`tag_extractor.py`**
- `extract_tags()` - Uses GPT-4 to analyze document content and generate 5 relevant tags
- Returns normalized tags (lowercase, hyphenated, alphanumeric only)
- Fallback to title-based tags if AI extraction fails

**`obsidian_generator.py`**
- `generate_markdown_safe()` - Converts document chunks to Obsidian-compatible markdown with strict token limits
- `create_frontmatter()` - Generates YAML frontmatter with title, tags, and metadata
- `generate_fallback_markdown()` - Basic markdown conversion without AI (used when token limits approached)
- Strips images during AI processing, re-adds them after conversion

**`embedding_manager.py`**
- `generate_embedding()` - Creates vector embeddings using Azure OpenAI text-embedding-ada-002
- `store_chunk()` - Saves chunk text, embeddings, and metadata to ChromaDB
- `query_by_tags()` - Retrieves chunks matching specific tags for filtered semantic search
- Manages persistent ChromaDB vector database

**`hybrid_linker.py`**
- `HybridLinker.find_links()` - Three-tier strategy to find related documents:
  - Tier 1: Deterministic (parent/child/sibling, exact heading matches)
  - Tier 2: Tag-filtered semantic search (searches within matching tags)
  - Tier 3: Full semantic search (discovers unexpected connections)
- `generate_backlinks_section()` - Formats related notes as Obsidian [[wiki-links]]
- Returns ranked list of most relevant document connections

**`utils.py`**
- `count_tokens()` - Counts tokens using tiktoken (cl100k_base encoding)
- `truncate_text()` - Safely truncates text to maximum token count
- `strip_images()` - Removes base64 image data from text for token efficiency
- `get_text_preview()` - Creates short preview of content (first N characters)

**`main.py`**
- Orchestrates three-phase pipeline:
  - Phase 1: Extract structure and create adaptive chunks
  - Phase 2: Generate markdown and store embeddings
  - Phase 3: Create intelligent links and append backlinks
- Progress tracking with tqdm and detailed logging
- Error handling and recovery for each document

## Performance 

**Processing Speed** (approximate):
- 10-20 documents: 5-10 minutes
- 50 documents: 20-30 minutes
- 100+ documents: 45-60 minutes


## Troubleshooting

**"Module not found" errors**
```bash
# Make sure virtual environment is activated
# You should see (venv) in your prompt
pip install -r requirements.txt
```

**"API key not found" or authentication errors**
- Check that `.env` exists and has correct values
- Verify API key is active in Azure Portal
- Ensure endpoint URL is correct (includes `https://`)

**"Token limit exceeded" errors**
- This should not happen with the current implementation
- If it does, reduce `MAX_CHUNK_CONTENT_TOKENS` in `config.py`
- Try setting `MAX_CONTEXT_LEVELS = 1`

**ChromaDB errors**
```bash
# Delete the database and regenerate
rm -rf chroma_store/chroma_data
python main.py
```

**Empty or malformed markdown files**
- Check that input `.docx` files have proper heading styles
- Verify files aren't password-protected
- Try opening and re-saving the Word file

## Known Limitations

- **External references**: Links to Confluence pages not in your document set won't be automatically created
- **Backlink placement**: Related notes section appears at the end of each document rather than after each section
- **Image size limits**: Images larger than 300KB are skipped to prevent token issues
- **Table formatting**: Complex tables are converted to simple text - advanced formatting may be lost
- **Content preservation**: AI may occasionally condense very detailed sections - review critical content

## Project Structure

```
├── config.py                  # Configuration and credentials
├── main.py                    # Main pipeline orchestrator
├── utils.py                   # Helper functions (token counting, text processing)
├── docx_extractor.py         # Extracts structure from Word docs
├── hierarchical_chunker.py   # Adaptive heading-based chunking
├── tree_manager.py           # Manages document hierarchy and context
├── tag_extractor.py          # AI-powered tag generation
├── obsidian_generator.py     # Converts chunks to Obsidian markdown
├── embedding_manager.py      # Vector storage and retrieval
└── hybrid_linker.py          # 3-tier intelligent linking system
```

## Contributing

Before committing code:
1. Remove all Word documents from `data/input_docs/`
2. Delete `chroma_store/chroma_data/` (vector DB)
3. Clear `output/markdown/` (generated files)
4. Never commit `.env` (already in `.gitignore`)
