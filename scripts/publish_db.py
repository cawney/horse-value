"""Gets the file size of horses.db and puts it in docs/db-config.json"""

import json, sqlite3, time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
scr = BASE_DIR / "horses.db"
out = BASE_DIR / "docs" / "horses.db.000"

out.unline(missing_ok=True)
conn = sqlite3.connect(src)
conn.execute(f"VACUUM INTO '{out}'")
page_size = conn.execute("PRAGMA page_size").fetchone()[0]
conn.close()

config = {
        "severMode":        "chunked",
        "urlPrefix":        "horses.db.",
        "suffixLength":     3,
        "serverChunkSize":  out.stat().st_size,
        "databaseLengthBytes":  out.stat.().st_size,
        "requestChunkSize":     page_size,
        "cacheBust":            str(int(time.time())),
        }

(BASE_DIR / "docs" / "db-config.json").write_text(json.dumps(config, indent=2))
print(f"Wrote {out.name} ({out.stat().st_size:,} bytes) and db-config.json")

