import sys
import os
import zlib
import hashlib


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
        # Git objects are stored in directories named with first 2 chars of hash
        # Remaining hash chars form the filename
        with open(f".git/objects/{obj_name[:2]}/{obj_name[2:]}", "rb") as f:
            # Git objects are stored compressed with zlib
            raw = zlib.decompress(f.read())
            # Object format: <type> <size>\0<content>
            # Split at first null byte to separate header from content
            header, content = raw.split(b"\0", maxsplit=1)
            # Display the actual content (works for both blob and tree)
            print(content.decode(encoding="utf-8"), end="")

    # Handle the "hash-object" command with the "-w" flag to create a blob
    elif command == "hash-object":
        if sys.argv[2] == "-w":
            # Get the file path from the arguments
            file_path = sys.argv[3]
            # Read file in binary mode to handle all file types
            with open(file_path, "rb") as f:
                content = f.read()
            # Git blob format: "blob <size>\0<content>"
            # The header describes the type and size of content
            header = f"blob {len(content)}\0".encode()
            store = header + content
            # SHA-1 hash is computed on the complete object (header + content)
            sha1_hash = hashlib.sha1(store).hexdigest()
            # Store object in .git/objects/<first-2-chars>/<remaining-38-chars>
            obj_dir = f".git/objects/{sha1_hash[:2]}"
            obj_path = f"{obj_dir}/{sha1_hash[2:]}"
            # Create the directory if it doesn't exist
            if not os.path.exists(obj_dir):
                os.makedirs(obj_dir)
            # Compress the object before storing
            with open(obj_path, "wb") as f:
                f.write(zlib.compress(store))
            # Print the SHA-1 hash of the blob
            print(sha1_hash)

        else:
            # Raise an error for unknown options
            raise RuntimeError(f"Unknown option for hash-object: #{sys.argv[2]}")  # More specific error

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

    elif command == "write-tree":
        # Initialize an empty list to store tree entries
        tree_entries = []

        # Iterate over the files in the current directory
        for root, dirs, files in os.walk("."):
            # Skip the .git directory
            if root.startswith("./.git"):
                continue

            for file_name in files:
                # Get the relative file path
                file_path = os.path.join(root, file_name).replace("\\", "/").lstrip("./")

                # Read the file content
                with open(file_path, "rb") as f:
                    content = f.read()

                # Create a blob object for the file
                header = f"blob {len(content)}\0".encode()
                store = header + content
                sha1_hash = hashlib.sha1(store).hexdigest()

                # Write the blob to the .git/objects directory
                obj_dir = f".git/objects/{sha1_hash[:2]}"
                obj_path = f"{obj_dir}/{sha1_hash[2:]}"
                if not os.path.exists(obj_dir):
                    os.makedirs(obj_dir)
                with open(obj_path, "wb") as f:
                    f.write(zlib.compress(store))

                # Add the file entry to the tree
                mode = "100644"  # Regular file mode
                tree_entries.append(f"{mode} {file_name}\0".encode() + bytes.fromhex(sha1_hash))

        # Combine all tree entries
        tree_content = b"".join(tree_entries)

        # Create the tree object
        header = f"tree {len(tree_content)}\0".encode()
        store = header + tree_content
        sha1_hash = hashlib.sha1(store).hexdigest()

        # Write the tree object to the .git/objects directory
        obj_dir = f".git/objects/{sha1_hash[:2]}"
        obj_path = f"{obj_dir}/{sha1_hash[2:]}"
        if not os.path.exists(obj_dir):
            os.makedirs(obj_dir)
        with open(obj_path, "wb") as f:
            f.write(zlib.compress(store))

        # Print the SHA-1 hash of the tree object
        print(sha1_hash)

    # Handle unknown commands
    else:
        raise RuntimeError(f"Unknown command #{command}")


if __name__ == "__main__":
    main()