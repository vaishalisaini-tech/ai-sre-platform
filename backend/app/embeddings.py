# app/embeddings.py
import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

# New recommended model. output_dimensionality=768 keeps our vectors
# the same size as our VECTOR(768) table column.
embedding_model = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    output_dimensionality=768,
)

def embed_text(text_to_embed: str) -> list[float]:
    """Turn a single piece of text into a 768-number vector."""
    return embedding_model.embed_query(text_to_embed)

