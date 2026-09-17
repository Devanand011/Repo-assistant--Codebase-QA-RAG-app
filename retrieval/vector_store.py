import chromadb
from sentence_transformers import SentenceTransformer

# Loads once, reused across calls — loading this every time would be slow.
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

chroma_client = chromadb.PersistentClient(path="chroma_db")


def get_collection(repo_name: str):
    """
    Each repo gets its own Chroma collection, so different repos'
    chunks never mix together during retrieval.
    """
    return chroma_client.get_or_create_collection(name=repo_name)


def embed_and_store(chunks: list[dict], repo_name: str):
    """
    Takes chunks from chunker.py, embeds each one's code,
    and stores them in a repo-specific Chroma collection.
    """
    collection = get_collection(repo_name)

    codes = [chunk["code"] for chunk in chunks]
    embeddings = embedding_model.encode(codes, show_progress_bar=True).tolist()

    ids = [f"{chunk['file']}::{chunk['name']}::{i}" for i, chunk in enumerate(chunks)]

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=codes,
        metadatas=[
            {
                "file": chunk["file"],
                "name": chunk["name"],
                "type": chunk["type"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
            }
            for chunk in chunks
        ],
    )

    return len(chunks)


if __name__ == "__main__":
    from ingestion.chunker import chunk_repo

    chunks = chunk_repo("cloned_repos/fastapi")
    count = embed_and_store(chunks, repo_name="fastapi")
    print(f"Stored {count} chunks in Chroma.")