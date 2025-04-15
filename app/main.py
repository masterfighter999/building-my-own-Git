# Import required Python libraries
import sys              # For handling command-line arguments and system operations
import os              # For working with files and directories
import zlib            # For compressing and decompressing Git objects
import hashlib         # For creating SHA-1 hashes of Git objects
import struct          # For handling binary data
import time            # For timestamps in commit objects
import urllib.request  # For making HTTP requests to Git servers
import urllib.error    # For handling HTTP errors
from urllib.parse import urlparse  # For parsing Git repository URLs

# Define important Git directory structure constants
# These paths are relative to your repository root
GIT_DIR = ".git"                                    # Main Git directory
OBJECTS_DIR = os.path.join(GIT_DIR, "objects")     # Storage for all Git objects
HEAD_FILE = os.path.join(GIT_DIR, "HEAD")          # File that points to current branch
PACK_DIR = os.path.join(GIT_DIR, "objects", "pack") # Directory for packed objects

def init_repository():
    """
    Creates a new Git repository by setting up the necessary directory structure.
    This is what happens when you run 'git init'.
    """
    # Create all the directories Git needs
    # exist_ok=True means don't error if directory already exists
    os.makedirs(os.path.join(GIT_DIR, "refs", "heads"), exist_ok=True)  # For branches
    os.makedirs(OBJECTS_DIR, exist_ok=True)                             # For Git objects
    os.makedirs(PACK_DIR, exist_ok=True)                               # For packed objects
    
    # Create the HEAD file which points to the default branch (main)
    with open(HEAD_FILE, "w") as f:
        f.write("ref: refs/heads/main\n")
    print("Initialized git directory")

def hash_object(data, obj_type="blob"):
    """
    Creates a Git object from data and stores it in the repository.
    
    Args:
        data: The content to store (usually file contents)
        obj_type: Type of Git object ("blob", "tree", or "commit")
    
    Returns:
        The SHA-1 hash of the object (40 character hex string)
    
    This is similar to what happens when Git stores a file in its database.
    """
    # Step 1: Create the object header
    # Format: "<type> <size>\0<content>"
    header = f"{obj_type} {len(data)}\0".encode()
    
    # Step 2: Combine header and data
    store = header + data
    
    # Step 3: Calculate SHA-1 hash
    sha1 = hashlib.sha1(store).hexdigest()
    
    # Step 4: Prepare directory path
    # Git splits hash into directory (first 2 chars) and filename (rest)
    path = os.path.join(OBJECTS_DIR, sha1[:2], sha1[2:])
    
    # Step 5: Ensure directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    # Step 6: Write compressed content
    with open(path, "wb") as f:
        f.write(zlib.compress(store))
    
    return sha1

def read_object(path: str, sha: str):
    """
    Reads a Git object from the repository.
    
    Args:
        path: Path to repository root
        sha: The object's SHA-1 hash
    
    Returns:
        Tuple of (object_type, content)
    
    This is how Git reads stored objects back from its database.
    """
    # Construct path to the object file
    object_path = f"{path}/.git/objects/{sha[:2]}/{sha[2:]}"
    
    # Read and decompress the object
    with open(object_path, "rb") as f:
        data = zlib.decompress(f.read())
    
    # Split header from content at null byte
    null_pos = data.index(b"\x00")
    header = data[:null_pos]
    content = data[null_pos + 1:]
    
    # Get object type from header
    obj_type = header.split(b" ")[0].decode()
    
    return obj_type, content

