from typing import TypedDict, List
from langgraph.graph import StateGraph, END

from retrieval.qa_engine import retrieve_relevant_chunks, generate_with_retry


class AgentState(TypedDict):
    question: str
    repo_name: str
    initial_chunks: List[dict]
    followup_query: str
    followup_chunks: List[dict]
    final_answer: str
    sources: List[dict]


def retrieve_initial_node(state: AgentState) -> AgentState:
    state["initial_chunks"] = retrieve_relevant_chunks(state["question"], state["repo_name"])
    return state


def decide_followup_node(state: AgentState) -> AgentState:
    chunks = state["initial_chunks"]
    context = "\n\n".join(f"File: {c['metadata']['file']}\n{c['code'][:500]}" for c in chunks[:3])

    prompt = f"""You are helping answer a question about a codebase.
Given the question and the code retrieved so far, suggest ONE short, specific
search query (a function name, class name, or related concept) that would
help find additional useful context — something referenced but not fully
shown in what's retrieved so far.

If the retrieved context already seems sufficient on its own, respond with
exactly: NONE

QUESTION: {state['question']}

RETRIEVED CONTEXT:
{context}

FOLLOW-UP SEARCH QUERY (or NONE):"""

    response = generate_with_retry(prompt)
    state["followup_query"] = response.text.strip()
    return state


def retrieve_followup_node(state: AgentState) -> AgentState:
    followup = state["followup_query"]
    if followup and followup.upper() != "NONE":
        state["followup_chunks"] = retrieve_relevant_chunks(followup, state["repo_name"])
    else:
        state["followup_chunks"] = []
    return state


def synthesize_node(state: AgentState) -> AgentState:
    all_chunks = state["initial_chunks"] + state["followup_chunks"]

    # De-duplicate — the follow-up search can re-surface a chunk we already have.
    seen = set()
    unique_chunks = []
    for c in all_chunks:
        key = (c["metadata"]["file"], c["metadata"].get("start_line"))
        if key not in seen:
            seen.add(key)
            unique_chunks.append(c)

    context = "\n\n".join(
        f"File: {c['metadata']['file']} (lines {c['metadata']['start_line']}-{c['metadata']['end_line']})\n{c['code']}"
        for c in unique_chunks
    )

    prompt = f"""You are a codebase assistant, your job is to answer questions about a codebase only from the provided context without inventing new answers. Answer the question using ONLY the code context below.
If the context doesn't fully answer the question, say so — don't guess or invent details.

CONTEXT:
{context}

QUESTION: {state['question']}

ANSWER (cite file names when relevant):"""

    response = generate_with_retry(prompt)
    state["final_answer"] = response.text
    state["sources"] = [
        {"file": c["metadata"]["file"], "lines": f"{c['metadata']['start_line']}-{c['metadata']['end_line']}"}
        for c in unique_chunks
    ]
    return state


def build_agent_graph():
    graph = StateGraph(AgentState)
    graph.add_node("retrieve_initial", retrieve_initial_node)
    graph.add_node("decide_followup", decide_followup_node)
    graph.add_node("retrieve_followup", retrieve_followup_node)
    graph.add_node("synthesize", synthesize_node)

    graph.set_entry_point("retrieve_initial")
    graph.add_edge("retrieve_initial", "decide_followup")
    graph.add_edge("decide_followup", "retrieve_followup")
    graph.add_edge("retrieve_followup", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


agent = build_agent_graph()


def answer_question_with_agent(question: str, repo_name: str) -> dict:
    result = agent.invoke({
        "question": question,
        "repo_name": repo_name,
        "initial_chunks": [],
        "followup_query": "",
        "followup_chunks": [],
        "final_answer": "",
        "sources": [],
    })
    return {"answer": result["final_answer"], "sources": result["sources"]}


if __name__ == "__main__":
    state = agent.invoke({
        "question": "How does FastAPI handle dependency injection, and where does Depends actually get used internally?",
        "repo_name": "fastapi",
        "initial_chunks": [], "followup_query": "", "followup_chunks": [],
        "final_answer": "", "sources": [],
    })
    print("FOLLOW-UP QUERY CHOSEN:", state["followup_query"])
    print("\nANSWER:\n", state["final_answer"])