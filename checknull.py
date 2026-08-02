from pathlib import Path

for file in Path(".").rglob("*.py"):
    data = file.read_bytes()
    if b"\x00" in data:
        print(f"Arquivo com null bytes: {file}")