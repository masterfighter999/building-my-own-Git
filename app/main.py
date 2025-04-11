import sys
import os
import zlib
import hashlib


def main():
    # You can use print statements as follows for debugging, they'll be visible when running tests.
    print("Logs from your program will appear here!", file=sys.stderr)


    command = sys.argv[1]
    if command == "init":
        os.mkdir(".git")
        os.mkdir(".git/objects")
        os.mkdir(".git/refs")
        with open(".git/HEAD", "w") as f:
            f.write("ref: refs/heads/main\n")
        print("Initialized git directory")

    elif command == "cat-file" and sys.argv[2] == "-p":
        obj_name = sys.argv[3]
        with open(f".git/objects/{obj_name[:2]}/{obj_name[2:]}", "rb") as f:
            raw = zlib.decompress(f.read())
            header, content = raw.split(b"\0", maxsplit=1)
            print(content.decode(encoding="utf-8"), end="")

    elif command == "hash-object": # Changed this line
        if sys.argv[2] == "-w":
            file_path = sys.argv[3]
            with open(file_path, "rb") as f:
                content = f.read()
            header = f"blob {len(content)}\0".encode()
            store = header + content
            sha1_hash = hashlib.sha1(store).hexdigest()
            obj_dir = f".git/objects/{sha1_hash[:2]}"
            obj_path = f"{obj_dir}/{sha1_hash[2:]}"
            if not os.path.exists(obj_dir):
                os.makedirs(obj_dir)
            with open(obj_path, "wb") as f:
                f.write(zlib.compress(store))
            print(sha1_hash)
        else:
            raise RuntimeError(f"Unknown option for hash-object: #{sys.argv[2]}") # More specific error

    else:
        raise RuntimeError(f"Unknown command #{command}")


if __name__ == "__main__":
    main()