"""Prepare local Bilibili SDK build inputs from the caller's game APK/init JSON.

Only the three named arm64 libraries and the SDK app key are copied. Neither
account tokens nor phone numbers are copied into the Android project.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--init-json", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    init = json.loads(args.init_json.read_text(encoding="utf-8"))
    extend = init.get("EXTEND", init)
    if isinstance(extend, str):
        extend = json.loads(extend)
    key = extend["APP_KEY"]
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9]{32}", key):
        raise ValueError("Expected a 32-character SDK APP_KEY")
    libraries = ["libcrypto_1_1.so", "libssl_1_1.so", "libcustom_rules.so"]
    with ZipFile(args.apk) as apk:
        contents = {name: apk.read("lib/arm64-v8a/" + name) for name in libraries}
    destination = root / "app/src/main/jniLibs/arm64-v8a"
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in contents.items():
        (destination / name).write_bytes(content)
        print(name, "SHA256", hashlib.sha256(content).hexdigest())
    (root / "bili.properties").write_text("appKey=" + key + "\n", encoding="ascii")
    print("Prepared local SDK inputs; no account credentials were copied.")


if __name__ == "__main__":
    main()
