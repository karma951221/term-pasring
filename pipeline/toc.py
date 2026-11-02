"""① 목차 읽기 + ② 항목 리스트업 (매뉴얼 §2, §3.1~3.4)."""
import collections, re
from common import (fitz, norm_key, match_key, _DOTS, _NUM_ITEM, _DAEBUN, _GARBLED, _INFO,
                    _GWAN, _JEOL, ROMAN)


def find_toc(doc):
    for i in range(min(200, doc.page_count)):
        t = doc[i].get_text()
        if t.count("....") > 20 and re.search(r"목\s*차", t[:200]):
            j = i
            while j + 1 < doc.page_count and doc[j + 1].get_text().count("....") >= 5:
                j += 1
            return i, j
    return None, None


def page_offset(doc):
    c = collections.Counter()
    step = max(1, (doc.page_count - 40) // 60)
    for i in range(40, doc.page_count, step):
        p = doc[i]
        H = p.rect.height
        for b in p.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                t = "".join(s["text"] for s in l["spans"]).strip()
                if l["bbox"][1] > 0.9 * H and re.fullmatch(r"\d{1,4}", t):
                    c[i - int(t)] += 1
    return c.most_common(1)[0][0] if c else 0


def _raw_lines(doc, s, e):
    out = []
    for pno in range(s, e + 1):
        p = doc[pno]
        H = p.rect.height
        links = [(lk["from"].y0, lk["from"].y1, lk.get("page")) for lk in p.get_links()
                 if lk.get("kind") == fitz.LINK_GOTO]
        rows = []
        for b in p.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                t = "".join(sp["text"] for sp in l["spans"])
                if not t.strip():
                    continue
                x0, y0, x1, y1 = l["bbox"]
                size = round(max(sp["size"] for sp in l["spans"]))
                rows.append([y0, x0, y1, x1, t, size])
        rows.sort(key=lambda r: (round(r[0]), r[1]))
        merged = []  # 같은 높이 조각 합치기 (이름 · 점선 · 쪽번호가 따로 잡히는 경우)
        for r in rows:
            if merged and abs(merged[-1][0] - r[0]) < 2 and r[1] >= merged[-1][3] - 2:
                m = merged[-1]
                m[4] += r[4]; m[3] = max(m[3], r[3]); m[5] = max(m[5], r[5])
            else:
                merged.append(r)
        for y0, x0, y1, x1, t, size in merged:
            t = re.sub(r"\s+", " ", t).strip()
            if y0 > 0.9 * H and re.fullmatch(r"\d{1,4}", t):
                continue
            if norm_key(t) == "목차":
                continue
            link = None
            for ly0, ly1, lp in links:
                if min(y1, ly1) - max(y0, ly0) >= 1:
                    link = lp
                    break
            out.append({"text": t, "size": size, "toc_page": pno, "y": round(y0, 1), "link": link})
    return out


def parse_lines(raw):
    """헤더 합치기 · '이름 …… 쪽' 분해. 반환: [{hdr|name, pp, link, size}]"""
    out, i = [], 0
    while i < len(raw):
        r = raw[i]
        if r["size"] >= 13:
            if out and out[-1].get("hdr") and out[-1]["_last"] == i - 1:
                out[-1]["text"] += " " + r["text"]; out[-1]["_last"] = i
                if out[-1]["link"] is None:
                    out[-1]["link"] = r["link"]
            else:
                out.append({"hdr": True, "text": r["text"], "link": r["link"], "size": r["size"], "_last": i})
            i += 1
            continue
        text, j, link = r["text"], i, r["link"]
        while True:
            parts = re.split(_DOTS, text)
            m = re.match(r"^\s*(\d{1,4})\s*$", parts[-1]) if len(parts) > 1 else None
            if m:
                name = re.sub(r"\s+", " ", " ".join(p for p in parts[:-1])).strip()
                out.append({"text": name, "pp": int(m.group(1)), "link": link, "size": r["size"], "_last": j})
                break
            if j + 1 < len(raw) and raw[j + 1]["size"] < 13 and j - i < 2:
                j += 1
                text = text + " " + raw[j]["text"]
                link = link if link is not None else raw[j]["link"]
                continue
            out.append({"text": text, "pp": None, "link": link, "size": r["size"], "_last": i, "nopage": True})
            j = i
            break
        i = j + 1
    for o in out:
        o.pop("_last", None)
    return out


def kind_of(text):
    k = norm_key(text)
    if any(k.startswith(x) for x in _INFO):
        return "info"
    if re.match(_GWAN, text):
        return "gwan"
    if re.match(r"^\s*제\s*\d+\s*조", text):
        return "jo"
    if re.match(_JEOL, text):
        return "jeol"
    if k.startswith("【별표") or k.startswith("별표") or k.startswith("【법규"):
        return "annex"
    if re.match(_DAEBUN, text.strip()):
        return "daebun"
    if re.match(_NUM_ITEM, text.strip()):
        return "num"
    if k.endswith("일반조항"):
        return "general"
    return "other"


def is_garbled(s):
    return bool(re.search(_GARBLED, s or ""))


def apply_cipher(s, cipher):
    return "".join(cipher.get(ch, ch) for ch in s)


def read_toc(doc):
    s, e = find_toc(doc)
    if s is None:
        return None
    lines = parse_lines(_raw_lines(doc, s, e))
    return {"toc": [s, e], "lines": lines}


def learn_self_cipher(doc, lines, offset, body_lines_fn):
    """깨진 목차 줄 ↔ 본문 큰 글씨 제목 글자 맞대기 투표 (§2.4)."""
    votes = collections.defaultdict(collections.Counter)
    for ln in lines:
        if ln.get("hdr") or not is_garbled(ln["text"]):
            continue
        m = re.match(_NUM_ITEM, ln["text"].strip())
        if not m or ln.get("pp") is None:
            continue
        pno = ln["pp"] + offset
        if not (0 <= pno < doc.page_count):
            continue
        a = body_lines_fn(pno)
        if not a:
            continue
        body = a["body_size"]
        L = a["lines"]
        for k, bl in enumerate(L):
            if bl["size"] <= body + 0.2:
                continue
            mm = re.match(r"^\s*(\d{1,3}(?:-\d{1,2})?)\s*\.", bl["text"])
            if not mm or mm.group(1) != m.group(1):
                continue
            t = bl["text"]
            for q in L[k + 1:k + 4]:
                if q["size"] > body + 0.2 and q["c"] == bl["c"]:
                    t += q["text"]
                else:
                    break
            src = re.sub(r"\s+", "", m.group(2))
            dst = re.sub(r"\s+", "", re.sub(r"^\s*\d{1,3}(?:-\d{1,2})?\s*\.", "", t))
            if len(src) == len(dst):
                for a1, b1 in zip(src, dst):
                    if is_garbled(a1) and not is_garbled(b1):
                        votes[a1][b1] += 1
            break
    return {k: v.most_common(1)[0][0] for k, v in votes.items()}


def global_votes(garbled_lines, normal_by_len):
    votes = collections.defaultdict(collections.Counter)
    for t in garbled_lines:
        s = re.sub(r"\s+", "", t)
        cands = [c for c in normal_by_len.get(len(s), ())
                 if all(is_garbled(a) or a == b for a, b in zip(s, c))]
        if len(set(cands)) == 1:
            for a, b in zip(s, cands[0]):
                if is_garbled(a):
                    votes[a][b] += 1
    return votes


# ---------------- ② 항목 리스트업 ----------------

def _strip_num(t):
    m = re.match(_NUM_ITEM, t.strip())
    return (m.group(1), m.group(2).strip()) if m else (None, t.strip())


def build_items(lines, offset, page_count):
    """반환: items(계획 레코드), bounds, boxes, bundles {bkey: {name, items}}"""
    def page_of(ln):
        if ln.get("pp") is not None:
            p = ln["pp"] + offset
            if 0 <= p < page_count:
                return p
        return ln.get("link")

    boxes, cur = [], None
    for ln in lines:
        if ln.get("hdr"):
            if "색인" in norm_key(ln["text"]):
                break
            cur = {"hdr": ln, "lines": []}
            boxes.append(cur)
        elif cur is not None:
            ln["kind"] = kind_of(ln["text"])
            cur["lines"].append(ln)
    items, bounds, box_info = [], [], []
    seen_basic = False
    for bx in boxes:
        hk = norm_key(bx["hdr"]["text"])
        has_gen_jeol = any(l["kind"] == "jeol" and norm_key(l["text"]).endswith("일반조항") for l in bx["lines"])
        if "기타제도성" in hk or "기타특별약관" in hk:
            typ = "other"
        elif "보통약관" in hk and not seen_basic:
            typ = "basic"
        elif seen_basic and has_gen_jeol:
            typ = "bundle"
        elif "특별약관" in hk or any(l["kind"] in ("daebun", "num") for l in bx["lines"]):
            typ = "special" if seen_basic else "basic"
        elif not seen_basic and any(l["kind"] == "gwan" for l in bx["lines"]):
            typ = "basic"  # 표지 제목에 '보통약관'이 없는 주계약(저축보험 등)
        else:
            typ = "other"
        if typ == "basic":
            seen_basic = True
        bx["type"] = typ
        hp = bx["hdr"].get("link")
        box_info.append({"type": typ, "name": bx["hdr"]["text"], "page": hp, "n_lines": len(bx["lines"])})
        bounds.append({"kind": "hdr", "anchor": bx["hdr"]["text"], "page": hp,
                       "bundle": bx["hdr"]["text"] if typ == "bundle" else None, "hdr": True})

        def add_bound(ln):
            if ln["kind"] in ("gwan", "jo"):
                return
            bounds.append({"kind": ln["kind"], "anchor": ln["text"], "page": page_of(ln),
                           "bundle": bx["hdr"]["text"] if typ == "bundle" else None})

        def new_item(kind, ln, name, section, bundle, roman=None, no=None):
            it = {"kind": kind, "name": name, "section": section, "bundle": bundle, "page": page_of(ln),
                  "anchor": ln["text"], "akind": ln["kind"], "roman": roman, "no": no,
                  "link": ln.get("link"), "pp": ln.get("pp")}
            items.append(it)
            return it

        if typ == "other":
            for ln in bx["lines"]:
                add_bound(ln)
        elif typ == "basic":
            jeols = [l for l in bx["lines"] if l["kind"] == "jeol"]
            started = False
            jeol_item, jeol_no, seq = None, 0, 0
            for ln in bx["lines"]:
                k = ln["kind"]
                if k == "jeol":
                    add_bound(ln)
                    jeol_no += 1
                    if jeol_no == 1:
                        new_item("보통약관", ln, re.sub(r"^\s*제\s*\d+\s*절\s*", "", ln["text"]) or ln["text"], None, None, no="0")
                        jeol_item = None
                    else:
                        jeol_item = new_item("보장조항", ln, re.sub(r"^\s*제\s*\d+\s*절\s*", "", ln["text"]),
                                             ln["text"], None, no=str(jeol_no))
                        jeol_item["_removable"] = True
                    continue
                if not jeols:
                    if k == "gwan" and not started:
                        started = True
                        it = new_item("보통약관", ln, "보통약관", None, None, no="0")
                        bounds.append({"kind": "gwan", "anchor": ln["text"], "page": page_of(ln), "bundle": None})
                        continue
                    if k == "num" and started:
                        num, nm = _strip_num(ln["text"])
                        seq += 1
                        new_item("보장조항", ln, nm, None, None, no=num)
                        add_bound(ln)
                        continue
                    add_bound(ln)
                    continue
                # 절이 있는 경우
                if jeol_no >= 2 and k in ("num", "other"):
                    if jeol_item is not None and jeol_item in items:
                        sec = jeol_item["section"]
                        items.remove(jeol_item)
                        jeol_item = None
                        cur_sec = sec
                    else:
                        cur_sec = items[-1]["section"] if items else None
                    num, nm = _strip_num(ln["text"])
                    new_item("보장조항", ln, nm, cur_sec, None, no=f"{jeol_no}-{num}" if num and "-" not in num else (num or str(jeol_no)))
                    add_bound(ln)
                    continue
                add_bound(ln)
        elif typ == "special":
            section, skip, roman = None, False, None
            L = bx["lines"]
            for idx, ln in enumerate(L):
                k = ln["kind"]
                if k in ("gwan", "jo"):
                    continue
                add_bound(ln)
                t = ln["text"].strip()
                if k == "daebun":
                    m = re.match(_DAEBUN, t)
                    title = m.group(2).strip()
                    tk = norm_key(title)
                    if any(x in tk for x in ("별표", "법규정", "인용", "기타특별약관")) or (tk.startswith("기타") and "관련" not in tk):
                        skip = True
                    else:
                        skip, section, roman = False, title, m.group(1)
                    continue
                if skip:
                    continue
                if k == "num":
                    num, nm = _strip_num(t)
                    nk = norm_key(nm)
                    if any(x in nk for x in ("별표", "인용법", "법규", "기타특별약관")):
                        skip = True
                        continue
                    nxt = next((x for x in L[idx + 1:] if x["kind"] == "num"), None)
                    if nxt and "-" not in num:
                        nn, _ = _strip_num(nxt["text"])
                        if nn and nn.startswith(num + "-"):
                            section = nm
                            continue
                    no = num if "-" in num else (f"{roman}-{num}" if roman else num)
                    new_item("특별약관", ln, nm, section, None, roman=roman, no=no)
                elif k == "general":
                    new_item("일반조항", ln, t, section, None, roman=roman, no=(f"{roman}-0" if roman else "0"))
        elif typ == "bundle":
            bname = bx["hdr"]["text"]
            jeol_no, jeol_item = 0, None
            for ln in bx["lines"]:
                k = ln["kind"]
                if k in ("gwan", "jo"):
                    continue
                add_bound(ln)
                if k == "jeol":
                    jeol_no += 1
                    nm = re.sub(r"^\s*제\s*\d+\s*절\s*", "", ln["text"]).strip()
                    if jeol_no == 1:
                        new_item("일반조항", ln, nm, bname, bname, no="0")
                        jeol_item = None
                    else:
                        jeol_item = new_item("특별약관", ln, nm, bname, bname, no=str(jeol_no))
                    continue
                if jeol_no >= 2 and k == "num":
                    if jeol_item is not None and jeol_item in items:
                        items.remove(jeol_item)
                        jeol_item = None
                    num, nm = _strip_num(ln["text"])
                    new_item("특별약관", ln, nm, bname, bname, no=num)
    for it in items:
        it.pop("_removable", None)
    return items, bounds, box_info
