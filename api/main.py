from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ingestion.repo_cloner import clone_repo
from ingestion.chunker import chunk_repo
from retrieval.vector_store import embed_and_store
from retrieval.qa_engine import answer_question

app = FastAPI(title="Repo Assistant API")

# Allows your React frontend (running on a different port during dev) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your actual frontend URL once deployed
    allow_methods=["*"],
    allow_headers=["*"],
)


class IndexRequest(BaseModel):
    repo_url: str


class AskRequest(BaseModel):
    question: str
    repo_name: str


@app.post("/index")
def index_repo(request: IndexRequest):
    """
    Clones, chunks, and embeds a repo so it can be queried afterward.
    """
    try:
        local_path = clone_repo(request.repo_url)
        chunks = chunk_repo(local_path)

        if not chunks:
            raise HTTPException(status_code=400, detail="No Python files found to index in this repo.")

        repo_name = request.repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        count = embed_and_store(chunks, repo_name=repo_name)

        return {"repo_name": repo_name, "chunks_indexed": count}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


@app.post("/ask")
def ask_question(request: AskRequest):
    """
    Answers a question about an already-indexed repo.
    """
    try:
        result = answer_question(request.question, repo_name=request.repo_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Question answering failed: {str(e)}")