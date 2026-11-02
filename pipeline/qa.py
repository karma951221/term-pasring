"""상품 1개 자동 QA (매뉴얼 §5.3): python pipeline/qa.py <파일명 일부> [NG 표시 수]"""
import collections, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import WORK


def ratio(st):
    tot = st.get("head_chars", 0) + st.get("art_chars", 0)
    art = st.get("art_chars", 0)
    return (art / tot * 100 if tot else 0), (st.get("para_chars", 0) / art * 100 if art else 0)


def qa(sub, show=20):
    for wp in sorted(glob.glob(os.path.join(WORK, "p" + "[0-9a-f]" * 8 + ".json"))):
        w = json.load(open(wp, encoding="utf-8"))
        if sub not in w["file"]:
            continue
        own = [r for r in w["items"] if r.get("owned") and "stats" in r]
        ok = sum(1 for r in own if not r["ng"])
        ar, pr = ratio(w["stats"])
        st = w["stats"]
        print(f"## {w['name']}  ({w['pages']}쪽, {w['secs']}s)")
        print("| 항목(파싱) | 참조 | 조 | 조 비율 | 문단 비율 | 표 | 박스 | 그림 | QA 통과 |")
        print("|---|---|---|---|---|---|---|---|---|")
        print(f"| {len(own)} | {len(w['items'])-len(own)} | {st.get('arts',0)} | {ar:.1f}% | {pr:.1f}% | "
              f"{st.get('n_표',0)} | {st.get('n_박스',0)} | {st.get('n_그림',0)} | {ok}/{len(own)} ({ok/max(1,len(own))*100:.1f}%) |")
        c = collections.Counter(i["type"] for i in w["issues"])
        print("이슈:", dict(c))
        n = 0
        for r in own:
            for t, d in r["ng"]:
                if n < show:
                    print(f"  NG {t:6} {r['id']:14} {r['name'][:30]} :: {d[:70]}")
                n += 1
        for i in w["issues"]:
            if i["type"] in ("시작위치못찾음", "표지불일치") and n < show:
                print(f"  {i['type']} {i.get('name', i.get('anchor',''))[:40]} p{i.get('page')}")
                n += 1


if __name__ == "__main__":
    qa(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 20)
