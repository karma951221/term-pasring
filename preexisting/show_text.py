"""확인용 원문: 질문 그룹별 담보마다 지급사유 조 전문 → preexisting/원문_확인용.md"""
import json, os, re, sys, collections
D = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1]
R = json.load(open(os.path.join(D, "work", "new_judged.json"), encoding="utf-8"))
G = [("장기요양돌봄지원금 4종", lambda x: x.get("code") in ("COV000877", "COV000878", "COV000879", "COV000880"), "code"),
     ("암 통합입통원일당 2종", lambda x: x["proc"] == "코드 미정" and "통합입통원" in x["cov"], "dkey"),
     ("체증형 진단비 8종", lambda x: x["proc"] == "코드 미정" and "체증형" in x["cov"], "dkey"),
     ("간병인사용 치매주요질환입원일당 2종", lambda x: x["proc"] == "코드 미정" and "치매주요" in x["cov"], "dkey")]


def art_text(it, a):
    L = [f"[{a['text']}]"]
    for b in a["blocks"]:
        t = b.get("text", "")
        if b["t"] in ("표", "그림"):
            t = "[표] " + t[:200] + ("…" if len(t) > 200 else "")
        elif b["t"] == "박스":
            t = "[박스] " + t[:200] + ("…" if len(t) > 200 else "")
        elif b["t"] in ("항", "호", "목"):
            t = f"{b.get('n', '')} {t}"
        L.append(t)
    return "\n".join(L)


md = ["# 확인용 원문 — 10/31 약관 지급사유 조", "", "> 재파싱(배경 음영 수정 반영) 결과에서 뽑았다. 담보마다 대표 상품담보 1건의 지급사유 조 전문과, 같은 담보의 다른 상품담보 목록.", ""]
for title, f, key in G:
    xs = [x for x in R if f(x)]
    md += [f"## {title}", ""]
    by = collections.defaultdict(list)
    for x in xs:
        by[x[key] if key == "code" else x["dkey"]].append(x)
    for k, grp in by.items():
        x = grp[0]
        it = json.load(open(os.path.join(OUT, "web", "items", x["id"] + ".json"), encoding="utf-8"))
        arts = [a for a in it["arts"] if re.search(r"지급사유|세부보장", a["title"] or "")]
        md += [f"### {x['code'] or '(코드 없음)'} {x['cov']}", "",
               f"- 판정: {x['pay']} · 상품담보 {len(grp)}건 · 대표: {x['prod']} › {x['cov']} (`{x['id']}`)"]
        md += [f"- 같은 담보: " + "; ".join(sorted({g['prod'] + ' › ' + g['cov'] for g in grp[1:]}))[:1500]] if len(grp) > 1 else []
        md += ["", "```text"] + [art_text(it, a) for a in arts] + ["```", ""]
open(os.path.join(D, "원문_확인용.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
print("ok", len(md))
