"""Bounded, source-linked documentation excerpts for each frozen roster entry."""
import argparse
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent / "competition-2026"


def clean(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    return re.sub(r"\s+", " ", s).strip(" #|*-`")


def digest(row, number):
    folder = OUT / "repositories" / row["full_name"].replace("/", "__")
    receipt = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
    path = folder / "README.source.txt"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = text.splitlines()
    headings = [clean(x) for x in lines if x.startswith("#")]
    paragraphs = [clean(x) for x in lines if len(clean(x)) > 65 and not x.startswith(("|", "```", "    ")) and not any(y in x.lower() for y in ("badge", "shields.io", "pip install", "npm install", "git clone", "copyright", "<img", "<svg", "!["))]
    intro = " ".join(paragraphs[:2])[:420]
    candidates = []
    pattern = re.compile(r"held.out|baseline|benchmark|accuracy|pass.rate|ablation|evaluat|measured|real.hardware|physical|fine.tun|trained|rl |reinforcement|honest|limitation|not.yet|not.claim|recorded|offline|mock|test.*pass|\d+\s*(tests|cases|tasks|trials|runs|%|mm)", re.I)
    for line_number, line in enumerate(lines, 1):
        plain = clean(line)
        if len(plain) > 45 and pattern.search(plain) and not plain.startswith(("pip install", "npm ", "pytest ", "python -", "cd ")):
            weight = sum(bool(re.search(p, plain, re.I)) for p in (r"held.out|baseline|ablation", r"\d", r"accuracy|pass.rate|benchmark|measured", r"not.claim|limitation|mock|offline"))
            candidates.append((weight, line_number, plain[:280]))
    selected = sorted(sorted(candidates, key=lambda x: -x[0])[:3], key=lambda x: x[1])
    return {"index": number, "repository": row["full_name"], "url": row["html_url"], "directory_summary": row["summary"], "documentation_status": receipt["status"], "documentation_url": receipt.get("source_url"), "readme_lines": len(lines), "intro_excerpt": intro, "headings": headings[:14], "evidence_excerpts": [{"line": n, "text": s} for _, n, s in selected], "directory_reported_signals": {k: row[k] for k in ("has_tests", "has_ci", "has_live_deploy", "has_video_demo", "open_weights_tuning", "meta_api_verified")}, "qualification": "Excerpts and repository claims; not independently reproduced. Directory flags are unverified third-party signals."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=173)
    args = parser.parse_args()
    rows = json.loads((OUT / "roster.json").read_text())
    digests = [digest(row, i) for i, row in enumerate(rows, 1)]
    (OUT / "documentation-digests.json").write_text(json.dumps(digests, indent=2, ensure_ascii=False), encoding="utf-8")
    for r in digests[args.start-1:args.end]:
        print(f'\n{r["index"]:03} {r["repository"]} [{r["documentation_status"]}, {r["readme_lines"]} lines]')
        print('INTRO:', r['intro_excerpt'][:340])
        print('SECTIONS:', ' / '.join(r['headings'][:8])[:190])
        for e in r['evidence_excerpts'][:2]:
            print(f'L{e["line"]}: {e["text"][:210]}')


if __name__ == "__main__":
    main()
