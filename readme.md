# Obsidian Knowledge Base Generator

Transform Word documents into an interconnected Obsidian knowledge base with semantic bidirectional linking using AI embeddings.

## Overview

This project automates the conversion of Word documents (.docx) into a structured Obsidian vault with:
- **Clean Markdown formatting** using LYT (Linking Your Thinking) principles
- **Embedded images** preserved in their original positions as base64 data URLs
- **Semantic backlinks** generated using AI embeddings (finds related content automatically)
- **Bidirectional linking** (if Doc A links to Doc B, Doc B automatically links back to Doc A)
- **Vector search** powered by ChromaDB for intelligent content discovery

---

## Features

### 1. **Intelligent Document Processing**
- Extracts text and images from Word documents
- Preserves document structure and formatting
- Embeds images directly in markdown (no external files needed)

### 2. **AI-Powered Content Organization**
- Uses Azure OpenAI GPT-4 to restructure content into atomic notes
- Applies LYT framework for better knowledge management
- Maintains semantic relationships between concepts

### 3. **Semantic Linking**
- Generates embeddings for all documents using Azure OpenAI
- Finds semantically similar content automatically
- Creates backlinks based on content similarity (not just keywords)

### 4. **Bidirectional Relationships**
- When Document A links to Document B, Document B automatically links back
- Creates a true knowledge graph structure
- Enables better knowledge discovery in Obsidian

### 5. **Efficient Storage**
- ChromaDB vector database for fast similarity search
- Automatic chunking for large documents
- Persistent storage across runs

---

## Architecture

```
┌─────────────────┐
│  Word Documents │
│    (.docx)      │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  STEP 1: Extraction & Conversion            │
│  ├─ docx_extractor.py                       │
│  │  └─ Extract text & images (inline)       │
│  │                                          │
│  ├─ obsidian_generator.py                   │
│  │  └─ GPT-4 converts to LYT markdown       │
│  │                                          │
│  └─ embedding_manager.py                    │
│     └─ Generate embeddings & store chunks   │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  ChromaDB Vector Database                   │
│  ├─ Document embeddings                     │
│  ├─ Metadata (title, source, chunk info)    │
│  └─ Enables semantic search                 │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  STEP 2: Semantic Link Generation           │
│  backlinker.py                              │
│  ├─ Find similar documents (cosine sim)     │
│  ├─ Generate backlinks                      │
│  └─ Create bidirectional relationships      │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│ Obsidian Vault  │
│   (.md files)   │
│ with backlinks  │
└─────────────────┘
```

---

## Prerequisites

### Required Software
- **Python 3.8+**
- **Azure OpenAI Account** (with API access)
- **Obsidian** (for viewing the knowledge base)

### Required Python Packages
```
python-docx
openai
chromadb
tiktoken
tqdm
python-dotenv (optional, for .env file)
```

---

## Installation

### 1. Clone or Download the Project

```bash
git clone <repository-url>
cd Obsidian-Genai-Poc
```

### 2. Create Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install python-docx openai chromadb tiktoken tqdm python-dotenv
```

### 4. Set Up Project Structure

The project will automatically create necessary folders, but you can set them up manually:

```bash
mkdir -p data/input_docs
mkdir -p output/markdown
mkdir -p chroma_store
```

---

## Configuration

### 1. Create `config.py`

Create a file named `config.py` in the project root:

```python
# config.py

import os
from dotenv import load_dotenv

load_dotenv()

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("API_VERSION")
CHAT_MODEL = os.getenv("AZURE_OPENAI_DEPLOYMENT")
EMBED_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

```
Before pushing code- delete all word docs from data/input_docs folder.                                                         

### 2. Get Azure OpenAI Credentials

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your Azure OpenAI resource
3. Go to **Keys and Endpoint**
4. Copy:
   - **Key** → `AZURE_OPENAI_API_KEY`
   - **Endpoint** → `AZURE_OPENAI_ENDPOINT`
5. Go to **Model deployments** and note:
   - Your GPT-4 deployment name → `CHAT_MODEL`
   - Your embedding model deployment name → `EMBED_MODEL`

### 3. Alternative: Use `.env` File (Optional)

Create a `.env` file:

```env
AZURE_OPENAI_ENDPOINT=https://<your-resource-name>.openai.azure.com/
AZURE_OPENAI_KEY=<your-api-key>
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT= text-embedding-ada-002
```


---

## Usage

### 1. Add Word Documents

Place your `.docx` files in the `data/input_docs/` folder:

```
data/
└── input_docs/
    ├── document1.docx
    ├── document2.docx
    └── document3.docx
```

### 2. Run the Pipeline

```bash
python main.py
```

### 3. What Happens During Execution

```
 Step 1: Converting Word files and storing embeddings...
  Processing: document1
    ✓ Embedded image 1 (15234 bytes)
    ✓ Embedded image 2 (28901 bytes)
    ✓ Extracted 5000 characters, 2 images (embedded)
    ✓ Converted to markdown (45678 characters)
    ✓ Saved to output/markdown/document1.md
    ✓ Stored embeddings

 Step 1 complete: All Markdown files created and embedded.

 Step 2: Generating semantic backlinks...
  [Progress bar for linking documents]

 Step 3: Creating bidirectional links...
  [Progress bar for bidirectional updates]

 All documents processed with semantic bidirectional linking!

 Summary:
   - Documents processed: 3
   - Bidirectional link pairs created: 12
```

### 4. Open in Obsidian

1. Open Obsidian
2. Click **"Open another vault"** → **"Open folder as vault"**
3. Select the `output/markdown` folder
4. Your knowledge base is ready!

### 5. View Your Notes

- Click any note to open it
- Press `Ctrl+E` to toggle between Edit and Reading mode
- Click on `[[Links]]` to navigate between related notes
- Explore the graph view: `Ctrl+G`

---
