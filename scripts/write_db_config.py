"""writes into docs/db-config.json the size of the docs/horses.db file
run this any time you import more horses before you commit and push."""

import json, time
from pathlib import Path

db = Path(__file__).resolve().parent.parent / "docs" / "horses.db"
if not db.is_file():
    raise SystemExit("DB Not found")

size = db.stat().st_size
config = {
        "serverMode":           "chunked",
        "urlPrefix":            "horses.db?part=",
        "suffixLength":         1,
        "serverChunkSize":      size,
        "databaseLengthBytes":  size,
        "requestChunkSize":     4096,
        "cacheBust":            str(int(time.time())),
        }
(db.parent / "db-config.json").write_text(json.dumps(config, indent=2))
print(f"db-config.json written. Used horses.db; {size:,} bytes")
