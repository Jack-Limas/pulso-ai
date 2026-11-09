"""Generates the gRPC and Connect stubs from the .proto contract into src/pulso."""

import os
import sys
from pathlib import Path

from grpc_tools import protoc

ROOT = Path(__file__).resolve().parent.parent
PROTO_DIR = ROOT / "proto"
OUT_DIR = ROOT / "src"


def main() -> None:
    proto_files = [str(path) for path in PROTO_DIR.rglob("*.proto")]
    # protoc looks plugins up on PATH, and virtual environments are not always activated.
    scripts_dir = Path(sys.executable).parent
    os.environ["PATH"] = f"{scripts_dir}{os.pathsep}{os.environ['PATH']}"
    exit_code = protoc.main(
        [
            "grpc_tools.protoc",
            f"-I{PROTO_DIR}",
            f"--python_out={OUT_DIR}",
            f"--pyi_out={OUT_DIR}",
            f"--grpc_python_out={OUT_DIR}",
            f"--connect-python_out={OUT_DIR}",
            *proto_files,
        ]
    )
    if exit_code != 0:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
