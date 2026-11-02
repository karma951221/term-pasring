"""③ 본문 구조화 (매뉴얼 §3.5~3.6, §4, §5.3)."""
import collections, re
from functools import lru_cache
from common import (fitz, TOP, FOOT, norm_key, match_key, balanced_title, nchars,
                    _JO_HEAD, _GWAN, _JEOL, _HO, _MOK, _MOKL, _CIRCLED, _HANG, _MOK2, _SUB,
                    _PUA_START, _PARTICLE, _NOTE, _FOOTNUM)

_ROMAN_LAT = None


def _q(vals, q):
    if not vals:
        return None
    v = sorted(vals)
    return v[min(len(v) - 1, int(len(v) * q))]


class Doc:
    def __init__(self, path, pet=False):
        self.doc = fitz.open(path)
        self.pet = pet
        self.analyze = lru_cache(maxsize=80)(self._analyze)

    # ---------------- §4.1 페이지 분석 ----------------
    def _analyze(self, pno):
        page = self.doc[pno]
        W, H = page.rect.width, page.rect.height
        raw = []
        allchars = 0
        for b in page.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                spans = [s for s in l["spans"] if s["text"]]
                if not spans:
                    continue
                t = "".join(s["text"] for s in spans)
                if not t.strip():
                    continue
                x0, y0, x1, y1 = l["bbox"]
                if y0 > 0.93 * H and re.fullmatch(_FOOTNUM, t.strip()):
                    continue
                if y1 < TOP - 6:
                    continue
                main = max(spans, key=lambda s: len(s["text"].strip()))
                raw.append({"text": t, "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                            "size": round(main["size"], 1), "bold": bool(main["flags"] & 16)})
        mid = W / 2
        ncols = 1 if self.pet else 2
        if ncols == 2:
            cross = sum(1 for r in raw if r["x0"] < mid - 20 and r["x1"] > mid + 20)
            if cross > max(3, len(raw) * 0.3):
                ncols = 1
        regions = detect_regions(page, W, H, ncols)
        body_lines = []
        for r in raw:
            cx, cy = (r["x0"] + r["x1"]) / 2, (r["y0"] + r["y1"]) / 2
            hit = None
            for g in regions:
                x0, y0, x1, y1 = g["bbox"]
                if x0 - 1 <= cx <= x1 + 1 and y0 - 1 <= cy <= y1 + 1:
                    hit = g
                    break
            if hit is not None:
                hit.setdefault("_lines", []).append(r)
            else:
                body_lines.append(r)
        for r in body_lines:
            r["c"] = 0 if ncols == 1 else (0 if (r["x0"] + r["x1"]) / 2 < mid else 1)
        body_lines.sort(key=lambda r: (r["c"], round(r["y0"]), r["x0"]))
        merged = []
        for r in body_lines:
            if merged:
                m = merged[-1]
                if (m["c"] == r["c"] and abs(m["y0"] - r["y0"]) < 2 and abs(m["y1"] - r["y1"]) < 2
                        and r["x0"] >= m["x1"] - 1):
                    gap = r["x0"] - m["x1"]
                    m["text"] += (" " if gap > r["size"] * 0.6 and not m["text"].endswith(" ") else "") + r["text"]
                    m["x1"] = max(m["x1"], r["x1"])
                    continue
            merged.append(dict(r))
        col_left, col_right = {}, {}
        for c in range(ncols):
            xs = [r["x0"] for r in merged if r["c"] == c]
            xe = [r["x1"] for r in merged if r["c"] == c]
            col_left[c] = _q(xs, 0.10) if xs else (54 if c == 0 else mid + 11)
            col_right[c] = _q(xe, 0.90) if xe else (mid - 11 if (c == 0 and ncols == 2) else W - 54)
        sizes = collections.Counter(r["size"] for r in merged)
        body = sizes.most_common(1)[0][0] if sizes else 10.0
        regs = []
        for g in regions:
            ls = sorted(g.pop("_lines", []), key=lambda r: (round(r["y0"]), r["x0"]))
            g["lines"] = ls
            regs.extend(split_box(g))
        for g in regs:
            g["text"] = re.sub(r"\s+", " ", " ".join(r["text"] for r in g["lines"])).strip()
            g["chars"] = sum(nchars(r["text"]) for r in g["lines"])
            g.pop("lines", None)
        return {"W": W, "H": H, "ncols": ncols, "lines": merged, "regions": regs,
                "col_left": col_left, "col_right": col_right, "body_size": body}


# ---------------- §4.2 표 · 박스 · 그림 ----------------

def _union_find(rects, pad=1.0):
    n = len(rects)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    order = sorted(range(n), key=lambda i: rects[i][0])
    active = []
    for i in order:
        x0, y0, x1, y1 = rects[i]
        active = [j for j in active if rects[j][2] + pad >= x0 - pad]
        for j in active:
            a = rects[j]
            if a[0] - pad <= x1 + pad and x0 - pad <= a[2] + pad and a[1] - pad <= y1 + pad and y0 - pad <= a[3] + pad:
                ra, rb = find(i), find(j)
                if ra != rb:
                    parent[ra] = rb
        active.append(i)
    groups = collections.defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())


def detect_regions(page, W, H, ncols):
    prims = []  # 괘선 (rect, kind) kind: h, v, rect
    fills_all = []  # 채움 도형: 괘선 묶음 안에 든 것만 fills 로 센다(배경 음영만으로는 표가 아님)
    curves = []
    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []
    for d in drawings:
        r = d.get("rect")
        if r is None or r.y0 > 0.94 * H or r.y1 < TOP - 6:
            continue
        has_curve = any(it[0] == "c" for it in d["items"])
        if has_curve:
            if r.width >= 30 and r.height >= 30:
                curves.append((r.x0, r.y0, r.x1, r.y1))
            continue
        dtype = d.get("type") or ""
        filled = d.get("fill") is not None and "f" in dtype
        stroked = "s" in dtype
        if filled and not stroked:
            # 채움만 있는 도형(배경 음영): 선으로 세지 않고 채움 1개로만 본다
            if r.width >= 2.5 and r.height >= 2.5:
                fills_all.append((r.x0, r.y0, r.x1, r.y1))
            continue
        for it in d["items"]:
            if it[0] == "l":
                p1, p2 = it[1], it[2]
                rr = (min(p1.x, p2.x), min(p1.y, p2.y), max(p1.x, p2.x), max(p1.y, p2.y))
            elif it[0] == "re":
                q = it[1]
                rr = (q.x0, q.y0, q.x1, q.y1)
            elif it[0] == "qu":
                q = it[1].rect
                rr = (q.x0, q.y0, q.x1, q.y1)
            else:
                continue
            w, h = rr[2] - rr[0], rr[3] - rr[1]
            if h < 2.5 and w > 8:
                prims.append((rr, "h"))
            elif w < 2.5 and h > 6:
                prims.append((rr, "v"))
            elif w >= 2.5 and h >= 2.5:
                prims.append((rr, "rect"))
                if filled:
                    fills_all.append(rr)
    col_h = FOOT * H - TOP
    regions = []
    leftovers = 0
    if prims:
        groups = _union_find([p[0] for p in prims])
        for g in groups:
            hy, vx, fills = set(), set(), 0
            x0 = min(prims[i][0][0] for i in g); y0 = min(prims[i][0][1] for i in g)
            x1 = max(prims[i][0][2] for i in g); y1 = max(prims[i][0][3] for i in g)
            for fr in fills_all:
                cx, cy = (fr[0] + fr[2]) / 2, (fr[1] + fr[3]) / 2
                if (x0 - 1 <= cx <= x1 + 1 and y0 - 1 <= cy <= y1 + 1
                        and (fr[2] - fr[0]) * (fr[3] - fr[1]) <= (x1 - x0 + 2) * (y1 - y0 + 2)):
                    fills += 1
            for i in g:
                rr, k = prims[i]
                if k == "h":
                    hy.add(round((rr[1] + rr[3]) / 2))
                elif k == "v":
                    vx.add(round((rr[0] + rr[2]) / 2))
                elif k == "rect":
                    hy.add(round(rr[1])); hy.add(round(rr[3])); vx.add(round(rr[0])); vx.add(round(rr[2]))
            bw, bh = x1 - x0, y1 - y0
            typ = None
            if len(hy) <= 2 and len(vx) <= 2 and fills < 3:
                if bw > 8 and bh > 6 and not (bw > 0.6 * W and bh > col_h * 0.8):
                    typ = "박스"
            elif (len(hy) >= 3 and len(vx) >= 2) or (len(hy) >= 2 and len(vx) >= 3) or fills >= 3:
                if bh < col_h * 0.97 or len(hy) >= 3:
                    typ = "표"
            if typ:
                regions.append({"t": typ, "bbox": [x0, y0, x1, y1], "_idx": set(g)})
            elif len(g) >= 4:
                leftovers += 1
    imgs = []
    try:
        for im in page.get_image_info():
            b = im["bbox"]
            if b[2] - b[0] >= 20 and b[3] - b[1] >= 20 and b[1] < FOOT * H and b[3] > TOP - 6:
                imgs.append(tuple(b))
    except Exception:
        pass
    # 박스 안에 다른 선 · 도형 · 이미지가 있으면 표(그림형 예시)
    for g in regions:
        if g["t"] != "박스":
            continue
        x0, y0, x1, y1 = g["bbox"]
        inner = False
        for i, (rr, k) in enumerate(prims):
            if i in g["_idx"]:
                continue
            cx, cy = (rr[0] + rr[2]) / 2, (rr[1] + rr[3]) / 2
            if x0 < cx < x1 and y0 < cy < y1:
                inner = True
                break
        if not inner:
            for b in imgs + curves:
                cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                if x0 < cx < x1 and y0 < cy < y1:
                    inner = True
                    break
        if inner:
            g["t"] = "표"
    for g in regions:
        g.pop("_idx", None)
    for b in imgs + curves:
        regions.append({"t": "그림", "bbox": list(b)})
    if leftovers:
        try:
            for t in page.find_tables().tables:
                b = list(t.bbox)
                if t.row_count * t.col_count <= 1:
                    continue
                if any(_overlap(b, g["bbox"]) for g in regions):
                    continue
                regions.append({"t": "표", "bbox": b})
        except Exception:
            pass
    # 겹치는 영역 합치기: 큰 것부터, 바깥 종류 유지
    regions.sort(key=lambda g: -(g["bbox"][2] - g["bbox"][0]) * (g["bbox"][3] - g["bbox"][1]))
    kept = []
    for g in regions:
        for k in kept:
            if _overlap(g["bbox"], k["bbox"]):
                k["bbox"] = [min(k["bbox"][0], g["bbox"][0]), min(k["bbox"][1], g["bbox"][1]),
                             max(k["bbox"][2], g["bbox"][2]), max(k["bbox"][3], g["bbox"][3])]
                break
        else:
            kept.append(g)
    mid = W / 2
    for g in kept:
        x0, y0, x1, y1 = g["bbox"]
        if ncols == 1:
            g["c"] = 0
        elif x0 < mid - 15 and x1 > mid + 15:
            g["c"] = -1
        else:
            g["c"] = 0 if (x0 + x1) / 2 < mid else 1
        g["bbox"] = [round(v, 1) for v in g["bbox"]]
    return kept


def _overlap(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > 0.5 and min(a[3], b[3]) - max(a[1], b[1]) > 0.5


def split_box(g):
    if g["t"] != "박스":
        return [g]
    heads = [i for i, r in enumerate(g["lines"]) if r["text"].lstrip().startswith("【")]
    if len(heads) <= 1:
        g["title"] = _box_title(g["lines"])
        return [g]
    out = []
    starts = heads if heads[0] == 0 else [0] + heads
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else len(g["lines"])
        ls = g["lines"][s:e]
        if not ls:
            continue
        y0 = g["bbox"][1] if k == 0 else round(ls[0]["y0"] - 1, 1)
        y1 = g["bbox"][3] if k == len(starts) - 1 else round(g["lines"][e]["y0"] - 1, 1)
        out.append({"t": "박스", "bbox": [g["bbox"][0], y0, g["bbox"][2], y1], "c": g["c"],
                    "lines": ls, "title": _box_title(ls)})
    return out


def _box_title(ls):
    if not ls:
        return ""
    t = ls[0]["text"].strip()
    m = re.match(r"^【([^】]*)】", t)
    if m:
        return m.group(1).strip()
    m = re.match(r"^【(.*)$", t)
    if m:
        return m.group(1).strip()[:60]
    return t[:60]


# ---------------- §3.5 시작 위치 찾기 ----------------

def locate(dx, page, anchor, kind):
    if page is None or not (0 <= page < dx.doc.page_count):
        return None
    if kind == "hdr":
        return (page, 0, 0.0)
    a = dx.analyze(page)
    key = match_key(anchor)
    L = a["lines"]
    body = a["body_size"]
    for i, ln in enumerate(L):
        acc = match_key(ln["text"])
        for q in L[i + 1:i + 4]:
            if q["c"] != ln["c"]:
                break
            acc += match_key(q["text"])
        n = min(len(key), len(acc), 14)
        if n < 3 or key[:n] != acc[:n]:
            continue
        strong = n >= 10
        big = ln["size"] > body + 0.2 or (kind == "gwan" and ln["size"] >= body - 0.2)
        if big or strong or kind in ("info", "general", "other", "hdr"):
            return (page, ln["c"], round(ln["y0"], 1))
    return None


def cover_check(dx, page, hdr_text):
    try:
        t = dx.doc[page].get_text()
    except Exception:
        return False
    k = match_key(hdr_text)[:12]
    return nchars(t) <= 200 and k in match_key(t)


# ---------------- §4.3 블록 만들기 ----------------

def _elements(dx, start, end):
    els = []
    sp, ep = start[0], min(end[0], dx.doc.page_count - 1)
    for p in range(sp, ep + 1):
        a = dx.analyze(p)
        for ln in a["lines"]:
            pos = (p, ln["c"], round(ln["y0"], 1))
            if start <= pos < end:
                els.append(("L", pos, ln, a))
        for g in a["regions"]:
            c = max(g["c"], 0)
            pos = (p, c, g["bbox"][1])
            if start <= pos < end:
                els.append(("R", pos, g, a))
    els.sort(key=lambda e: (e[1][0], e[1][1], e[1][2], (e[2]["x0"] if e[0] == "L" else e[2]["bbox"][0])))
    return els


def _ends_block(text):
    return bool(re.search(r"(다|요|음|함|임|것|\.|\)|】|」)\s*$", text or ""))


def _ends_sent(text):
    return bool(re.search(r"(\.|:|다|\)|」|】|등|형|음|함|임|것)\s*$", text or ""))


_MOK2_ORDER = {}


def _mok2_style(tok):
    if re.match(r"^\d+\)$", tok):
        return "n)", int(tok[:-1])
    if re.match(r"^\(\d+\)$", tok):
        return "(n)", int(tok[1:-1])
    if re.match(rf"^\([{_MOKL}]\)$", tok):
        return "(가)", _MOKL.index(tok[1]) + 1
    if re.match(rf"^[{_MOKL}]\)$", tok):
        return "가)", _MOKL.index(tok[0]) + 1
    if "㉠" <= tok[0] <= "㉭":
        return "㉠", ord(tok[0]) - ord("㉠") + 1
    if "㉮" <= tok[0] <= "㉻":
        return "㉮", ord(tok[0]) - ord("㉮") + 1
    return None, None


def build_blocks(dx, start, end):
    els = _elements(dx, start, end)
    stat = {"orig": 0}
    sizes = collections.Counter()
    pua_doc = False
    for e in els:
        if e[0] == "L":
            n = nchars(e[2]["text"])
            stat["orig"] += n
            sizes[e[2]["size"]] += n
            if re.match(_PUA_START, e[2]["text"]):
                pua_doc = True
        else:
            stat["orig"] += e[2].get("chars", 0)
    body = sizes.most_common(1)[0][0] if sizes else 10.0
    blocks = []
    cur = None
    prev = None  # (pos, line, analysis)
    pend = None  # 조 제목 괄호 이어붙이기
    hn = 0
    ho_last, ho_open, mok_last = 0, False, 0
    mok2 = {}

    def push(b):
        nonlocal cur
        blocks.append(b)
        cur = b
        return b

    def mk(t, ln, pos, text, **kw):
        b = {"t": t, "text": text, "p": pos[0], "c": pos[1], "y0": round(ln["y0"], 1), "y1": round(ln["y1"], 1)}
        b.update(kw)
        return b

    def nxt_line(i):
        for e in els[i + 1:]:
            if e[0] == "L":
                return e[2]["text"].strip()
            return None
        return None

    def append(ln, pos):
        if cur is None:
            return
        if (pos[0], pos[1]) != (cur["p"], cur["c"]) and not cur.get("span"):
            cur["span"] = True
        cur["text"] += ln["text"]
        if (pos[0], pos[1]) == (cur["p"], cur["c"]):
            cur["y1"] = round(max(cur["y1"], ln["y1"]), 1)

    for i, (typ, pos, ln, a) in enumerate(els):
        if typ == "R":
            g = ln
            b = {"t": g["t"], "text": g.get("text", ""), "bbox": g["bbox"], "p": pos[0], "c": g["c"],
                 "y0": g["bbox"][1], "y1": g["bbox"][3]}
            if g["t"] == "박스":
                b["title"] = g.get("title", "")
            blocks.append(b)
            cur, prev, pend = None, None, None
            continue
        text = ln["text"]
        st = text.strip()
        lh = max(ln["y1"] - ln["y0"], 1.0)
        gap = (ln["y0"] - prev[2]["y1"]) if (prev and prev[1][:2] == pos[:2]) else None
        col_change = prev is not None and prev[1][:2] != pos[:2]
        # 2. 조 제목 괄호 이어붙이기
        if pend is not None:
            pend["text"] += text
            pend["y1"] = round(max(pend["y1"], ln["y1"]), 1)
            bt = balanced_title(pend["text"].strip())
            if (bt and bt[1] is not None) or len(pend["text"]) > 120:
                nx = nxt_line(i)
                quote = bt is None or bt[1] is None or bt[2].strip() or (nx and re.match(_PARTICLE, nx))
                if quote:
                    pend["t"] = "문단"
                    push(pend)
                else:
                    pend.update({"t": "조", "label": bt[0], "title": bt[1].strip()})
                    push(pend)
                    hn, ho_last, ho_open, mok_last, mok2 = 0, 0, False, 0, {}
                pend = None
            prev = (typ, pos, ln)
            continue
        size = ln["size"]
        # 3. 큰 글씨
        if size > body + 0.2:
            if len(st) <= 1 and not st.isalnum():
                prev = (typ, pos, ln)
                continue
            if re.match(_GWAN, st):
                push(mk("관", ln, pos, st))
            elif re.match(_JEOL, st):
                push(mk("절", ln, pos, st))
            elif cur is not None and cur["t"] == "제목" and gap is not None and gap < lh * 1.2:
                append(ln, pos)
            else:
                push(mk("제목", ln, pos, st))
            prev = (typ, pos, ln)
            continue
        # 4. 조 제목
        if re.match(_JO_HEAD, st):
            ok_ctx = (cur is None or cur["t"] in ("제목", "관", "절", "표", "그림", "박스")
                      or _ends_block(cur["text"]) or (gap is not None and gap > lh * 0.4) or col_change)
            nx = nxt_line(i)
            bt = balanced_title(st)
            if ok_ctx and (bt[1] is None or not (nx and re.match(_PARTICLE, nx))):
                if bt[1] is None:
                    pend = mk("조", ln, pos, text)
                    prev = (typ, pos, ln)
                    continue
                if not bt[2].strip():
                    push(mk("조", ln, pos, st, label=bt[0], title=bt[1].strip()))
                    hn, ho_last, ho_open, mok_last, mok2 = 0, 0, False, 0, {}
                    prev = (typ, pos, ln)
                    continue
        # 5. 기호만 있는 짧은 줄
        if len(st) <= 2 and not re.search(r"\w", st) and cur is not None:
            cur["text"] += st
            prev = (typ, pos, ln)
            continue
        # 6. 문맥
        cl = a["col_left"].get(pos[1], 54)
        cr = a["col_right"].get(pos[1], a["W"] - 54)
        indented = text[:1].isspace() or (ln["x0"] - cl > 4)
        ends_sent = cur is not None and _ends_sent(cur["text"])
        prev_short = False
        if prev is not None and prev[1][:2] == pos[:2]:
            room = cr - prev[2]["x1"]
            colw = cr - cl
            prev_short = (room > prev[2]["size"] * 1.5 and ends_sent) or room > colw * 0.35
        para_end = (prev is None or (col_change and ends_sent) or (gap is not None and gap > lh * 0.9)
                    or prev_short or cur is None)
        outdent = prev is not None and prev[1][:2] == pos[:2] and ln["x0"] < prev[2]["x0"] - 3
        sent_end = para_end or ends_sent or outdent
        # 7. 항
        m = re.match(_HANG, text)
        if m:
            sym = m.group(1)
            body_t = text[m.end():].strip()
            if "" <= sym <= "":
                hn += 1
                push(mk("항", ln, pos, body_t, n=_CIRCLED[hn - 1] if hn <= 20 else f"({hn})", hn=hn))
                ho_last, ho_open, mok_last, mok2 = 0, False, 0, {}
            elif pua_doc:
                push(mk("호", ln, pos, body_t, n=sym))
                ho_open, mok_last, mok2 = True, 0, {}
            else:
                hn = _CIRCLED.index(sym) + 1
                push(mk("항", ln, pos, body_t, n=sym, hn=hn))
                ho_last, ho_open, mok_last, mok2 = 0, False, 0, {}
            prev = (typ, pos, ln)
            continue
        # 8. 호
        m = re.match(_HO, text)
        if m and sent_end:
            num = int(m.group(1))
            if num == 1 or num == ho_last + 1:
                push(mk("호", ln, pos, text[m.end():].strip(), n=f"{num}."))
                ho_last, ho_open, mok_last, mok2 = num, True, 0, {}
                prev = (typ, pos, ln)
                continue
        # 9. 목
        m = re.match(_MOK, text)
        if m and sent_end:
            k = _MOKL.index(m.group(1)) + 1
            if k == mok_last + 1:
                push(mk("목", ln, pos, text[m.end():].strip(), n=f"{m.group(1)}."))
                mok_last = k
                prev = (typ, pos, ln)
                continue
        # 10. 목2
        m = re.match(_MOK2, text)
        if m and ho_open:
            tok = m.group(1).strip()
            style, k = _mok2_style(tok)
            if style and (sent_end or style in ("㉠", "㉮")) and k == mok2.get(style, 0) + 1:
                mok2[style] = k
                push(mk("목", ln, pos, text[m.end():].strip(), n=tok))
                prev = (typ, pos, ln)
                continue
        # 11. 각주
        if re.match(_NOTE, text) and sent_end:
            push(mk("각주", ln, pos, st))
            prev = (typ, pos, ln)
            continue
        # 12. 새 문단
        if para_end or (re.match(_SUB, text) and sent_end) or (cur is not None and cur["t"] in ("제목", "관", "절", "조")):
            push(mk("문단", ln, pos, st))
            prev = (typ, pos, ln)
            continue
        # 13. 이어쓰기
        append(ln, pos)
        prev = (typ, pos, ln)
    if pend is not None:
        pend["t"] = "문단"
        blocks.append(pend)
    # 후처리
    out = []
    for b in blocks:
        b["text"] = re.sub(r"\s+", " ", b["text"]).strip()
        if b["t"] == "문단" and b["text"].startswith("【") and not b.get("span"):
            a = dx.analyze(b["p"])
            cl = a["col_left"].get(b["c"], 54); cr = a["col_right"].get(b["c"], a["W"] - 54)
            b["t"] = "박스"; b["noborder"] = True
            b["bbox"] = [round(cl, 1), b["y0"], round(cr, 1), b["y1"]]
            b["title"] = _box_title([{"text": b["text"]}])
        out.append(b)
    for k, b in enumerate(out):
        if b["t"] == "박스":
            t = b["text"]
            cont = (t.startswith("】") or (re.match(r"^[^【]{0,25}】", t) is not None and not t.startswith("【"))) \
                or (k > 0 and out[k - 1]["t"] in ("박스", "표", "그림") and not t.startswith("【"))
            if t.startswith("【"):
                b["label"] = "박스"
            elif cont:
                b["label"] = "(계속)"
            else:
                b["label"] = "박스"
    return out, stat


# ---------------- §4.4 nest ----------------

def nest(blocks):
    head, arts, cur, gwan = [], [], None, None
    for b in blocks:
        if b["t"] == "관":
            if cur is None:
                head.append(b)
            gwan = b["text"]
            continue
        if b["t"] == "조":
            cur = {"label": b["label"], "title": b["title"], "gwan": gwan, "text": b["text"],
                   "p": b["p"], "c": b["c"], "y0": b["y0"], "y1": b["y1"], "blocks": []}
            arts.append(cur)
            continue
        (cur["blocks"] if cur else head).append(b)
    return head, arts


# ---------------- §5.3 자동 QA ----------------

def block_chars(b):
    n = nchars(b.get("text", ""))
    if b["t"] in ("항", "호", "목") and b.get("n"):
        n += nchars(b["n"]) if not str(b["n"]).startswith("(") else 1
    return n


def item_stats(head, arts):
    st = collections.Counter()
    for b in head:
        st["head_chars"] += block_chars(b)
        st["n_" + b["t"]] += 1
    for a in arts:
        st["art_chars"] += nchars(a["text"])
        for b in a["blocks"]:
            c = block_chars(b)
            st["art_chars"] += c
            if b["t"] == "문단":
                st["para_chars"] += c
            st["n_" + b["t"]] += 1
    st["arts"] = len(arts)
    return dict(st)


def _jo_num(label):
    m = re.match(r"제(\d+)조(?:의(\d+))?", label)
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (None, None)


def qa_item(it, head, arts, orig, removed_title_chars=0):
    ng = []
    st = item_stats(head, arts)
    got = st.get("head_chars", 0) + st.get("art_chars", 0) + removed_title_chars
    if orig and abs(got - orig) / orig > 0.01:
        ng.append(("글자불일치", f"원문 {orig} · 블록 {got}"))
    prev = None
    for a in arts:
        n, s = _jo_num(a["label"])
        if n is None:
            continue
        if prev is None:
            if n != 1:
                ng.append(("번호끊김", f"첫 조 {a['label']}"))
        else:
            pn, ps = prev
            if not ((n == pn + 1 and s == 0) or (n == pn and s >= 1 and s == ps + 1) or (n == pn + 1 and s >= 1)):
                ng.append(("번호끊김", f"{pn}조 다음 {a['label']}"))
        prev = (n, s)
    for a in arts:
        hs = [b.get("hn") for b in a["blocks"] if b["t"] == "항"]
        if hs and hs != list(range(1, len(hs) + 1)):
            ng.append(("항번호끊김", f"{a['label']} 항 {hs[:8]}"))
            break
    titles = [b for b in head if b["t"] == "제목"] + [b for a in arts for b in a["blocks"] if b["t"] == "제목"]
    if len(titles) >= 2:
        ng.append(("경계섞임", f"제목 {len(titles)}개: " + " | ".join(t["text"][:30] for t in titles[1:3])))
    if titles:
        tk = match_key(re.sub(r"^\s*[\dⅠ-Ⅹ\-]+\s*\.\s*", "", titles[0]["text"]))
        nk = match_key(it["name"])[:10]
        if nk and nk not in tk and tk[:10] not in match_key(it["name"]):
            ng.append(("제목불일치", f"{titles[0]['text'][:40]}"))
    warn = []
    if not arts:
        warn.append(("조없음", ""))
    return ng, warn, st