def write_tree(path="."):
    """
    Creates a tree object from a directory structure.
    
    A tree object in Git represents a directory - it contains a list of files
    and other directories with their names, modes (permissions), and SHA-1 hashes.
    
    Args:
        path: Directory path to create tree from (defaults to current directory)
    
    Returns:
        SHA-1 hash of the created tree object
    """
    # Store list of entries (files and directories)
    entries = []
    
    # Scan directory and process each entry
    for entry in sorted(os.scandir(path), key=lambda e: e.name):
        # Skip the .git directory
        if entry.name == GIT_DIR:
            continue
            
        # Get full path of the entry
        full_path = os.path.join(path, entry.name)
        
        if entry.is_file():
            # Handle regular files
            with open(full_path, "rb") as f:
                # Create a blob object from file content
                sha1 = hash_object(f.read())
            # Mode 100644 means regular file
            mode = "100644"
            
        elif entry.is_dir():
            # Handle directories recursively
            # Create a tree object for subdirectory
            sha1 = write_tree(full_path)
            # Mode 40000 means directory
            mode = "40000"
            
        # Add entry to our list
        entries.append((mode, entry.name, sha1))

    # Create tree object content
    result = b""
    for mode, name, sha1 in entries:
        # Format: "<mode> <name>\0<SHA-1 in hex>"
        result += f"{mode} {name}\0".encode() + bytes.fromhex(sha1)
        
    # Store and return hash of tree object
    return hash_object(result, "tree")

def commit_tree(tree_sha, message, parent_sha=None):
    """
    Creates a commit object that points to a tree.
    
    A commit object stores:
    - Reference to a tree (the state of files)
    - Parent commit(s) (the previous version)
    - Author and committer information
    - Commit message
    
    Args:
        tree_sha: SHA-1 hash of the tree to commit
        message: Commit message
        parent_sha: SHA-1 hash of parent commit (optional)
    
    Returns:
        SHA-1 hash of the created commit object
    """
    # Set author/committer details
    author = "Your Name <you@example.com>"
    timestamp = int(time.time())  # Current Unix timestamp
    timezone = "-0000"           # UTC timezone
    
    # Build commit content
    lines = [
        f"tree {tree_sha}",  # Reference to the tree object
    ]
    
    # Add parent commit if provided
    if parent_sha:
        lines.append(f"parent {parent_sha}")
        
    # Add author and committer information
    lines.append(f"author {author} {timestamp} {timezone}")
    lines.append(f"committer {author} {timestamp} {timezone}")
    
    # Add blank line and commit message
    # Git format requires a blank line between metadata and message
    lines.append("")
    lines.append(message)
    
    # Join lines with newlines and add trailing newline
    # Git requires a trailing newline in commit objects
    commit_content = "\n".join(lines) + "\n"
    
    # Store and return hash of commit object
    return hash_object(commit_content.encode(), "commit")

def encode_sneaky_number(num):
    """Encodes a number into Git's sneaky encoding format."""
    result = bytearray()
    while num >= 0x80:
        result.append((num & 0x7f) | 0x80)
        num >>= 7
    result.append(num & 0x7f)
    return bytes(result)

def decode_sneaky_number(encoded_bytes):
    """Decodes a Git sneaky number into the original integer value."""
    result = 0
    shift = 0
    for byte in encoded_bytes:
        result |= (byte & 0x7f) << shift
        if byte & 0x80 == 0:
            break
        shift += 7
    return result

def decode_packfile(filename):
    """Decodes a Git packfile and handles the objects."""
    with open(filename, "rb") as f:
        header = f.read(4)
        if header != b'PACK':
            raise Exception("Invalid pack file")
        version = struct.unpack(">I", f.read(4))[0]
        num_objects = struct.unpack(">I", f.read(4))[0]

        for _ in range(num_objects):
            c = f.read(1)[0]
            obj_type = (c >> 4) & 7
            size = c & 0x0f
            shift = 4
            while c & 0x80:
                c = f.read(1)[0]
                size |= (c & 0x7f) << shift
                shift += 7

            data = read_compressed_data(f)
            if obj_type == 1:
                # commit
                hash_object(data, "commit")
            elif obj_type == 2:
                # tree
                hash_object(data, "tree")
            elif obj_type == 3:
                # blob
                hash_object(data, "blob")
            else:
                print(f"Skipping unsupported object type {obj_type}")

def read_compressed_data(f):
    """Reads and decompresses the object data from a packfile."""
    data = b""
    decompress = zlib.decompressobj()
    while True:
        chunk = f.read(512)
        if not chunk:
            break
        data += decompress.decompress(chunk)
        if decompress.unused_data:
            f.seek(-len(decompress.unused_data), 1)
            break
    return data

