import os
import shutil
from git import Repo

CLONE_BASE_DIR = "cloned_repos"

import stat

def _remove_readonly(func, path, _):
    """Clears the read-only bit and retries deletion — needed because
    git marks some internal files read-only, which Windows blocks
    shutil.rmtree from deleting otherwise."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def clone_repo(repo_url: str) -> str:
    """
    Clones a public GitHub repo into a local folder.
    Returns the local path where it was cloned.
    """
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    local_path = os.path.join(CLONE_BASE_DIR, repo_name)

    # If we've already cloned this repo before, wipe it and re-clone fresh.
    # (Later we'll replace this with a smarter "check commit hash, only
    # re-clone if it changed" approach — for now, simple and correct.)
    if os.path.exists(local_path):
        shutil.rmtree(local_path, onerror=_remove_readonly)

    os.makedirs(CLONE_BASE_DIR, exist_ok=True)
    Repo.clone_from(repo_url, local_path, depth=1)  # shallow clone for speed

    return local_path


if __name__ == "__main__":
    # Quick manual test
    path = clone_repo("https://github.com/tiangolo/fastapi.git")
    print(f"Cloned to: {path}")