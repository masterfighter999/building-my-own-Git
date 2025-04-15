import sys
import os
import zlib
import hashlib
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

GIT_DIR = ".git"
OBJECTS_DIR = os.path.join(GIT_DIR, "objects")
INDEX_FILE = os.path.join(GIT_DIR, "index")
HEAD_FILE = os.path.join(GIT_DIR, "HEAD")

def init_repository():
    """Initialize a new Git repository."""
    os.makedirs(OBJECTS_DIR, exist_ok=True)
    os.makedirs(os.path.join(GIT_DIR, "refs"), exist_ok=True)
    with open(HEAD_FILE, "w") as f:
        f.write("ref: refs/heads/main\n")
    print("Initialized git directory")

def hash_object(data, obj_type="blob"):
    """Create a Git object and return its hash."""
    header = f"{obj_type} {len(data)}\0".encode()
    store = header + data
    sha1 = hashlib.sha1(store).hexdigest()
    path = os.path.join(OBJECTS_DIR, sha1[:2], sha1[2:])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(zlib.compress(store))
    return sha1

def read_object(sha1):
    """Read a Git object and return its content."""
    path = os.path.join(OBJECTS_DIR, sha1[:2], sha1[2:])
    if not os.path.exists(path):
        raise RuntimeError(f"Object {sha1} not found")
    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())
    header, content = raw.split(b"\0", 1)
    obj_type, size = header.decode().split()
    return obj_type, content

def write_tree(path="."):
    """Create a Git tree object from a directory."""
    entries = []
    for entry in sorted(os.scandir(path), key=lambda e: e.name):
        if entry.name == GIT_DIR:
            continue
        full_path = os.path.join(path, entry.name)
        if entry.is_file():
            with open(full_path, "rb") as f:
                sha1 = hash_object(f.read())
            mode = "100644"
            entries.append((mode, entry.name, sha1))
        elif entry.is_dir():
            sha1 = write_tree(full_path)
            mode = "40000"
            entries.append((mode, entry.name, sha1))
    
    tree_content = b""
    for mode, name, sha1 in entries:
        tree_content += f"{mode} {name}\0".encode() + bytes.fromhex(sha1)
    return hash_object(tree_content, "tree")

def commit_tree(tree_sha, message, parent_sha=None):
    """Create a Git commit object."""
    author = "Your Name <you@example.com>"
    timestamp = int(time.time())
    timezone = "-0500"

    commit_content = []
    commit_content.append(f"tree {tree_sha}")
    if parent_sha:
        commit_content.append(f"parent {parent_sha}")
    commit_content.append(f"author {author} {timestamp} {timezone}")
    commit_content.append(f"committer {author} {timestamp} {timezone}")
    commit_content.append("")
    commit_content.append(message)
    
    return hash_object("\n".join(commit_content).encode(), "commit")

def clone_repository(url):
    if not url.endswith(".git"):
        print("Invalid git URL", file=sys.stderr)
        sys.exit(1)

    try:
        info_refs_url = f"{url}/info/refs?service=git-upload-pack"
        req = urllib.request.Request(info_refs_url)
        with urllib.request.urlopen(req) as response:
            if response.status != 200:
                raise Exception("Invalid response from server")

    except urllib.error.HTTPError as e:
        print("repository does not exist", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print("repository does not exist", file=sys.stderr)
        sys.exit(1)

    repo_name = url.split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    os.makedirs(repo_name, exist_ok=True)

    git_dir = os.path.join(repo_name, ".git")
    os.makedirs(os.path.join(git_dir, "objects"), exist_ok=True)
    os.makedirs(os.path.join(git_dir, "refs"), exist_ok=True)

    with open(os.path.join(git_dir, "HEAD"), "w") as f:
        f.write("ref: refs/heads/main\n")

    print("Initialized git directory")
    print(f"Cloned repository from {url} into {repo_name}")

def main():
    command = sys.argv[1]

    if command == "init":
        init_repository()
        
    elif command == "cat-file" and sys.argv[2] == "-p":
        obj_type, content = read_object(sys.argv[3])
        if obj_type in ("blob", "commit"):
            print(content.decode(), end="")
        else:
            raise RuntimeError(f"Unsupported object type: {obj_type}")
            
    elif command == "hash-object" and sys.argv[2] == "-w":
        with open(sys.argv[3], "rb") as f:
            print(hash_object(f.read()))
            
    elif command == "write-tree":
        print(write_tree())
        
    elif command == "commit-tree":
        tree_sha = sys.argv[2]
        parent_sha = None
        message = None
        
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "-p":
                parent_sha = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "-m":
                message = sys.argv[i + 1]
                i += 2
            else:
                i += 1
                
        if not message:
            message = sys.stdin.read().strip()
            
        print(commit_tree(tree_sha, message, parent_sha))
        
    elif command == "clone":
        if len(sys.argv) < 3:
            raise RuntimeError("clone command requires a repository URL")
        clone_repository(sys.argv[2])
        
    else:
        raise RuntimeError(f"Unknown command {command}")

if __name__ == "__main__":
    main()