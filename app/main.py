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
        # Open the corresponding object file in the .git/objects directory
        with open(f".git/objects/{obj_name[:2]}/{obj_name[2:]}", "rb") as f:
            # Decompress the file content
            raw = zlib.decompress(f.read())
            # Split the content into header and actual content
            header, content = raw.split(b"\0", maxsplit=1)
            # Print the content as a UTF-8 string
            print(content.decode(encoding="utf-8"), end="")

    # Handle the "hash-object" command with the "-w" flag to create a blob
    elif command == "hash-object":  # Changed this line
        if sys.argv[2] == "-w":
            # Get the file path from the arguments
            file_path = sys.argv[3]
            # Read the file content
            with open(file_path, "rb") as f:
                content = f.read()
            # Create the blob header in the format "blob <size>\0"
            header = f"blob {len(content)}\0".encode()
            # Combine the header and content
            store = header + content
            # Compute the SHA-1 hash of the blob
            sha1_hash = hashlib.sha1(store).hexdigest()
            # Determine the directory and file path for storing the blob
            obj_dir = f".git/objects/{sha1_hash[:2]}"
            obj_path = f"{obj_dir}/{sha1_hash[2:]}"
            # Create the directory if it doesn't exist
            if not os.path.exists(obj_dir):
                os.makedirs(obj_dir)
            # Write the compressed blob to the file
            with open(obj_path, "wb") as f:
                f.write(zlib.compress(store))
            # Print the SHA-1 hash of the blob
            print(sha1_hash)

        elif command == "ls-tree":
            param, tree_hash = sys.argv[2], sys.argv[3]
            if param == "--name-only":
                with open(f".git/objects/{tree_hash[:2]}/{tree_hash[2:]}", "rb") as f:
                    data = zlib.decompress(f.read())
                    _, body = data.split(b'\x00', 1)

                    i = 0
                    while i < len(body):
                    # Read mode and filename (till \0)
                        space_index = body.index(b' ', i)
                        null_index = body.index(b'\x00', space_index)
                        mode = body[i:space_index]
                        name = body[space_index + 1:null_index]
                        i = null_index + 1

                    # Read 20-byte SHA-1 hash
                        sha = body[i:i + 20]
                        i += 20

                    # Just print the name as per --name-only
                        print(name.decode())


        else:
            # Raise an error for unknown options
            raise RuntimeError(f"Unknown option for hash-object: #{sys.argv[2]}")  # More specific error

    # Handle unknown commands
    else:
        raise RuntimeError(f"Unknown command #{command}")


if __name__ == "__main__":
    main()