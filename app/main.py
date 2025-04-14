import sys
import os
import zlib
import hashlib
import time
from pathlib import Path
import shutil  # Move this import to the top

def create_blob_entry(path, write=True):
    """Create a Git blob object from a file and optionally write it to .git/objects.

    Args:
        path: Path to the file to create blob from
        write: Whether to write the blob to .git/objects directory

    Returns:
        SHA-1 hash of the blob
    """
    with open(path, "rb") as f:
        data = f.read()
        header = f"blob {len(data)}\0".encode("utf-8")
        store = header + data
        sha = hashlib.sha1(store).hexdigest()
        if write:
            os.makedirs(f".git/objects/{sha[:2]}", exist_ok=True)
            with open(f".git/objects/{sha[:2]}/{sha[2:]}", "wb") as f:
                f.write(zlib.compress(store))
    return sha

def write_tree(path: str):
    """Create a Git tree object from a directory and write it to .git/objects.

    Args:
        path: Path to the directory to create tree from

    Returns:
        SHA-1 hash of the tree
    """
    if os.path.isfile(path):
        return create_blob_entry(path)
    
    contents = sorted(
        os.listdir(path),
        key=lambda x: x if os.path.isfile(os.path.join(path, x)) else f"{x}/",
    )
    s = b""
    for item in contents:
        if item == ".git":
            continue
        full = os.path.join(path, item)
        if os.path.isfile(full):
            s += f"100644 {item}\0".encode()
        else:
            s += f"40000 {item}\0".encode()
        sha1 = int.to_bytes(int(write_tree(full), base=16), length=20, byteorder="big")
        s += sha1
    s = f"tree {len(s)}\0".encode() + s
    sha1 = hashlib.sha1(s).hexdigest()
    os.makedirs(f".git/objects/{sha1[:2]}", exist_ok=True)
    with open(f".git/objects/{sha1[:2]}/{sha1[2:]}", "wb") as f:
        f.write(zlib.compress(s))
    return sha1

def write_object(repo_path: Path, obj_type: str, contents: bytes) -> str:
    """Write a git object and return its hash.

    Args:
        repo_path: Path to git repository
        obj_type: Object type (commit, tree, blob)
        contents: Object contents

    Returns:
        SHA-1 hash of the object
    """
    header = f"{obj_type} {len(contents)}\0".encode()
    store = header + contents
    sha = hashlib.sha1(store).hexdigest()
    obj_path = repo_path / ".git" / "objects" / sha[:2] / sha[2:]
    obj_path.parent.mkdir(exist_ok=True)
    obj_path.write_bytes(zlib.compress(store))
    return sha

def clone_repo(remote_path: str, local_path: str):
    """
    Clone a Git repository from a remote .git directory to a local path.

    Args:
        remote_path: Path to the source Git repository (.git folder)
        local_path: Path to clone the repository into
    """
    # Ensure the remote path ends with /.git if needed
    remote_git = Path(remote_path).resolve()
    if not remote_git.name == ".git":
        remote_git = remote_git / ".git"

    # Define the target path for the cloned repo
    local_git = Path(local_path) / ".git"

    # Copy .git directory
    if not remote_git.exists():
        raise RuntimeError(f"Remote Git directory not found: {remote_git}")
    
    shutil.copytree(remote_git, local_git)

    # Optionally create a working directory with checked-out files
    # Here we just create the directory; checking out files is not implemented yet
    os.makedirs(local_path, exist_ok=True)

    print(f"Cloned Git repository from {remote_path} to {local_path}")

