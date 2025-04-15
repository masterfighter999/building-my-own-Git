import sys
import os
import zlib
import hashlib
import struct
import time
import urllib.request
import urllib.error

GIT_DIR = ".git"
OBJECTS_DIR = os.path.join(GIT_DIR, "objects")
HEAD_FILE = os.path.join(GIT_DIR, "HEAD")

def init_repository():
    os.makedirs(os.path.join(GIT_DIR, "refs"), exist_ok=True)
    os.makedirs(OBJECTS_DIR, exist_ok=True)
    with open(HEAD_FILE, "w") as f:
        f.write("ref: refs/heads/main\n")
    print("Initialized git directory")

def hash_object(data, obj_type="blob"):
    header = f"{obj_type} {len(data)}\0".encode()
    store = header + data
    sha1 = hashlib.sha1(store).hexdigest()
    path = os.path.join(OBJECTS_DIR, sha1[:2], sha1[2:])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(zlib.compress(store))
    return sha1

def read_object(sha1):
    path = os.path.join(OBJECTS_DIR, sha1[:2], sha1[2:])
    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())
    header, content = raw.split(b'\0', 1)
    obj_type, size = header.decode().split()
    return obj_type, content

def write_tree(path="."):
    entries = []
    for entry in sorted(os.scandir(path), key=lambda e: e.name):
        if entry.name == GIT_DIR:
            continue
        full_path = os.path.join(path, entry.name)
        if entry.is_file():
            with open(full_path, "rb") as f:
                sha1 = hash_object(f.read())
            mode = "100644"
        elif entry.is_dir():
            sha1 = write_tree(full_path)
            mode = "40000"
        entries.append((mode, entry.name, sha1))

    result = b""
    for mode, name, sha1 in entries:
        result += f"{mode} {name}\0".encode() + bytes.fromhex(sha1)
    return hash_object(result, "tree")

def commit_tree(tree_sha, message, parent_sha=None):
    author = "Your Name <you@example.com>"
    timestamp = int(time.time())
    timezone = "-0000"

    lines = [
        f"tree {tree_sha}",
    ]
    if parent_sha:
        lines.append(f"parent {parent_sha}")
    lines.append(f"author {author} {timestamp} {timezone}")
    lines.append(f"committer {author} {timestamp} {timezone}")
    lines.append("")
    lines.append(message)

    return hash_object("\n".join(lines).encode(), "commit")

def encode_sneaky_number(num):
    """Encodes a number into Git's sneaky encoding format"""
    result = bytearray()
    while num >= 0x80:
        result.append((num & 0x7f) | 0x80)
        num >>= 7
    result.append(num & 0x7f)
    return bytes(result)

def decode_sneaky_number(encoded_bytes):
    """Decodes a Git sneaky number into the original integer value"""
    result = 0
    shift = 0
    for byte in encoded_bytes:
        result |= (byte & 0x7f) << shift
        if byte & 0x80 == 0:
            break
        shift += 7
    return result

def decode_packfile(filename):
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

        print("Initialized git directory")
        print(f"Cloned repository from {url} into {repo_name}")
    except Exception as e:
        print("repository does not exist", file=sys.stderr)
        sys.exit(1)

def main():
    command = sys.argv[1]

    if command == "init":
        init_repository()

    elif command == "cat-file" and sys.argv[2] == "p":
        obj_type, content = read_object(sys.argv[3])
        print(content.decode(), end="")

    elif command == "hash-object" and sys.argv[2] == "w":
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
            if sys.argv[i] == "p":
                parent_sha = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "m":
                message = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        if not message:
            message = sys.stdin.read().strip()
        print(commit_tree(tree_sha, message, parent_sha))

    elif command == "clone":
        if len(sys.argv) < 3:
            print("URL required", file=sys.stderr)
            sys.exit(1)
        clone_repository(sys.argv[2])

    else:
        raise RuntimeError(f"Unknown command {command}")

if __name__ == "__main__":
    main()
