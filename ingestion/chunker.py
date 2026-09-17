import os
from tree_sitter import Language, Parser
import tree_sitter_python as tspython

PY_LANGUAGE = Language(tspython.language())
parser = Parser(PY_LANGUAGE)


def chunk_python_file(file_path: str, repo_root: str) -> list[dict]:
    """
    Parses a single .py file and returns a list of chunks,
    one per top-level function or class definition.
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        source_code = f.read()

    tree = parser.parse(bytes(source_code, "utf-8"))
    root_node = tree.root_node

    chunks = []
    relative_path = os.path.relpath(file_path, repo_root)

    for node in root_node.children:
        if node.type in ("function_definition", "class_definition"):
            chunk_text = source_code[node.start_byte:node.end_byte]
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf-8") if name_node else "unknown"

            chunks.append({
                "file": relative_path,
                "name": name,
                "type": node.type,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "code": chunk_text,
            })

    return chunks


def chunk_repo(repo_path: str) -> list[dict]:
    """
    Walks every .py file in the repo and chunks it.
    """
    all_chunks = []
    for dirpath, _, filenames in os.walk(repo_path):
        for filename in filenames:
            if filename.endswith(".py"):
                file_path = os.path.join(dirpath, filename)
                all_chunks.extend(chunk_python_file(file_path, repo_path))

    return all_chunks


if __name__ == "__main__":
    chunks = chunk_repo("cloned_repos/fastapi")
    print(f"Total chunks: {len(chunks)}")
    print("Example chunk:")
    print(chunks[0])