"""입력 묶음 md → 대표담보별 요약(트리거 문장 · 키워드 · 참고 조문 플래그)"""
import json, os, re, sys
D = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(D, "work", "input.md"), encoding="utf-8").read()
KW = ["진단확정", "질병", "상해", "검사", "촬영", "수급대상", "인정", "등록", "출생", "응급", "내원", "치아", "수술",
      "입원", "사망", "장해", "치료", "결정", "산정특례", "생략"]
secs = re.split(r"(?m)^## (?=COV|NEW)", src)[1:]
out = []
for s in secs:
    head = s.split("\n", 1)[0].strip()
    code, name = head.split(" ", 1)
    meta = re.search(r"^- 상품담보 (\d+)건 · 판매 유효값 (.*?) · 현행 구분: (.*)$", s, re.M)
    note = re.search(r"^- 기존 비고[:：]?\s*(.*)$", s, re.M)
    bundles = re.split(r"(?m)^### 지급사유 원문 \d+ — ", s)[1:]
    bl = []
    for b in bundles:
        n = re.match(r"상품담보 (\d+)건", b)
        who = re.search(r"^- (.*?) · `", b, re.M)
        txt = re.search(r"```text\n(.*?)```", b, re.S)
        txt = txt.group(1) if txt else ""
        body = "\n".join(l for l in txt.splitlines() if not l.startswith("[제") or True)
        first = next((l for l in txt.splitlines() if re.match(r"^[①1]", l)), txt.splitlines()[1] if len(txt.splitlines()) > 1 else txt)
        sig = sorted(k for k in KW if k in body)
        bl.append({"n": int(n.group(1)) if n else 0, "who": who.group(1) if who else "", "first": first,
                   "sig": sig, "body": body})
    ref = re.search(r"\*\*참고 조문\*\*\s*```text\n(.*?)```", s, re.S)
    reft = ref.group(1) if ref else ""
    pre = bool(re.search(r"보장개시일\s*(전|이전)[^.]{0,40}(발병|진단|치료|발생)", reft))
    out.append({"code": code, "name": name, "n": int(meta.group(1)) if meta else 0,
                "valid": meta.group(2) if meta else "", "gubun": meta.group(3) if meta else "",
                "note": note.group(1) if note else "", "bundles": bl, "pre": pre})
json.dump(out, open(os.path.join(D, "work", "digest.json"), "w"), ensure_ascii=False)
w = int(sys.argv[1]) if len(sys.argv) > 1 else 230
with open(os.path.join(D, "work", "digest.txt"), "w", encoding="utf-8") as f:
    for i, c in enumerate(out):
        sigs = {tuple(b["sig"]) for b in c["bundles"]}
        f.write(f"#{i+1} {c['code']} {c['name']} | 상품담보 {c['n']} · 원문 {len(c['bundles'])} · 키워드묶음 {len(sigs)}"
                f"{' · 보장개시일전부지급' if c['pre'] else ''}{(' · 비고:' + c['note'][:80]) if c['note'] else ''}\n")
        seen = set()
        for k, b in enumerate(c["bundles"]):
            key = tuple(b["sig"])
            if key in seen:
                continue
            seen.add(key)
            f.write(f"  [{k+1}] {b['first'][:w]}\n      kw={','.join(b['sig'])}\n")
print(len(out), "대표담보 ·", sum(c["n"] for c in out), "상품담보 ·", sum(len(c["bundles"]) for c in out), "원문")
