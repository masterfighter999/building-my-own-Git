import sys
import os
import zlib
import hashlib

def create_blob_entry(path, write=True):
    """Create a Git blob object from a file and optionally write it to .git/objects."""

    """   
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
    """Create a Git tree object from a directory and write it to .git/objects."""

    """
    Create a tree object from a directory and write it to .git/objects
    
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
        sha1 = bytes.fromhex(write_tree(full))  # Corrected line
        s += sha1
    s = f"tree {len(s)}\0".encode() + s
    sha1 = hashlib.sha1(s).hexdigest()
    os.makedirs(f".git/objects/{sha1[:2]}", exist_ok=True)
    with open(f".git/objects/{sha1[:2]}/{sha1[2:]}", "wb") as f:
        f.write(zlib.compress(s))
    return sha1

def commit_tree(tree_hash, parent_hash=None, message=""):
    """
    Create a Git commit object and write it to .git/objects.

    Args:
        tree_hash: The SHA-1 hash of the tree object.
        parent_hash: The SHA-1 hash of the parent commit (optional).
        message: The commit message.

    Returns:
        SHA-1 hash of the commit object.
    """
    # Prepare the commit object content
    lines = [f"tree {tree_hash}"]
    if parent_hash:
        lines.append(f"parent {parent_hash}")
    lines.append(f"author You <you@example.com> 1234567890 +0000")
    lines.append(f"committer You <you@example.com> 1234567890 +0000")
    lines.append("")
    lines.append(message)
    content = "\n".join(lines).encode("utf-8")

    # Add the header
    header = f"commit {len(content)}\0".encode("utf-8")
    store = header + content

    # Compute the SHA-1 hash
    sha = hashlib.sha1(store).hexdigest()

    # Write the commit object to .git/objects
    os.makedirs(f".git/objects/{sha[:2]}", exist_ok=True)
    with open(f".git/objects/{sha[:2]}/{sha[2:]}", "wb") as f:
        f.write(zlib.compress(store))

    return sha

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

    elif command == "commit-tree":
        # Get the tree hash from the arguments
        tree_hash = sys.argv[2]
        # Get the parent hash if provided
        parent_hash = sys.argv[3] if len(sys.argv) > 3 else None
        # Read the commit message from standard input
        message = sys.stdin.read().strip()
        # Create the commit object
        sha1_hash = commit_tree(tree_hash, parent_hash, message)
        print(sha1_hash)

    # Handle unknown commands
    else:
        raise RuntimeError(f"Unknown command #{command}")


if __name__ == "__main__":
    main()