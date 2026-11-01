"""Read-only evidence collection for the frozen unofficial Track 2 roster.

Fetches public documentation as inert text. Does not execute competitor code.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/competition-2026"
HEADERS = {"User-Agent": "Mozilla/5.0 (public hackathon documentation review)", "Accept": "text/plain,text/html,application/json"}


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.text.append(data.strip())


def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=25) as response:
                data = response.read(2_000_001)
                if len(data) > 2_000_000:
                    raise ValueError("Documentation exceeds 2MB limit")
                return data, response.geturl()
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503) or attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("Fetch exhausted")


def collect(name):
    folder = OUT / "repositories" / name.replace("/", "__")
    folder.mkdir(parents=True, exist_ok=True)
    record_path = folder / "receipt.json"
    if record_path.exists():
        return json.loads(record_path.read_text(encoding="utf-8"))
    record = {"repository": name, "collected_utc": datetime.now(timezone.utc).isoformat(), "attempts": [], "status": "unavailable"}
    for filename in ("README.md", "readme.md", "README.MD", "Readme.md", "README.rst", "README"):
        url = f"https://raw.githubusercontent.com/{name}/HEAD/{filename}"
        try:
            data, final_url = get(url)
            text = data.decode("utf-8", errors="replace")
            (folder / "README.source.txt").write_text(text, encoding="utf-8")
            record.update(status="readme_fetched", source_url=final_url, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), filename=filename)
            break
        except Exception as error:
            record["attempts"].append({"url": url, "error": str(error)[:180]})
            if isinstance(error, urllib.error.HTTPError) and error.code in (403, 429):
                break
    if record["status"] == "unavailable":
        try:
            data, final_url = get(f"https://github.com/{name}")
            (folder / "repository.html").write_bytes(data)
            parser = VisibleText()
            parser.feed(data.decode("utf-8", errors="replace"))
            (folder / "repository-visible.txt").write_text("\n".join(parser.text), encoding="utf-8")
            record.update(status="repository_page_only", source_url=final_url, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        except Exception as error:
            record["attempts"].append({"url": f"https://github.com/{name}", "error": str(error)[:180]})
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def main():
    all_rows = json.loads((OUT / "directory.json").read_text(encoding="utf-8"))
    rows = [r for r in all_rows if "push the frontier" in r["track"].lower()]
    assert len(rows) == 173, f"Expected the discussed 173-entry snapshot, got {len(rows)}"
    (OUT / "roster.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    primary = {r["full_name"] for r in rows}
    linked = {l["full_name"] for r in rows for l in r.get("linked_repos", [])}
    names = sorted(primary | linked)
    records = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        tasks = {executor.submit(collect, name): name for name in names}
        for future in as_completed(tasks):
            result = future.result()
            records.append(result)
            if len(records) % 20 == 0 or result["status"] != "readme_fetched":
                print(f'{len(records)}/{len(names)} {result["repository"]}: {result["status"]}', flush=True)
    coverage = {"collected_utc": datetime.now(timezone.utc).isoformat(), "source": "https://artifacts.watt-mind.com/meta-hackathon-2026/projects.json", "directory_sha256": hashlib.sha256((OUT / "directory.json").read_bytes()).hexdigest(), "directory_entries": len(all_rows), "track_2_entries": len(rows), "distinct_primary_repositories": len(primary), "additional_linked_repositories": len(linked-primary), "records": sorted(records, key=lambda r: r["repository"]), "scope": "Public documentation retrieval only; no competitor code executed and no leaderboard scores treated as official judging."}
    (OUT / "collection.json").write_text(json.dumps(coverage, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in coverage.items() if k != "records"}, indent=2))


if __name__ == "__main__":
    main()