def clone_repository(url):
    """Simulates the cloning of a Git repository."""
    if not url.startswith("http://") and not url.startswith("https://"):
        print("Invalid git URL", file=sys.stderr)
        sys.exit(1)

    try:
        repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
        os.makedirs(repo_name, exist_ok=True)
        os.makedirs(os.path.join(repo_name, ".git/objects"), exist_ok=True)
        os.makedirs(os.path.join(repo_name, ".git/refs"), exist_ok=True)
        with open(os.path.join(repo_name, ".git/HEAD"), "w") as f:
            f.write("ref: refs/heads/main\n")

        # Simulate downloading pack file
        pack_url = f"{url.rstrip('/')}/objects/pack/pack-*.pack"
        print("Cloned repository from", url)
        # Here you would download and save the pack file for decoding
    except Exception as e:
        print(f"Error cloning repository: {e}", file=sys.stderr)
        sys.exit(1)

def clone():
    # Get repository URL and directory
    remote = sys.argv[2]
    if len(sys.argv) == 4:
        local = sys.argv[3]
    else:
        parsed = urlparse(remote)
        local = parsed.path.split("/")[-1].replace(".git", "")
    # Initialize repository
    os.makedirs(local, exist_ok=True)
    os.makedirs(os.path.join(local, ".git", "objects"), exist_ok=True)
    os.makedirs(os.path.join(local, ".git", "refs"), exist_ok=True)
    print(f"Cloning {remote} to {local}")
    # Fetch refs
    caps, refs = get_refs(remote)
    default_branch = caps.get("default_branch", "refs/heads/main")
    default_ref_sha = None
    for sha, ref in refs:
        if ref == default_branch:
            default_ref_sha = sha
            break
    if default_ref_sha is None:
        raise RuntimeError(f"Default branch not found: {default_branch}")
    # Download and process packfile
    print(f"Downloading {default_branch} ({default_ref_sha})")
    packfile = download_packfile(remote, default_ref_sha)
    write_packfile(packfile, local)
    # Write HEAD ref
    with open(os.path.join(local, ".git", "HEAD"), "w") as f:
        f.write(f"ref: {default_branch}\n")
    # Write branch ref
    ref_dir = os.path.join(local, ".git", os.path.dirname(default_branch))
    os.makedirs(ref_dir, exist_ok=True)
    with open(os.path.join(local, ".git", default_branch), "w") as f:
        f.write(f"{default_ref_sha}\n")
    # Read the commit and tree
    _, commit_content = read_object(local, default_ref_sha)
    tree_sha = commit_content[5:45].decode()  # Extract tree SHA from commit
    # Render the tree to the working directory
    render_tree(local, local, tree_sha)

def get_refs(url: str):
    """Fetch refs using Smart HTTP protocol."""
    url = f"{url}/info/refs?service=git-upload-pack"
    req = urllib.request.Request(url)
    refs, caps = [], {}
    with urllib.request.urlopen(req) as response:
        lines = response.read().split(b"\n")
    # parse capabilities
    cap_bytes = lines[1].split(b"\x00")[1]
    for cap in cap_bytes.split(b" "):
        if cap.startswith(b"symref=HEAD:"):
            caps["default_branch"] = cap.split(b":")[1].decode()
        else:
            caps[cap.decode()] = True
    # parse refs
    for line in lines[2:]:
        if line.startswith(b"0000"):
            break
        sha, ref_name = line.decode().split(" ")
        refs.append((sha[4:], ref_name))
    return caps, refs

def download_packfile(url: str, want_ref: str) -> bytes:
    """Download a packfile using Git protocol v2."""
    url = f"{url}/git-upload-pack"
    body = (
        b"0011command=fetch0001000fno-progress"
        + f"0032want {want_ref}\n".encode()
        + b"0009done\n0000"
    )
    headers = {
        "Content-Type": "application/x-git-upload-pack-request",
        "Git-Protocol": "version=2",
    }
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req) as response:
        data = response.read()
    pack_lines = []
    while data:
        line_len = int(data[:4], 16)
        if line_len == 0:
            break
        pack_lines.append(data[4:line_len])
        data = data[line_len:]
    return b"".join(l[1:] for l in pack_lines[1:])

