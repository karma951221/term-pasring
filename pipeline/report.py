"""통계 · 확인 필요 목록 · 진행 현황 → out/work/report.md (매뉴얼 §5.2)"""
import collections, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import WORK, PLAN, norm_key


def main():
    plan = json.load(open(PLAN, encoding="utf-8"))
    ws = [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(os.path.join(WORK, "p" + "[0-9a-f]" * 8 + ".json")))]
    done = {w["file"] for w in ws}
    allf = sorted(plan["results"], key=lambda f: plan["results"][f]["pages"])
    tot = collections.Counter()
    kinds = collections.Counter()
    kinds_ref = collections.Counter()
    bundles = set()
    issues = []
    qa_ok = qa_n = 0
    rows = []
    for w in ws:
        st = w["stats"]
        for k, v in st.items():
            tot[k] += v
        own = [r for r in w["items"] if r.get("owned") and "stats" in r]
        ok = sum(1 for r in own if not r["ng"])
        qa_ok += ok; qa_n += len(own)
        for r in w["items"]:
            kinds_ref[r["label"]] += 1
            if r.get("owned") and "stats" in r:
                kinds[r["label"]] += 1
            if r["bundle"] and r.get("owned"):
                bundles.add(norm_key(r["bundle"]))
        issues.extend(w["issues"])
        tc = st.get("head_chars", 0) + st.get("art_chars", 0)
        ar = st.get("art_chars", 0) / tc * 100 if tc else 0
        pr = st.get("para_chars", 0) / st.get("art_chars", 1) * 100 if st.get("art_chars") else 0
        rows.append((w["name"], w["pages"], len(own), len(w["items"]) - len(own), st.get("arts", 0), ar, pr,
                     ok, len(own), len(w["issues"]), w.get("secs", 0)))
    tc = tot["head_chars"] + tot["art_chars"]
    L = ["# 통합약관 파싱 보고서", ""]
    L += ["## 진행 현황", "", f"완료 PDF {len(done)} / {len(allf)} · 남은 {len(allf)-len(done)}", ""]
    L += ["## 전체 통계 (매뉴얼 §5.2)", "", "| 지표 | 값 |", "|---|---|",
          f"| 상품(주계약 PDF) | {len(ws)} |",
          f"| 독립특약 묶음(실제 파싱) | {len(bundles)} / 전체 {len(plan['bundle_owner'])} |"]
    for k in ["보통약관(일반조항)", "보통약관(보장조항)", "특별약관", "관련 특별약관 하위 일반조항"]:
        L.append(f"| {k} (파싱 · 참조 포함) | {kinds[k]} · {kinds_ref[k]} |")
    L += [f"| 조 수 | {tot['arts']} |",
          f"| 조로 나뉜 글자 비율 | {tot['art_chars']/tc*100 if tc else 0:.1f}% |",
          f"| 조 안 문단 비율 | {tot['para_chars']/tot['art_chars']*100 if tot['art_chars'] else 0:.1f}% |",
          f"| 표 · 박스 · 그림 | {tot['n_표']} · {tot['n_박스']} · {tot['n_그림']} |",
          f"| 자동 QA 통과 | {qa_ok}/{qa_n} ({qa_ok/max(1,qa_n)*100:.1f}%) |",
          f"| 이슈 | {len(issues)} |", ""]
    c = collections.Counter(i["type"] for i in issues)
    L += ["## 확인 필요 목록 (유형별)", "", "| 유형 | 건수 |", "|---|---|"] + [f"| {k} | {v} |" for k, v in c.most_common()] + [""]
    L += ["### 앞 20건", "", "| 유형 | 상품 | 항목 | 내용 |", "|---|---|---|---|"]
    order = ["시작위치못찾음", "목차본문불일치", "경계섞임", "번호끊김", "항번호끊김", "제목불일치", "글자불일치", "표지불일치", "조없음"]
    srt = sorted(issues, key=lambda i: order.index(i["type"]) if i["type"] in order else 99)
    for i in srt[:20]:
        L.append(f"| {i['type']} | {i['file'][:40]} | {i.get('id','')} {i.get('name','')[:30]} | {str(i.get('detail',''))[:60]} |")
    L += ["", "전체 목록: `out/work/issues.json` (`python pipeline/run.py index` 후)", ""]
    L += ["## PDF별", "", "| 상품 | 쪽 | 항목 | 참조 | 조 | 조 비율 | 문단 비율 | QA | 이슈 | 초 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: x[1]):
        L.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]:.1f}% | {r[6]:.1f}% | {r[7]}/{r[8]} | {r[9]} | {r[10]} |")
    pend = [f for f in allf if f not in done]
    if pend:
        L += ["", "## 남은 PDF", ""] + [f"- {f} ({plan['results'][f]['pages']}쪽)" for f in pend]
    if os.path.exists(os.path.join(WORK, "failed.log")):
        L += ["", "## 실패 로그", "", "`out/work/failed.log` 참고"]
    open(os.path.join(WORK, "report.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"완료 {len(done)}/{len(allf)} · 항목 {qa_n} · 조 비율 {tot['art_chars']/tc*100 if tc else 0:.1f}% · "
          f"문단 {tot['para_chars']/tot['art_chars']*100 if tot['art_chars'] else 0:.1f}% · QA {qa_ok}/{qa_n} · 이슈 {dict(c)}")


if __name__ == "__main__":
    main()
