import os
from dotenv import load_dotenv
from google import genai as google_genai
from retrieval.vector_store import get_collection, embedding_model

load_dotenv()
client = google_genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

#gemini_model = google_genai.GenerativeModel("gemini-1.5-flash")

CONFIDENCE_THRESHOLD = 0.1  # chunks less similar than this are treated as "not found"


def retrieve_relevant_chunks(question: str, repo_name: str, top_k: int = 5):
    collection = get_collection(repo_name)
    question_embedding = embedding_model.encode([question]).tolist()

    results = collection.query(
        query_embeddings=question_embedding,
        n_results=top_k,
    )

    chunks = []
    for i in range(len(results["documents"][0])):
        distance = results["distances"][0][i]
        similarity = 1 - distance  # Chroma returns distance; convert to similarity

        chunks.append({
            "code": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "similarity": similarity,
        })

    return chunks

import time

def generate_with_retry(prompt: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
            )
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            print(f"Request failed ({e}), retrying in {wait_time}s...")
            time.sleep(wait_time)

def answer_question(question: str, repo_name: str) -> dict:
    chunks = retrieve_relevant_chunks(question, repo_name)

    # If even the best match is weak, don't let the LLM guess.
    if not chunks or chunks[0]["similarity"] < CONFIDENCE_THRESHOLD:
        return {
            "answer": "I couldn't find anything in this codebase confidently related to your question. Try rephrasing, or it may not be covered in this repo.",
            "sources": [],
        }

    context = "\n\n".join(
        f"File: {c['metadata']['file']} (lines {c['metadata']['start_line']}-{c['metadata']['end_line']})\n{c['code']}"
        for c in chunks
    )

    prompt = f"""You are a codebase assistant. Answer the question using ONLY the code context below.
If the context doesn't fully answer the question, say so — don't guess or invent details.

CONTEXT:
{context}

QUESTION: {question}

ANSWER (cite file names when relevant):"""

    response = generate_with_retry(prompt)

    return {
        "answer": response.text,
        "sources": [
            {"file": c["metadata"]["file"], "lines": f"{c['metadata']['start_line']}-{c['metadata']['end_line']}"}
            for c in chunks
        ],
    }


if __name__ == "__main__":
    result = answer_question("How does FastAPI handle dependency injection?", repo_name="fastapi")
    print("ANSWER:\n", result["answer"])
    print("\nSOURCES:")
    for s in result["sources"]:
        print(f"  {s['file']} (lines {s['lines']})")