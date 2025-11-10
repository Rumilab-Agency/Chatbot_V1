from fastapi import FastAPI, UploadFile, Form, Query
from pymongo import MongoClient
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams
from openai import OpenAI
import uuid
import os
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
QDRANT_HOST = os.getenv("QDRANT_HOST")
QDRANT_PORT = int(os.getenv("QDRANT_PORT") or 6333)
VECTOR_SIZE = int(os.getenv("VECTOR_SIZE") or 1536)

app = FastAPI()

# MongoDB setup
mongo_client = MongoClient(MONGO_URI)
kb_db = mongo_client["kb_db"]
documents_col = kb_db["documents"]
embeddings_col = kb_db["embeddings"]

# Qdrant setup
qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
qdrant.recreate_collection(
    collection_name="kb_vectors",
    vectors_config=VectorParams(
        size=VECTOR_SIZE,           # embedding dimension
        distance=Distance.COSINE
    )
)

# OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

def generate_embedding(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding  # new v1 API

@app.post("/documents")
async def add_document(title: str = Form(...), file: UploadFile = None, text: str = Form(None)):
    doc_id = str(uuid.uuid4())
    content = ""

    if file:
        content = (await file.read()).decode("utf-8", errors="ignore")
    elif text:
        content = text
    else:
        return {"error": "No content provided"}

    # Save document metadata
    documents_col.insert_one({
        "docId": doc_id,
        "title": title,
        "type": file.filename.split(".")[-1] if file else "text",
        "createdAt": None
    })

    # Split content into chunks
    chunks = [content[i:i+500] for i in range(0, len(content), 500)]

    points = []
    for chunk in chunks:
        embedding = generate_embedding(chunk)
        chunk_id = str(uuid.uuid4())  # unique UUID for each chunk
        embeddings_col.insert_one({
            "docId": doc_id,
            "chunkId": chunk_id,
            "text": chunk,
            "embedding": embedding
        })
        points.append(PointStruct(
            id=chunk_id,
            vector=embedding,
            payload={"docId": doc_id, "text": chunk}
        ))

    # Insert into Qdrant
    qdrant.upsert(collection_name="kb_vectors", points=points)

    return {"message": "Document ingested", "docId": doc_id}


TOP_K = 5  # number of relevant chunks to retrieve

@app.get("/query")
async def query_kb(message: str = Query(...)):
    # Generate embedding for user query
    query_embedding = generate_embedding(message)

    # Search in Qdrant
    search_result = qdrant.search(
        collection_name="kb_vectors",
        query_vector=query_embedding,
        limit=TOP_K
    )

    # Collect retrieved chunks
    retrieved_chunks = [hit.payload["text"] for hit in search_result]

    return {
        "query": message,
        "retrieved_chunks": retrieved_chunks
    }
