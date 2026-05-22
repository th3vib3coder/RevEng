from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_MAX_READ_BYTES = 64 * 1024 * 1024


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def hash_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    total = len(data)
    return -sum((count / total) * math.log2(count / total) for count in counts if count)


def ascii_strings(data: bytes, min_len: int = 4, limit: int = 200) -> list[str]:
    strings: list[str] = []
    current = bytearray()
    for byte in data:
        if 32 <= byte <= 126:
            current.append(byte)
        else:
            if len(current) >= min_len:
                strings.append(current.decode("ascii", errors="ignore"))
                if len(strings) >= limit:
                    break
            current.clear()
    if len(strings) < limit and len(current) >= min_len:
        strings.append(current.decode("ascii", errors="ignore"))
    return strings


def file_type_guess(data: bytes) -> str:
    if data.startswith(b"MZ"):
        return "PE/DOS MZ"
    if data.startswith(b"\x7fELF"):
        return "ELF"
    if data.startswith((b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe")):
        return "Mach-O/Fat Mach-O"
    if data.startswith(b"PK\x03\x04"):
        return "ZIP/APK/JAR/AAR"
    return "unknown"


def run_optional_tool(command: list[str], timeout_s: int = 10) -> dict[str, Any]:
    tool = command[0]
    if shutil.which(tool) is None:
        return {"available": False, "stdout": "", "stderr": ""}
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout_s, check=False)
        return {
            "available": True,
            "returncode": result.returncode,
            "stdout": result.stdout[:8000],
            "stderr": result.stderr[:4000],
        }
    except Exception as exc:
        return {"available": True, "error": str(exc), "stdout": "", "stderr": ""}


def triage(path: Path, max_read_bytes: int = DEFAULT_MAX_READ_BYTES) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise SystemExit(f"not a file: {path}")
    size_bytes = path.stat().st_size
    with path.open("rb") as handle:
        data = handle.read(max_read_bytes)
    bytes_analyzed = len(data)
    chunk_size = 4096
    chunks = [
        {"offset": offset, "entropy": round(entropy(data[offset : offset + chunk_size]), 4)}
        for offset in range(0, min(len(data), chunk_size * 32), chunk_size)
    ]
    limitations = ["Static triage only; the sample was not executed."]
    if bytes_analyzed < size_bytes:
        limitations.append(
            f"Only the first {bytes_analyzed} of {size_bytes} bytes were read for entropy/strings/type; "
            "hashes still cover the full file."
        )
    return {
        "sample": {"path": str(path), "name": path.name},
        "hashes": {
            "md5": hash_file(path, "md5"),
            "sha1": hash_file(path, "sha1"),
            "sha256": hash_file(path, "sha256"),
        },
        "file_type": file_type_guess(data[:16]),
        "size_bytes": size_bytes,
        "bytes_analyzed": bytes_analyzed,
        "entropy": {"overall": round(entropy(data), 4), "chunks": chunks},
        "strings_summary": {"ascii_preview": ascii_strings(data)},
        "tool_outputs": {
            "file": run_optional_tool(["file", str(path)]),
            "objdump_header": run_optional_tool(["objdump", "-h", str(path)]),
            "readelf_header": run_optional_tool(["readelf", "-h", str(path)]),
        },
        "limitations": limitations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Static binary triage")
    parser.add_argument("sample")
    parser.add_argument("--json-out", required=True)
    parser.add_argument(
        "--max-read-bytes",
        type=positive_int,
        default=DEFAULT_MAX_READ_BYTES,
        help="Maximum bytes read into memory for entropy/strings/type; hashes always stream the full file",
    )
    args = parser.parse_args()

    payload = triage(Path(args.sample), max_read_bytes=args.max_read_bytes)
    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
