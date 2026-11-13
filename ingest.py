# ============================================================================
# ingest.py — Knowledge Base Ingestion Pipeline
# ============================================================================
# YEH FILE KYA KARTI HAI?
# -----------------------
# Jab admin brand guidelines, product info, ya legal documents upload karta hai,
# ye file unhe process karti hai:
#   1. Document padhho (PDF/TXT)
#   2. Chhote chunks mein todo (kyunki AI ek baar mein bahut bada text nahi padh sakta)
#   3. Har chunk ka embedding banao (text → numbers vector)
#   4. ChromaDB mein store karo (vector database)
#   5. SQLite mein metadata save karo (filename, type, version)
#
# CHUNKING KYA HAI?
# -----------------
# Ek 50-page document ko ek baar mein AI ko dena mushkil hai.
# Isliye hum use chhote "chunks" mein todte hain (like paragraphs).
# Jab query aaye, sirf relevant chunks dhundhe hain — poora document nahi.
#
# EMBEDDING KYA HAI? (Recap)
# --------------------------
# Text ko numbers ki list mein convert karna.
# "Our brand color is blue" → [0.23, -0.45, 0.67, ...]
# Similar meaning ke texts ke numbers bhi similar honge.
# Ye numbers ChromaDB mein store hote hain for fast similarity search.
#
# CHROMADB KYA HAI? (Recap)
# -------------------------
# Ek vector database — embeddings store karti hai aur similarity search karti hai.
# Regular DB: WHERE name = 'apple' (exact match)
# Vector DB: "red fruit" → finds "apple" (meaning match)
# ============================================================================

import os
import chromadb                          # Vector database
from chromadb.config import Settings     # ChromaDB settings
import db                               # Hamari db.py file (SQLite operations)

# ─── CHROMADB SETUP ─────────────────────────────────────────────────────────
# ChromaDB ko persistent mode mein initialize karo
# Persistent = data disk pe save hoga, program band hone pe bhi rahega

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_data")
# chroma_data/ folder mein vector database save hogi

chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
# PersistentClient → data file mein save hoga (vs InMemoryClient jo RAM mein hota)

# Collection banao ya existing lo — ye ek "table" jaisa hai vector DB mein
# Collection = embeddings ka group (jaise SQL mein table hota hai)
collection = chroma_client.get_or_create_collection(
    name="brand_guidelines",
    metadata={"description": "Brand guidelines, product facts, and legal rules"}
)
# get_or_create → agar already hai toh use karo, nahi toh naya banao


# ─── CHUNKING ───────────────────────────────────────────────────────────────

def chunk_text(text, chunk_size=500, overlap=50):
    """
    Bade text ko chhote chunks mein todo.
    
    PARAMETERS:
        text: str — poora document text
        chunk_size: int — har chunk mein max kitne characters (default 500)
        overlap: int — consecutive chunks mein kitne characters common honge (default 50)
    
    OVERLAP KYU?
    Soch ek sentence do chunks ke beech mein kat gaya:
        Chunk 1: "...our brand color is"
        Chunk 2: "blue and white..."
    Overlap se dono chunks mein poora sentence aayega:
        Chunk 1: "...our brand color is blue and"
        Chunk 2: "our brand color is blue and white..."
    
    RETURNS:
        list of strings — har ek chunk
    """
    if not text or not text.strip():
        return []
    
    # Pehle text ko paragraphs mein split karo
    paragraphs = text.split("\n\n")
    
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # Agar current chunk + new paragraph chunk_size se chhota hai, add karo
        if len(current_chunk) + len(para) + 1 <= chunk_size:
            current_chunk += ("\n" + para if current_chunk else para)
        else:
            # Current chunk save karo aur naya start karo
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            # Agar paragraph khud bahut bada hai, use bhi todo
            if len(para) > chunk_size:
                # Sentences mein split karo
                sentences = para.replace(". ", ".\n").split("\n")
                current_chunk = ""
                for sent in sentences:
                    if len(current_chunk) + len(sent) + 1 <= chunk_size:
                        current_chunk += (" " + sent if current_chunk else sent)
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sent
            else:
                current_chunk = para
    
    # Last chunk save karo
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    # Overlap add karo — har chunk ke end ke kuch characters next chunk ke start mein
    if overlap > 0 and len(chunks) > 1:
        overlapped_chunks = [chunks[0]]
        for i in range(1, len(chunks)):
            # Previous chunk ke last 'overlap' characters lo
            prev_tail = chunks[i - 1][-overlap:] if len(chunks[i - 1]) > overlap else ""
            overlapped_chunks.append(prev_tail + " " + chunks[i])
        chunks = overlapped_chunks
    
    return chunks

