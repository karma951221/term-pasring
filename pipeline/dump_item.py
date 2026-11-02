"""사람이 읽는 덤프 (매뉴얼 §7): python pipeline/dump_item.py <item_id> [줄수] [자를길이]"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ITEMS


def fmt(b, w):
    tag = b["t"]
    if b["t"] in ("항", "호", "목"):
        tag += str(b.get("n", ""))
    elif b["t"] == "박스":
        tag += ":" + b.get("label", "") + ("·무테" if b.get("noborder") else "") + (f" {b.get('title','')[:20]}" if b.get("title") else "")
    return f"[{tag}] p{b['p']}c{b['c']}y{int(b['y0'])} {b.get('text','')[:w]}"


def dump(iid, n=40, w=150):
    it = json.load(open(os.path.join(ITEMS, iid + ".json"), encoding="utf-8"))
    out = [f"# {it['name']} [{it['kind']}] sec={it.get('section')} pages={it['pages']}" + (f" shared={len(it['shared'])}" if it.get("shared") else "")]
    for b in it["head"]:
        out.append(fmt(b, w))
    for a in it["arts"]:
        out.append(f"== {a['text'][:80]}  gwan={(a['gwan'] or '')[:20]}  p{a['p']}c{a['c']}y{int(a['y0'])}")
        for b in a["blocks"]:
            out.append("  " + fmt(b, w))
    if len(out) > n:
        out = out[:n] + [f"... (+{len(out)-n}줄)"]
    print("\n".join(out))


if __name__ == "__main__":
    dump(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 40, int(sys.argv[3]) if len(sys.argv) > 3 else 150)
