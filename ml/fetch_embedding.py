"""Explicit offline fetch of the reviewed MiniLM embedding model. Never called on startup."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True, help="Full model repository commit SHA")
    parser.add_argument("--output", default="artifacts/minilm")
    args = parser.parse_args()
    if len(args.revision) != 40 or any(c not in "0123456789abcdef" for c in args.revision):
        raise ValueError("Use a full lowercase model commit SHA")
    from huggingface_hub import snapshot_download

    path = Path(
        snapshot_download(
            "sentence-transformers/all-MiniLM-L6-v2",
            revision=args.revision,
            local_dir=args.output,
            ignore_patterns=["onnx/*", "openvino/*", "*.h5", "*.msgpack"],
        )
    )
    manifest = {
        str(file.relative_to(path)): hashlib.sha256(file.read_bytes()).hexdigest()
        for file in sorted(path.rglob("*"))
        if file.is_file() and ".cache" not in file.parts
    }
    (path / "joldinaw-manifest.json").write_text(
        json.dumps({"revision": args.revision, "files": manifest}, indent=2), encoding="utf-8"
    )
    print("Prepared local model; set EMBEDDING_PATH and EMBEDDING_REVISION explicitly")


if __name__ == "__main__":
    main()