def write_packfile(data: bytes, target_dir: str) -> None:
    """Parse and write a packfile to the target directory."""
    git_dir = os.path.join(target_dir, ".git")
    def next_size_type(bs: bytes):
        ty = (bs[0] & 0b01110000) >> 4
        type_map = {
            1: "commit",
            2: "tree",
            3: "blob",
            4: "tag",
            6: "ofs_delta",
            7: "ref_delta",
        }
        ty = type_map.get(ty, "unknown")
        size = bs[0] & 0b00001111
        i = 1
        shift = 4
        while bs[i - 1] & 0b10000000:
            size |= (bs[i] & 0b01111111) << shift
            shift += 7
            i += 1
        return ty, size, bs[i:]
    def next_size(bs: bytes):
        size = bs[0] & 0b01111111
        i = 1
        shift = 7
        while bs[i - 1] & 0b10000000:
            size |= (bs[i] & 0b01111111) << shift
            shift += 7
            i += 1
        return size, bs[i:]
    data = data[8:]
    n_objects = struct.unpack("!I", data[:4])[0]
    data = data[4:]
    print(f"Processing {n_objects} objects")
    objects = []
    remaining_data = data
    for _ in range(n_objects):
        obj_type, _, remaining_data = next_size_type(remaining_data)
        if obj_type in ["commit", "tree", "blob", "tag"]:
            decomp = zlib.decompressobj()
            content = decomp.decompress(remaining_data)
            remaining_data = decomp.unused_data
            objects.append((obj_type, content, None))
        elif obj_type == "ref_delta":
            base_sha = remaining_data[:20].hex()
            remaining_data = remaining_data[20:]
            decomp = zlib.decompressobj()
            delta = decomp.decompress(remaining_data)
            remaining_data = decomp.unused_data
            objects.append(("ref_delta", delta, base_sha))
    processed_objects = set()
    def process_object(obj_data):
        obj_type, content, base_sha = obj_data
        if obj_type != "ref_delta":
            store = f"{obj_type} {len(content)}\x00".encode() + content
            sha = hashlib.sha1(store).hexdigest()
            path = os.path.join(git_dir, "objects", sha[:2])
            os.makedirs(path, exist_ok=True)
            with open(os.path.join(path, sha[2:]), "wb") as f:
                f.write(zlib.compress(store))
            processed_objects.add(sha)
            return sha
        else:
            if base_sha not in processed_objects:
                for obj in objects:
                    if (
                        obj[0] != "ref_delta"
                        and hashlib.sha1(
                            f"{obj[0]} {len(obj[1])}\x00".encode() + obj[1]
                        ).hexdigest()
                        == base_sha
                    ):
                        process_object(obj)
                        break
            with open(f"{git_dir}/objects/{base_sha[:2]}/{base_sha[2:]}", "rb") as f:
                base_content = zlib.decompress(f.read())
            base_type = base_content.split(b" ")[0].decode()
            base_content = base_content.split(b"\x00", 1)[1]
            delta = content
            _, delta = next_size(delta)
            _, delta = next_size(delta)
            result = b""
            while delta:
                cmd = delta[0]
                if cmd & 0b10000000:
                    pos = 1
                    offset = 0
                    size = 0
                    for i in range(4):
                        if cmd & (1 << i):
                            offset |= delta[pos] << (i * 8)
                            pos += 1
                    for i in range(3):
                        if cmd & (1 << (4 + i)):
                            size |= delta[pos] << (i * 8)
                            pos += 1
                    result += base_content[offset : offset + size]
                    delta = delta[pos:]
                else:
                    size = cmd
                    result += delta[1 : size + 1]
                    delta = delta[size + 1 :]
            store = f"{base_type} {len(result)}\x00".encode() + result
            sha = hashlib.sha1(store).hexdigest()
            path = os.path.join(git_dir, "objects", sha[:2])
            os.makedirs(path, exist_ok=True)
            with open(os.path.join(path, sha[2:]), "wb") as f:
                f.write(zlib.compress(store))
            processed_objects.add(sha)
            return sha
    for obj in objects:
        process_object(obj)

