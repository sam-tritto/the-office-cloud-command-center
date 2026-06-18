import os
import json
import math
from collections import Counter
import re

try:
    from google import genai
except ImportError:
    genai = None

INDEX_PATH = "data/vector_index.json"
DOCS_DIR = "data/documents"

def generate_query_embedding(text: str) -> list[float]:
    if not genai or not os.environ.get("GEMINI_API_KEY"):
        raise ValueError("GEMINI_API_KEY is not set or google-genai is not installed.")
    
    client = genai.Client()
    response = client.models.embed_content(
        model="text-embedding-004",
        contents=text
    )
    return response.embeddings[0].values

def cosine_similarity(u: list[float], v: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(u, v))
    norm_u = math.sqrt(sum(a * a for a in u))
    norm_v = math.sqrt(sum(b * b for b in v))
    if norm_u == 0 or norm_v == 0:
        return 0.0
    return dot_product / (norm_u * norm_v)

def keyword_overlap_similarity(query: str, text: str) -> float:
    # simple TF-like word matching
    def get_words(s):
        return re.findall(r'\w+', s.lower())
    
    query_words = get_words(query)
    if not query_words:
        return 0.0
    
    text_words = set(get_words(text))
    overlap = sum(1 for w in query_words if w in text_words)
    return overlap / len(query_words)

def search_docs(query: str, top_k: int = 3) -> list[dict]:
    # Check if we can use embeddings
    use_embeddings = bool(genai and os.environ.get("GEMINI_API_KEY") and os.path.exists(INDEX_PATH))
    
    if use_embeddings:
        try:
            with open(INDEX_PATH, "r") as f:
                index = json.load(f)
            
            query_emb = generate_query_embedding(query)
            
            results = []
            for item in index:
                score = cosine_similarity(query_emb, item["embedding"])
                results.append({
                    "file_name": item["file_name"],
                    "text": item["text"],
                    "score": score
                })
            
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]
            
        except Exception as e:
            print(f"Error using vector index: {e}. Falling back to keyword search.")
    
    # Fallback: keyword search
    results = []
    if os.path.exists(DOCS_DIR):
        for filename in os.listdir(DOCS_DIR):
            if filename.endswith(".txt"):
                filepath = os.path.join(DOCS_DIR, filename)
                with open(filepath, "r") as f:
                    content = f.read()
                
                # Split content into smaller chunks roughly comparable to embeddings chunk size
                chunks = [content[i:i+800] for i in range(0, len(content), 800)]
                
                for chunk in chunks:
                    score = keyword_overlap_similarity(query, chunk)
                    if score > 0:
                        results.append({
                            "file_name": filename,
                            "text": chunk,
                            "score": score
                        })
    
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]
