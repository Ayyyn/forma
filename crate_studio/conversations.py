"""Local durable project conversations, independent of CAD revisions and receipts."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3


class Conversations:
    def __init__(self, path, documents):
        self.path, self.documents = Path(path), Path(documents)

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=20)
        try:
            with db:
                db.execute(
                    "CREATE TABLE IF NOT EXISTS messages (seq INTEGER PRIMARY KEY, root TEXT NOT NULL, run TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, document TEXT NOT NULL, created TEXT NOT NULL, UNIQUE(root, run, role))"
                )
                db.execute(
                    "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, value TEXT NOT NULL)"
                )
                yield db
        finally:
            db.close()

    def save_job(self, job):
        value = {
            key: job[key]
            for key in (
                "id",
                "document_id",
                "status",
                "stage",
                "agent_mode",
                "applied_id",
                "error",
            )
            if key in job
        }
        with self.connection() as db:
            db.execute(
                "INSERT OR REPLACE INTO jobs(id,value) VALUES(?,?)",
                (job["id"], json.dumps(value)),
            )

    def read_job(self, job_id):
        with self.connection() as db:
            row = db.execute("SELECT value FROM jobs WHERE id=?", (job_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def root(self, document_id):
        seen = set()
        while document_id:
            if (
                not re.fullmatch(r"cad-[a-f0-9]{12}", document_id)
                or document_id in seen
                or len(seen) >= 1000
            ):
                raise ValueError("Invalid conversation document lineage")
            seen.add(document_id)
            record = json.loads(
                (self.documents / (document_id + ".json")).read_text(encoding="utf-8")
            )
            if not record.get("parent_id"):
                return document_id
            document_id = record["parent_id"]
        raise ValueError("Missing conversation project")

    def read(self, document_id):
        root = self.root(document_id)
        with self.connection() as db:
            rows = db.execute(
                "SELECT run,role,content,document,created FROM messages WHERE root=? ORDER BY seq",
                (root,),
            ).fetchall()
        return {
            "project_id": root,
            "messages": [
                {
                    "run_id": r[0],
                    "role": r[1],
                    **json.loads(r[2]),
                    "document_id": r[3],
                    "created_at": r[4],
                }
                for r in rows
            ],
            "storage": "Local project database; retained across reloads and server restarts",
        }

    def append(self, document_id, run_id, role, content):
        if role not in ("user", "assistant") or not isinstance(content, dict):
            raise ValueError("Invalid conversation message")
        root = self.root(document_id)
        with self.connection() as db:
            db.execute(
                "INSERT OR IGNORE INTO messages(root,run,role,content,document,created) VALUES(?,?,?,?,?,?)",
                (
                    root,
                    run_id,
                    role,
                    json.dumps(content, ensure_ascii=False, allow_nan=False),
                    document_id,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def context(self, document_id):
        rows = self.read(document_id)["messages"]
        completed = {r["run_id"] for r in rows if r["role"] == "assistant"}
        result, size = [], 0
        for row in reversed(rows):
            if row["run_id"] not in completed:
                continue
            content = row.get("text", "")
            if row.get("questions"):
                content += "\n" + "\n".join(row["questions"])
            if len(result) >= 20 or size + len(content) > 24000:
                break
            result.append({"role": row["role"], "content": content})
            size += len(content)
        return list(reversed(result))
