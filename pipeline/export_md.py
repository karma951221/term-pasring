"""(선택) 항목별 markdown: out/md/<상품>/<번호>_<항목명>.md
python pipeline/export_md.py [상품명 일부]"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT, WEB, ITEMS


def safe(s, n=60):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", s or "").strip("_")[:n]


def block_md(b):
    t = b["t"]
    if t == "표":
        return "[표]"
    if t == "그림":
        return "[그림]"
    if t == "박스":
        return f"[박스 {b.get('title','')}]".replace("  ", " ")
    if t == "항":
        return f"{b.get('n','')} {b['text']}"
    if t == "호":
        n = b.get("n", "")
        return f"{n if n.endswith('.') else n} {b['text']}"
    if t == "목":
        return f"  - {b.get('n','')} {b['text']}"
    if t in ("제목", "절"):
        return f"# {b['text']}"
    if t == "관":
        return f"### {b['text']}"
    return b["text"]


def main(sub=None):
    idx = json.load(open(os.path.join(WEB, "index.json"), encoding="utf-8"))
    names = {p["id"]: p["name"] for p in idx["products"]}
    n = 0
    for row in idx["items"]:
        prod = names.get(row["bundle"] and next((p["id"] for p in idx["products"] if p["type"] == "독립특약" and p["name"] == row["bundle"]), None) or row["src"], row["src"])
        if sub and sub not in prod:
            continue
        it = json.load(open(os.path.join(ITEMS, row["id"] + ".json"), encoding="utf-8"))
        L = [block_md(b) for b in it["head"]]
        for a in it["arts"]:
            L.append(f"## {a['text']}")
            L += [block_md(b) for b in a["blocks"]]
        d = os.path.join(OUT, "md", safe(prod))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{safe(str(row.get('no') or ''), 10)}_{safe(row['name'])}.md"), "w", encoding="utf-8") as f:
            f.write("\n\n".join(L) + "\n")
        n += 1
    print(f"md {n}개")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
