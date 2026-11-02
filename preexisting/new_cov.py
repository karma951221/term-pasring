"""§5-1 새 상품담보 찾기: 10/31 약관 항목 중 DATA (상품명, 상품담보명)에 없는 것"""
import json, os, re, sys, unicodedata
D = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else ""  # 재파싱 결과 폴더(out)
X = json.load(open(os.path.join(D, "work", "xlsx.json"), encoding="utf-8"))
idx = json.load(open(os.path.join(OUT, "web", "index.json"), encoding="utf-8")) if OUT and os.path.exists(os.path.join(OUT, "web", "index.json")) else None


def nk(s):
    s = unicodedata.normalize("NFKC", s or "").replace("ㆍ", "·").replace("•", "·").replace("∙", "·")
    return re.sub(r"[\s·.]", "", s).lower()


def pkey(s):  # 상품명: 버전 숫자 · (무)/무배당 · '약관' 무시
    s = re.sub(r"^\s*(\(무\)|무배당)\s*", "", s or "")
    s = re.sub(r"\d{4}(\.\d)?(?=\D|$)", "", s)
    s = re.sub(r"약관$", "", s.strip())
    s = re.sub(r"\s*\([^()]*(심사형|고지형|가입형|계약형)\)\s*$", "", s)  # 고지유형 접미
    s = re.sub(r"\s*\([^()]*(심사형|고지형|가입형|계약형)\)\s*$", "", s)
    return nk(s)


def ckey(s):
    s = re.sub(r"^\s*\d{1,3}(-\d{1,2})?\s*\.\s*", "", s or "")
    s = re.sub(r"\d{4}(\.\d)?(?=\D|$)", "", s)
    return nk(s)


def main():
    global data_keys
    data_keys = {(pkey(p), ckey(d["cov"])) for d in X["data"] for p in (d["prod"] or "").split(", ")}
    data_prods = {pkey(p) for d in X["data"] for p in (d["prod"] or "").split(", ")}
    prods = {p["id"]: p for p in idx["products"]}
    OUTSCOPE = ("상해관련", "비용손해", "재물손해", "배상책임", "반려", "실손", "법률비용")
    rows = []
    for it in idx["items"]:
        if it["kind"] not in ("특별약관", "보장조항", "보통약관"):
            continue
        if it["bundle"]:
            prod = it["bundle"]
        else:
            prod = prods[it["src"]]["name"]
        key = (pkey(prod), ckey(it["name"] if it["kind"] != "보통약관" else prod))
        sec = nk(it.get("section") or "")
        nm = nk(it["name"])
        scope = "범위 밖" if (any(k in sec for k in OUTSCOPE) or any(k in nm for k in ("배상책임", "실손", "반려", "펫퍼민트"))
                             or ("상해" in nm and "질병" not in nm)) else "대상"
        rows.append({"id": it["id"], "kind": it["kind"], "prod": prod, "cov": it["name"], "section": it.get("section"),
                     "known": key in data_keys, "prod_known": key[0] in data_prods, "scope": scope})
    uniq = {}
    for r in rows:
        uniq.setdefault((pkey(r["prod"]), ckey(r["cov"])), r)
    rows = list(uniq.values())
    json.dump(rows, open(os.path.join(D, "work", "cov1031.json"), "w"), ensure_ascii=False)
    from collections import Counter
    print("10/31 상품담보(중복 제거)", len(rows), "· DATA에 있음", sum(r["known"] for r in rows))
    new = [r for r in rows if not r["known"]]
    print("새 상품담보", len(new), Counter((r["kind"], r["scope"], r["prod_known"]) for r in new))
    print("DATA 상품 수", len(data_prods), "· 10/31 상품 수", len({pkey(r['prod']) for r in rows}),
          "· 10/31에만 있는 상품", len({pkey(r['prod']) for r in rows} - data_prods))
    for p in sorted({r["prod"] for r in new if not r["prod_known"]})[:40]: print("  새상품:", p)


if __name__ == "__main__":
    main()
