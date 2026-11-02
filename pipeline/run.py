"""실행기: plan · extract · index (매뉴얼 §3.4, §6).

python pipeline/run.py plan
python pipeline/run.py extract [--jobs N] [--batch K] [--only 이름일부]
python pipeline/run.py index
"""
import argparse, collections, json, os, re, sys, time, traceback
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (fitz, SRC_DIR, OUT, WORK, WEB, ITEMS, PLAN, norm_key, match_key, pdf_id, bundle_id,
                    product_name, is_pet, kind_label, group_name, nchars, list_pdfs)
import toc as T
import extract as X


def jdump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def jload(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------- plan ----------------

def plan_one(fname):
    path = os.path.join(SRC_DIR, fname)
    doc = fitz.open(path)
    r = T.read_toc(doc)
    res = {"file": fname, "pid": pdf_id(fname), "name": product_name(fname), "pages": doc.page_count}
    if r is None:
        res["error"] = "목차없음"
        return res
    res["toc"] = r["toc"]
    res["offset"] = T.page_offset(doc)
    res["lines"] = r["lines"]
    return res


def _finish_plan(res, cipher, page_count):
    lines = res.pop("lines")
    for ln in lines:
        if T.is_garbled(ln["text"]) and cipher:
            ln["text"] = T.apply_cipher(ln["text"], cipher)
    res["cipher_size"] = len(cipher)
    res["garbled_left"] = sum(1 for ln in lines if T.is_garbled(ln["text"]))
    mism = []
    for ln in lines:
        if ln.get("pp") is not None and ln.get("link") is not None and ln["pp"] + res["offset"] != ln["link"]:
            mism.append({"anchor": ln["text"][:60], "pp": ln["pp"], "link": ln["link"]})
    res["link_mismatch"] = mism
    res["nopage"] = [ln["text"][:60] for ln in lines if ln.get("nopage")][:20]
    items, bounds, boxes = T.build_items(lines, res["offset"], page_count)
    res["items"], res["bounds"], res["boxes"] = items, bounds, boxes
    return res


def cmd_plan(args):
    files = list_pdfs()
    if args.only:
        files = [f for f in files if args.only in f]
    t0 = time.time()
    with Pool(args.jobs) as pool:
        raws = pool.map(plan_one, files)
    # 깨진 목차: 자체 치환표 + 전역 치환표
    normal_by_len = collections.defaultdict(set)
    for r in raws:
        for ln in r.get("lines", []):
            if not ln.get("hdr") and not T.is_garbled(ln["text"]):
                normal_by_len[len(re.sub(r"\s+", "", ln["text"]))].add(re.sub(r"\s+", "", ln["text"]))
    results = {}
    for r in raws:
        if "error" in r:
            results[r["file"]] = r
            continue
        garbled = [ln["text"] for ln in r["lines"] if T.is_garbled(ln["text"])]
        cipher = {}
        if garbled:
            dx = X.Doc(os.path.join(SRC_DIR, r["file"]))
            selfc = T.learn_self_cipher(dx.doc, r["lines"], r["offset"], dx.analyze)
            gv = T.global_votes(garbled, normal_by_len)
            votes = collections.defaultdict(collections.Counter)
            for k, v in gv.items():
                votes[k].update(v)
            for k, v in selfc.items():
                votes[k][v] += 3
            cipher = {k: v.most_common(1)[0][0] for k, v in votes.items()}
        results[r["file"]] = _finish_plan(r, cipher, r["pages"])
    # 독립특약 소유자: 쪽수가 가장 적은 PDF
    holders = collections.defaultdict(list)
    names = {}
    for f, r in results.items():
        for it in r.get("items", []):
            if it.get("bundle"):
                k = norm_key(it["bundle"])
                names[k] = it["bundle"]
                if f not in [h[1] for h in holders[k]]:
                    holders[k].append((r["pages"], f))
    owner = {k: sorted(v)[0][1] for k, v in holders.items()}
    plan = {"results": results, "bundle_owner": owner, "bundle_names": names}
    jdump(plan, PLAN)
    # 보고: 구분별 개수
    cnt = collections.Counter()
    for r in results.values():
        for it in r.get("items", []):
            cnt[("독립특약 " if it.get("bundle") else "") + it["kind"]] += 1
    print(f"PDF {len(results)} · 독립특약 묶음 {len(owner)} · {time.time()-t0:.0f}s")
    print("구분별(참조 포함):", dict(cnt))
    print("목차없음:", [f for f, r in results.items() if "error" in r])
    print("깨진 목차 PDF:", sum(1 for r in results.values() if r.get("cipher_size")),
          "· 남은 깨진 줄:", sum(r.get("garbled_left", 0) for r in results.values()),
          "· 링크 불일치:", sum(len(r.get("link_mismatch", [])) for r in results.values()))


# ---------------- extract ----------------

def _has_body(dx, start, end):
    for typ, pos, el, a in X._elements(dx, start, end):
        if typ == "R":
            return True
        if el["size"] <= a["body_size"] + 0.2 and nchars(el["text"]) > 0 and not re.match(r"^\s*\d{1,3}(?:-\d{1,2})?\s*\.", el["text"]) :
            return True
        if el["size"] <= a["body_size"] + 0.2 and nchars(el["text"]) > 0:
            return True
    return False


def extract_one(fname):
    plan = jload(PLAN)
    r = plan["results"][fname]
    owner = plan["bundle_owner"]
    pid = r["pid"]
    wpath = os.path.join(WORK, pid + ".json")
    if os.path.exists(wpath):
        return fname, "skip"
    t0 = time.time()
    dx = X.Doc(os.path.join(SRC_DIR, fname), pet=is_pet(r["name"]))
    npages = dx.doc.page_count
    issues = []

    def owned(it):
        return not it.get("bundle") or owner.get(norm_key(it["bundle"])) == fname

    # 경계 위치
    bpos = []
    for b in r["bounds"]:
        if b.get("bundle") and not b.get("hdr") and owner.get(norm_key(b["bundle"])) != fname:
            continue
        if b["page"] is None:
            continue
        pos = X.locate(dx, b["page"], b["anchor"], b["kind"])
        if b.get("hdr"):
            if not X.cover_check(dx, b["page"], b["anchor"]):
                issues.append({"type": "표지불일치", "file": fname, "anchor": b["anchor"][:60], "page": b["page"]})
        if pos is None:
            pos = (b["page"], 0, 0.0)
        bpos.append(tuple(pos))
    bpos = sorted(set(bpos))
    # 항목 id
    seq_main = 0
    bseq = collections.Counter()
    recs = []
    for it in r["items"]:
        if it.get("bundle"):
            bk = norm_key(it["bundle"])
            bseq[bk] += 1
            iid = f"{bundle_id(bk)}-{bseq[bk]}"
        else:
            iid = f"{pid}-{seq_main}"
            seq_main += 1
        rec = {"id": iid, "kind": it["kind"], "label": kind_label(it["kind"], it.get("bundle")), "name": it["name"],
               "section": it.get("section"), "bundle": it.get("bundle"), "no": it.get("no"),
               "anchor": it["anchor"], "owned": owned(it), "page": it.get("page")}
        recs.append(rec)
    work_items = [x for x in recs if x["owned"]]
    # 시작 위치
    for rec in work_items:
        pos = X.locate(dx, rec["page"], rec["anchor"], "item") if rec["page"] is not None else None
        if pos is None:
            pos = X.locate(dx, rec["page"], rec["anchor"], "other") if rec["page"] is not None else None
            if pos is None or True:
                pass
        if pos is None:
            issues.append({"type": "시작위치못찾음", "file": fname, "id": rec["id"], "name": rec["name"][:60], "page": rec["page"]})
            pos = (rec["page"] if rec["page"] is not None else 0, 0, 0.0)
        rec["start"] = tuple(pos)
    # 범위
    def next_bound(p):
        lim = (p[0], p[1], p[2] + 2)
        for b in bpos:
            if b > lim:
                return b
        return (npages, 0, 0.0)
    for rec in work_items:
        s = rec["start"]
        e = next_bound(s)
        k = 0
        while k < 12 and e[0] < npages and not _has_body(dx, s, e):
            e = next_bound(e)
            k += 1
        rec["end"] = e
    # 공유 약관
    groups, i = [], 0
    while i < len(work_items):
        j = i
        while (j + 1 < len(work_items) and work_items[j + 1]["end"] == work_items[i]["end"]
               and work_items[j + 1]["start"] > work_items[j]["start"]):
            j += 1
        groups.append(work_items[i:j + 1])
        i = j + 1
    stats = collections.Counter()
    for g in groups:
        view_start = g[0]["start"]
        cache = None
        for rec in g:
            shared = len(g) > 1
            if cache is None or not shared:
                blocks, st = X.build_blocks(dx, view_start if shared else rec["start"], rec["end"])
                cache = (blocks, st)
            blocks, st = json.loads(json.dumps(cache[0])), cache[1]
            removed = 0
            if shared:
                first_art = next((k for k, b in enumerate(blocks) if b["t"] == "조"), len(blocks))
                tidx = [k for k in range(first_art) if blocks[k]["t"] == "제목"]
                if tidx:
                    removed = sum(nchars(blocks[k]["text"]) for k in tidx) - nchars(rec["anchor"])
                    blocks[tidx[0]]["text"] = rec["anchor"]
                    for k in reversed(tidx[1:]):
                        del blocks[k]
            head, arts = X.nest(blocks)
            if T.is_garbled(rec["name"]) and not shared:
                t0b = next((b for b in head if b["t"] == "제목"), None)
                if t0b:
                    rec["name"] = re.sub(r"^\s*\d{1,3}(?:-\d{1,2})?\s*\.\s*", "", t0b["text"])
            ng, warn, ist = X.qa_item(rec, head, arts, st["orig"], removed)
            pages = sorted({b["p"] for b in head} | {a["p"] for a in arts} | {b["p"] for a in arts for b in a["blocks"]})
            item = {"id": rec["id"], "kind": rec["kind"], "label": rec["label"], "name": rec["name"],
                    "section": rec["section"], "bundle": rec["bundle"],
                    "owner": rec["bundle"] or r["name"], "no": rec["no"],
                    "pages": [pages[0], pages[-1]] if pages else [rec["start"][0], rec["start"][0]],
                    "start": list(rec["start"]), "end": list(rec["end"]),
                    "head": head, "arts": arts}
            if shared:
                item["shared"] = [x["anchor"] for x in g]
            jdump(item, os.path.join(ITEMS, rec["id"] + ".json"))
            rec.update({"pages": item["pages"], "stats": ist, "ng": ng, "warn": warn, "orig": st["orig"],
                        "shared": len(g) if shared else 0})
            for k2, v in ist.items():
                stats[k2] += v
            for t, d in ng:
                issues.append({"type": t, "file": fname, "id": rec["id"], "name": rec["name"][:60], "detail": d})
            for t, d in warn:
                issues.append({"type": t, "file": fname, "id": rec["id"], "name": rec["name"][:60], "detail": d})
    for rec in recs:
        rec.pop("anchor", None)
        if "start" in rec:
            rec["start"] = list(rec["start"]); rec["end"] = list(rec["end"])
    for m in r.get("link_mismatch", []):
        issues.append({"type": "목차본문불일치", "file": fname, "name": m["anchor"], "detail": f"쪽 {m['pp']} · 링크 {m['link']}"})
    out = {"file": fname, "pid": pid, "name": r["name"], "pages": npages, "pet": is_pet(r["name"]),
           "items": recs, "issues": issues, "stats": dict(stats), "secs": round(time.time() - t0, 1)}
    jdump(out, os.path.join(WORK, pid + ".json"))
    return fname, f"ok {len(work_items)}건 {out['secs']}s"


def _safe(fname):
    try:
        return extract_one(fname)
    except Exception:
        os.makedirs(WORK, exist_ok=True)
        with open(os.path.join(WORK, "failed.log"), "a", encoding="utf-8") as f:
            f.write(f"== {fname}\n{traceback.format_exc()}\n")
        return fname, "FAILED"


def pending_files(plan, only=None):
    res = plan["results"]
    files = [f for f in res if "error" not in res[f]]
    if only:
        files = [f for f in files if only in f]
    files = [f for f in files if not os.path.exists(os.path.join(WORK, res[f]["pid"] + ".json"))]
    return sorted(files, key=lambda f: res[f]["pages"])


def cmd_extract(args):
    plan = jload(PLAN)
    files = pending_files(plan, args.only)
    if args.batch:
        files = files[:args.batch]
    files.sort(key=lambda f: -plan["results"][f]["pages"])  # 큰 PDF부터
    t0 = time.time()
    print(f"처리 대상 {len(files)}개")
    if args.jobs > 1 and len(files) > 1:
        with Pool(args.jobs, maxtasksperchild=1) as pool:
            for f, msg in pool.imap_unordered(_safe, files):
                print(f"  {msg:>18}  {f[:60]}", flush=True)
    else:
        for f in files:
            f, msg = _safe(f)
            print(f"  {msg:>18}  {f[:60]}", flush=True)
    left = len(pending_files(plan))
    print(f"완료 {time.time()-t0:.0f}s · 남은 PDF {left}개")


# ---------------- index ----------------

def cmd_index(args):
    plan = jload(PLAN)
    owner = plan["bundle_owner"]
    names = plan["bundle_names"]
    products, items, issues = [], [], []
    bhosts = collections.defaultdict(list)
    bitems = collections.defaultdict(list)
    for f, r in sorted(plan["results"].items(), key=lambda x: x[1]["name"]):
        wp = os.path.join(WORK, r.get("pid", "") + ".json")
        if not os.path.exists(wp):
            continue
        w = jload(wp)
        issues.extend(w["issues"])
        own_ids, bset = [], []
        for rec in w["items"]:
            if rec["bundle"]:
                bk = norm_key(rec["bundle"])
                bid = bundle_id(bk)
                if bid not in bset:
                    bset.append(bid)
                if w["pid"] not in bhosts[bid]:
                    bhosts[bid].append(w["pid"])
            else:
                own_ids.append(rec["id"])
            if not rec["owned"] or "stats" not in rec:
                continue
            gname, gkey = group_name(rec["name"])
            row = {"id": rec["id"], "kind": rec["kind"], "label": rec["label"], "name": rec["name"],
                   "section": rec["section"], "bundle": rec["bundle"], "key": norm_key(rec["name"]),
                   "pages": rec["pages"], "arts": rec["stats"].get("arts", 0), "no": rec["no"],
                   "gkey": gkey, "gname": gname, "src": w["pid"]}
            items.append(row)
            if rec["bundle"]:
                bitems[bundle_id(norm_key(rec["bundle"]))].append(rec["id"])
        products.append({"id": w["pid"], "type": "주계약", "name": w["name"], "file": f,
                         "key": norm_key(w["name"]), "pages": w["pages"], "items": own_ids, "bundles": bset})
    for bk, f in owner.items():
        bid = bundle_id(bk)
        if bid not in bhosts:
            continue
        products.append({"id": bid, "type": "독립특약", "name": names[bk], "key": bk,
                         "owner": plan["results"][f]["pid"], "items": bitems.get(bid, []), "hosts": bhosts[bid]})
    jdump({"products": products, "items": items}, os.path.join(WEB, "index.json"))
    jdump(issues, os.path.join(WORK, "issues.json"))
    print(f"상품 {sum(1 for p in products if p['type']=='주계약')} · 독립특약 {sum(1 for p in products if p['type']=='독립특약')} · 항목 {len(items)} · 이슈 {len(issues)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["plan", "extract", "index"])
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--batch", type=int, default=0)
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    {"plan": cmd_plan, "extract": cmd_extract, "index": cmd_index}[args.cmd](args)


if __name__ == "__main__":
    main()
