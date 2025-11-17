import os
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from openai import OpenAI
from pymongo import MongoClient
from dotenv import load_dotenv
from uuid import uuid4

load_dotenv()

# ---------- ENV VARIABLES ----------
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_COLLECTION = "documents"

MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongo:27017")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ---------- CLIENTS ----------
qdrant = QdrantClient(url=QDRANT_URL)

mongo = MongoClient(MONGO_URL)
db = mongo["rag_db"]
docs_collection = db["documents"]

openai = OpenAI(api_key=OPENAI_API_KEY)

# ---------- CREATE COLLECTION IF NOT EXISTS ----------
def setup_collection():
    existing = [c.name for c in qdrant.get_collections().collections]
    if QDRANT_COLLECTION not in existing:
        qdrant.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
        )
setup_collection()

# ---------- EMBEDDING HELPER ----------
def embed(text: str):
    res = openai.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return res.data[0].embedding

# ---------- INGEST PDF ----------
def ingest_pdf(filepath: str):
    from PyPDF2 import PdfReader

    reader = PdfReader(filepath)

    for page in reader.pages:
        text = page.extract_text()
        if not text:
            continue

        vector = embed(text)
        doc_id = str(uuid4())

        qdrant.upsert(
            collection_name=QDRANT_COLLECTION,
            points=[
                PointStruct(
                    id=doc_id,
                    vector=vector,
                    payload={"text": text}
                )
            ]
        )

        docs_collection.insert_one({
            "_id": doc_id,
            "text": text
        })

# ---------- PROCESS A USER QUERY ----------
def process_query(query: str):
    query_emb = embed(query)

    results = qdrant.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=query_emb,
        limit=3
    )

    context_chunks = [r.payload["text"] for r in results]

    full_context = "\n\n".join(context_chunks)

    chat = openai.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Use the provided context for answers."},
            {"role": "user", "content": f"Context:\n{full_context}\n\nQuestion: {query}"}
        ]
    )

    return chat.choices[0].message["content"]