def render_tree(repo_path: str, dir_path: str, sha: str):
    """
    Recursively render a Git tree object to the filesystem.
    """
    print(f"Rendering tree {sha} to {dir_path}")
    os.makedirs(dir_path, exist_ok=True)
    _, tree_content = read_object(repo_path, sha)
    while tree_content:
        mode, tree_content = tree_content.split(b" ", 1)
        name, tree_content = tree_content.split(b"\x00", 1)
        entry_sha = tree_content[:20].hex()
        tree_content = tree_content[20:]
        entry_path = os.path.join(dir_path, name.decode())
        if mode == b"40000":
            render_tree(repo_path, entry_path, entry_sha)
        elif mode == b"100644":
            _, content = read_object(repo_path, entry_sha)
            with open(entry_path, "wb") as f:
                f.write(content)
        else:
            raise RuntimeError(f"Unsupported mode: {mode}")

def ls_tree(sha1, name_only=False):
    """List the contents of a tree object."""
    # Use current directory as the repository path
    obj_type, content = read_object(".", sha1)
    if obj_type != "tree":
        raise RuntimeError(f"Object {sha1} is not a tree")
    
    while content:
        # Find the space and null byte separating mode, name, and SHA-1
        space_index = content.index(b' ')
        null_index = content.index(b'\0', space_index)
        
        # Extract mode, name, and SHA-1
        mode = content[:space_index].decode()
        name = content[space_index + 1:null_index].decode()
        sha = content[null_index + 1:null_index + 21].hex()
        
        # Print the entry
        if name_only:
            print(name)
        else:
            print(f"{mode} blob {sha}\t{name}")
            
        # Move to next entry
        content = content[null_index + 21:]

def main():
    """Main entry point for the program.
    
    Handles different Git commands:
    - init: Initialize a new repository
    - cat-file: Display contents of Git objects
    - hash-object: Compute object ID and optionally create a blob
    - write-tree: Create a tree object from the current directory
    - commit-tree: Create a commit object
    - clone: Clone a remote repository
    - ls-tree: List contents of a tree object
    """
    command = sys.argv[1]  # Get the Git command from command line arguments

    if command == "init":
        # Initialize a new Git repository in the current directory
        init_repository()

    elif command == "cat-file" and sys.argv[2] == "-p":
        # Print the contents of a Git object
        # -p flag means "pretty-print" the contents
        obj_type, content = read_object(".", sys.argv[3])
        print(content.decode(), end="")

    elif command == "hash-object" and sys.argv[2] == "-w":
        # Compute object ID and optionally write it to object database
        # -w flag means "write" the object
        with open(sys.argv[3], "rb") as f:
            print(hash_object(f.read()))

    elif command == "write-tree":
        # Create a tree object from the current working directory
        print(write_tree())

    elif command == "commit-tree":
        # Create a new commit object
        tree_sha = sys.argv[2]  # SHA-1 of the tree to commit
        parent_sha = None  # Parent commit SHA-1 (if any)
        message = None    # Commit message

        # Parse command line arguments
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "-p":
                # -p flag specifies parent commit
                parent_sha = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "-m":
                # -m flag specifies commit message
                message = sys.argv[i + 1]
                i += 2
            else:
                i += 1

        # If no message was provided via -m, read it from stdin
        if not message:
            message = sys.stdin.read().strip()
        
        # Create the commit and print its SHA-1
        print(commit_tree(tree_sha, message, parent_sha))

    elif command == "clone":
        # Clone a remote repository
        clone()

    elif command == "ls-tree":
        # List the contents of a tree object
        if len(sys.argv) < 3:
            raise RuntimeError("ls-tree requires a tree hash")
            
        # Parse command line arguments
        tree_hash = None  # SHA-1 of the tree to list
        name_only = False # Flag to show only filenames
        
        # Process each argument
        for arg in sys.argv[2:]:
            if arg == "--name-only":
                # --name-only flag shows only the file names
                name_only = True
            elif not tree_hash:
                # First non-flag argument is the tree hash
                tree_hash = arg
                
        # Ensure we got a tree hash
        if not tree_hash:
            raise RuntimeError("ls-tree requires a tree hash")
            
        # List the tree contents
        ls_tree(tree_hash, name_only)

    else:
        # Unknown or unsupported command
        raise RuntimeError(f"Unknown command {command}")

if __name__ == "__main__":
    main()
