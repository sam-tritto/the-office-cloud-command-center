import os
import json
from google import genai

DOCS_DIR = "data/documents"
INDEX_PATH = "data/vector_index.json"
CHUNK_SIZE = 800 # characters roughly ~150 words

def build_index():
    if not os.environ.get("GEMINI_API_KEY"):
        print("Skipping RAG index build: GEMINI_API_KEY is not set.")
        return
    
    if not os.path.exists(DOCS_DIR):
        print(f"Directory {DOCS_DIR} does not exist.")
        return
        
    client = genai.Client()
    index_data = []
    
    chunk_id_counter = 0
    for filename in os.listdir(DOCS_DIR):
        if not filename.endswith(".txt"):
            continue
            
        filepath = os.path.join(DOCS_DIR, filename)
        with open(filepath, "r") as f:
            content = f.read()
            
        # simple overlap split
        chunks = []
        i = 0
        while i < len(content):
            chunk = content[i:i+CHUNK_SIZE]
            if not chunk.strip():
                break
            chunks.append(chunk)
            i += CHUNK_SIZE - 200 # overlap
            
        for chunk in chunks:
            response = client.models.embed_content(
                model="text-embedding-004",
                contents=chunk
            )
            embedding = response.embeddings[0].values
            
            index_data.append({
                "chunk_id": chunk_id_counter,
                "file_name": filename,
                "text": chunk,
                "embedding": embedding
            })
            chunk_id_counter += 1
            
    with open(INDEX_PATH, "w") as f:
        json.dump(index_data, f)
        
    print(f"Successfully built RAG vector index with {len(index_data)} chunks.")

if __name__ == "__main__":
    build_index()