def main():
    # Debugging logs will appear in the standard error stream
    print("Logs from your program will appear here!", file=sys.stderr)

    # Get the command from the first argument
    command = sys.argv[1]

    # Handle the "init" command to initialize a Git repository
    if command == "init":
        # Create necessary directories for a Git repository
        os.mkdir(".git")
        os.mkdir(".git/objects")
        os.mkdir(".git/refs")
        # Create the HEAD file pointing to the main branch
        with open(".git/HEAD", "w") as f:
            f.write("ref: refs/heads/main\n")
        print("Initialized git directory")

    # Handle the "cat-file" command with the "-p" flag to print the content of a Git object
    elif command == "cat-file" and sys.argv[2] == "-p":
        # Get the object name (SHA-1 hash) from the arguments
        obj_name = sys.argv[3]
        # Open the corresponding object file in the .git/objects directory
        with open(f".git/objects/{obj_name[:2]}/{obj_name[2:]}", "rb") as f:
            # Decompress the file content
            raw = zlib.decompress(f.read())
            # Split the content into header and actual content
            header, content = raw.split(b"\0", maxsplit=1)
            # Print the content as a UTF-8 string
            print(content.decode(encoding="utf-8"), end="")

    # Handle the "hash-object" command with the "-w" flag to create a blob
    elif command == "hash-object":
        if sys.argv[2] == "-w":
            file_path = sys.argv[3]
            sha1_hash = create_blob_entry(file_path)
            print(sha1_hash)
        else:
            raise RuntimeError(f"Unknown option for hash-object: #{sys.argv[2]}")

    # Add write-tree command handling
    elif command == "write-tree":
        sha1_hash = write_tree(".")
        print(sha1_hash)

    # Handle the "ls-tree" command to list tree entries
    elif command == "ls-tree":
        # Check if we have at least 2 arguments
        if len(sys.argv) < 3:
            raise RuntimeError("ls-tree requires a tree hash")
        # Get parameters and tree hash
        param = sys.argv[2]
        tree_hash = sys.argv[3] if param.startswith('--') else sys.argv[2]
        # Read and decompress the tree object
        with open(f".git/objects/{tree_hash[:2]}/{tree_hash[2:]}", "rb") as f:
            data = zlib.decompress(f.read())
        # Split header and content
        header, content = data.split(b'\x00', 1)
        # Verify this is a tree object
        if not header.startswith(b'tree'):
            raise RuntimeError(f"Object {tree_hash} is not a tree")
        # Parse entries based on format
        i = 0
        while i < len(content):
            # Find the space that separates mode from name
            space_index = content.index(b' ', i)
            # Find the null byte that separates name from SHA
            null_index = content.index(b'\x00', space_index)
            # Extract mode, name and SHA
            mode = content[i:space_index].decode()
            name = content[space_index + 1:null_index].decode()
            sha = content[null_index + 1:null_index + 21].hex()
            # Move index to next entry
            i = null_index + 21
            if param == "--name-only":
                # Print only the filename
                print(name)
            else:
                # Print full entry: mode type hash name
                print(f"{mode} blob {sha}\t{name}")

    # Handle the "commit-tree" command to create a commit object
    elif command == "commit-tree":
        # Parse arguments
        if len(sys.argv) < 3:
            raise RuntimeError("commit-tree requires a tree hash")
        tree_sha = sys.argv[2]
        parent_sha = None
        message = None
        # Parse optional arguments
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "-p":
                if i + 1 >= len(sys.argv):
                    raise RuntimeError("-p requires a parent hash")
                parent_sha = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "-m":
                if i + 1 >= len(sys.argv):
                    raise RuntimeError("-m requires a message")
                message = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        if not message:
            message = sys.stdin.read().strip()
        # Generate timestamp
        timestamp = int(time.time())
        timezone = "-0500"  # Example timezone, adjust as needed
        # Build commit contents
        contents = []
        contents.append(f"tree {tree_sha}\n".encode())
        if parent_sha:
            contents.append(f"parent {parent_sha}\n".encode())
        contents.append(f"author Your Name <you@example.com> {timestamp} {timezone}\n".encode())
        contents.append(f"committer Your Name <you@example.com> {timestamp} {timezone}\n".encode())
        contents.append(b"\n")
        contents.append(message.encode())
        contents.append(b"\n")
        # Write commit object and print hash
        hash = write_object(Path("."), "commit", b"".join(contents))
        print(hash)

    # Handle the "clone" command to clone a repository
    elif command == "clone":
        if len(sys.argv) != 4:
            raise RuntimeError("Usage: clone <remote_path> <local_path>")
        remote = sys.argv[2]
        local = sys.argv[3]
        clone_repo(remote, local)

    # Handle unknown commands
    else:
        raise RuntimeError(f"Unknown command #{command}")

if __name__ == "__main__":
    main()