from fastapi import FastAPI, UploadFile, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams
from openai import OpenAI
from docx import Document
from bs4 import BeautifulSoup
import pdfplumber
import requests
import uuid
import os
from dotenv import load_dotenv

# Load env
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
QDRANT_HOST = os.getenv("QDRANT_HOST")
QDRANT_PORT = int(os.getenv("QDRANT_PORT") or 6333)
VECTOR_SIZE = int(os.getenv("VECTOR_SIZE") or 1536)

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database
mongo_client = MongoClient(MONGO_URI)
kb_db = mongo_client["kb_db"]
documents_col = kb_db["documents"]
embeddings_col = kb_db["embeddings"]

# Qdrant
qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
qdrant.recreate_collection(
    collection_name="kb_vectors",
    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
)

client = OpenAI(api_key=OPENAI_API_KEY)

# ----------------------------------------------------------
# Embedding Generator
# ----------------------------------------------------------
def generate_embedding(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


# ----------------------------------------------------------
# Parsing Functions
# ----------------------------------------------------------
def parse_pdf(file: UploadFile):
    text = ""
    with pdfplumber.open(file.file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text


def parse_docx(file: UploadFile):
    doc = Document(file.file)
    return "\n".join([p.text for p in doc.paragraphs])


def parse_url(url: str):
    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n")


# ----------------------------------------------------------
# Ingest Document (PDF, DOCX, TEXT)
# ----------------------------------------------------------
@app.post("/documents")
async def ingest_document(
    title: str = Form(...),
    file: UploadFile = None,
    text: str = Form(None)
):
    doc_id = str(uuid.uuid4())

    if file:
        ext = file.filename.split(".")[-1].lower()

        if ext == "pdf":
            content = parse_pdf(file)
        elif ext == "docx":
            content = parse_docx(file)
        else:
            content = (await file.read()).decode("utf-8", errors="ignore")
    else:
        if not text:
            return {"error": "No content provided"}
        content = text

    documents_col.insert_one({
        "docId": doc_id,
        "title": title,
        "type": "file" if file else "text"
    })

    chunks = [content[i:i+500] for i in range(0, len(content), 500)]
    points = []

    for ch in chunks:
        emb = generate_embedding(ch)
        chunk_id = str(uuid.uuid4())

        embeddings_col.insert_one({
            "docId": doc_id,
            "chunkId": chunk_id,
            "text": ch,
            "embedding": emb
        })

        points.append(PointStruct(
            id=chunk_id,
            vector=emb,
            payload={"docId": doc_id, "text": ch}
        ))

    qdrant.upsert(collection_name="kb_vectors", points=points)

    return {"message": "Document ingested", "docId": doc_id}


# ----------------------------------------------------------
# Ingest Website URL
# ----------------------------------------------------------
@app.post("/ingest-url")
async def ingest_url(url: str = Form(...)):
    content = parse_url(url)
    doc_id = str(uuid.uuid4())

    documents_col.insert_one({
        "docId": doc_id,
        "title": url,
        "type": "url"
    })

    chunks = [content[i:i+500] for i in range(0, len(content), 500)]
    points = []

    for ch in chunks:
        emb = generate_embedding(ch)
        chunk_id = str(uuid.uuid4())

        embeddings_col.insert_one({
            "docId": doc_id,
            "chunkId": chunk_id,
            "text": ch,
            "embedding": emb
        })

        points.append(PointStruct(
            id=chunk_id,
            vector=emb,
            payload={"docId": doc_id, "text": ch}
        ))

    qdrant.upsert(collection_name="kb_vectors", points=points)

    return {"message": "URL ingested", "docId": doc_id}


# ----------------------------------------------------------
# Query
# ----------------------------------------------------------
@app.get("/query")
async def query_kb(message: str = Query(...)):
    embedding = generate_embedding(message)

    search = qdrant.search(
        collection_name="kb_vectors",
        query_vector=embedding,
        limit=5
    )

    return {
        "query": message,
        "retrieved_chunks": [hit.payload["text"] for hit in search]
    }