def read_pdf_file(filepath):
    """
    PDF file padhho aur text nikalo.
    Pehle pypdf (jo requirements.txt mein hai) use karega, 
    aur fallback ke liye PyPDF2 check karega.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            print("⚠️ Neither pypdf nor PyPDF2 is installed. PDF reading disabled.")
            return ""

    try:
        text = ""
        with open(filepath, "rb") as f:
            reader = PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
        return text
    except Exception as e:
        print(f"⚠️ Error reading PDF {filepath}: {e}")
        return ""

def read_text_file(filepath):
    """
    Text file padhho (.txt format).
    
    encoding='utf-8' → Hindi/special characters bhi sahi se padh sake
    errors='ignore' → agar koi character nahi padh paya toh skip karo (crash nahi hoga)
    """
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def read_pdf_file(filepath):
    """
    PDF file padhho aur text nikalo.
    
    PyPDF2 library use karti hai — PDF ke har page se text extract karti hai.
    """
    try:
        from pypdf import PdfReader  # pypdf is the modern successor to PyPDF2
        text = ""
        with open(filepath, "rb") as f:     # "rb" = read binary (PDF binary format mein hota)
            reader = PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
        return text
    except ImportError:
        # Agar pypdf installed nahi hai
        print("⚠️ pypdf not installed. PDF reading disabled.")
        return ""


# ─── MAIN INGESTION FUNCTION ────────────────────────────────────────────────

def ingest_document(filepath, doc_type="guideline"):
    """
    MAIN FUNCTION — Document ko process karke knowledge base mein daalo.
    
    STEPS:
        1. File padhho (text ya PDF)
        2. Text ko chunks mein todo
        3. ChromaDB mein store karo (embeddings automatic ban jayenge)
        4. SQLite mein metadata save karo
    
    PARAMETERS:
        filepath: str — file ka full path
        doc_type: str — 'guideline', 'factsheet', 'legal', 'template'
    
    RETURNS:
        dict — result with doc_id, chunk_count, status
    """
    filename = os.path.basename(filepath)
    # os.path.basename → full path se sirf filename nikalo
    # "C:/docs/brand.pdf" → "brand.pdf"
    
    print(f"📥 Ingesting: {filename} (type: {doc_type})")
    
    # Step 1: File padhho
    # ───────────────────
    if filepath.lower().endswith(".pdf"):
        text = read_pdf_file(filepath)
    else:
        text = read_text_file(filepath)
    
    if not text.strip():
        return {"status": "error", "message": "File is empty or could not be read"}
    
    print(f"   📄 Text extracted: {len(text)} characters")
    
    # Step 2: Chunks mein todo
    # ────────────────────────
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    print(f"   🔪 Split into {len(chunks)} chunks")
    
    if not chunks:
        return {"status": "error", "message": "No chunks created from document"}
    
    # Step 3: ChromaDB mein store karo
    # ─────────────────────────────────
    # ChromaDB ko har chunk ke liye chahiye:
    #   - documents: actual text chunks
    #   - ids: unique identifier for each chunk
    #   - metadatas: extra info (filename, type, chunk number)
    
    # Unique IDs banao har chunk ke liye
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # strftime → datetime ko string mein format karo
    # %Y = year (2026), %m = month (11), %d = day (04)
    
    ids = [f"{filename}_{timestamp}_chunk_{i}" for i in range(len(chunks))]
    # List comprehension — ek line mein list banao
    # Result: ["brand.pdf_20261104_200415_chunk_0", "brand.pdf_20261104_200415_chunk_1", ...]
    
    metadatas = [
        {
            "filename": filename,
            "doc_type": doc_type,
            "chunk_index": i,
            "total_chunks": len(chunks),
        }
        for i in range(len(chunks))
    ]
    # Har chunk ke saath metadata store hoga (kaunsi file se aaya, chunk number, etc.)
    
    # ChromaDB mein add karo
    # ChromaDB automatically embeddings banayega (default: all-MiniLM-L6-v2 model)
    collection.add(
        documents=chunks,
        ids=ids,
        metadatas=metadatas,
    )
    print(f"   💾 Stored {len(chunks)} chunks in ChromaDB")
    
    # Step 4: SQLite mein metadata save karo
    # ──────────────────────────────────────
    content_preview = text[:500]  # Pehle 500 characters preview ke liye
    doc_id = db.add_document(filename, doc_type, content_preview, len(chunks))
    print(f"   📝 Document record saved (ID: {doc_id})")
    
    print(f"✅ Successfully ingested: {filename}")
    
    return {
        "status": "success",
        "doc_id": doc_id,
        "filename": filename,
        "chunk_count": len(chunks),
        "char_count": len(text),
    }


def ingest_text_directly(text, title, doc_type="guideline"):
    """
    Direct text ko ingest karo (bina file ke).
    Ye tab useful hai jab user UI mein directly text paste kare.
    
    PARAMETERS:
        text: str — guidelines/rules text
        title: str — document ka title/name
        doc_type: str — document type
    """
    if not text.strip():
        return {"status": "error", "message": "Text is empty"}
    
    print(f"📥 Ingesting text: {title} (type: {doc_type})")
    
    # Chunks mein todo
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    print(f"   🔪 Split into {len(chunks)} chunks")
    
    if not chunks:
        return {"status": "error", "message": "No chunks created"}
    
    # ChromaDB mein store karo
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ids = [f"{title}_{timestamp}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {"filename": title, "doc_type": doc_type, "chunk_index": i, 
         "total_chunks": len(chunks)}
        for i in range(len(chunks))
    ]
    
    collection.add(documents=chunks, ids=ids, metadatas=metadatas)
    print(f"   💾 Stored {len(chunks)} chunks in ChromaDB")
    
    # SQLite mein save karo
    doc_id = db.add_document(title, doc_type, text[:500], len(chunks))
    print(f"✅ Successfully ingested: {title}")
    
    return {
        "status": "success",
        "doc_id": doc_id,
        "filename": title,
        "chunk_count": len(chunks),
    }


def get_collection_stats():
    """ChromaDB collection ki stats nikalo — kitne documents/chunks hain."""
    count = collection.count()
    return {
        "total_chunks": count,
        "collection_name": "brand_guidelines",
    }


def delete_chunks_by_filename(filename):
    """
    ChromaDB se ek specific document ke saare chunks delete karo.
    'filename' metadata field se match karke delete karta hai.
    """
    try:
        # ChromaDB where clause: filename field match karo
        results = collection.get(where={"filename": filename})
        ids_to_delete = results.get("ids", [])
        if ids_to_delete:
            collection.delete(ids=ids_to_delete)
            print(f"🗑️ Deleted {len(ids_to_delete)} chunks for '{filename}' from ChromaDB")
            return len(ids_to_delete)
        else:
            print(f"ℹ️ No ChromaDB chunks found for filename '{filename}'")
            return 0
    except Exception as e:
        print(f"⚠️ Could not delete chunks for '{filename}': {e}")
        return 0


def clear_collection():
    """
    Poora knowledge base clear karo (⚠️ DANGER — sab data delete ho jayega).
    Ye sirf development/testing ke liye hai.
    """
    # Purani collection delete karo aur nayi banao
    global collection
    chroma_client.delete_collection("brand_guidelines")
    collection = chroma_client.get_or_create_collection(
        name="brand_guidelines",
        metadata={"description": "Brand guidelines, product facts, and legal rules"}
    )
    print("🗑️ Knowledge base cleared!")
