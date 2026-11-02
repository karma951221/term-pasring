"""검수 3: 신규 상품담보 판정 ↔ DATA 판정 대조 (같은 담보 키 + 같은 고지 접사)"""
import collections, json, os, re, sys
sys.argv = [sys.argv[0], ""]
D = os.path.dirname(os.path.abspath(__file__))
X = json.load(open(os.path.join(D, "work", "xlsx.json"), encoding="utf-8"))
R = json.load(open(os.path.join(D, "work", "new_judged.json"), encoding="utf-8"))
src = open(os.path.join(D, "judge_new.py"), encoding="utf-8").read()
ns = {}
exec(src[src.index("AFF ="):src.index("# DATA: 담보 키")].replace("from new_cov import nk, ckey  # noqa", ""), {**ns, "re": re, "nk": None}, ns) if False else None
import importlib.util
spec = importlib.util.spec_from_file_location("nc", os.path.join(D, "new_cov.py")); nc = importlib.util.module_from_spec(spec); spec.loader.exec_module(nc)
AFF = r"\((?:[^()]*간편가입|[^()]*건강가입|편한가입|[^()]*고지[^()]*가입|예약|1년감액형|2년감액형|전환용)\)"
def dkey(name):
    s = re.sub(r"^\s*\d{1,3}(-\d{1,2})?\s*\.\s*", "", name or ""); s = re.sub(r"^\s*갱신형\s*", "", s); s = re.sub(AFF, "", s)
    s = s.replace("태아가입용", ""); s = re.sub(r"\s*(보장\s*특별약관|추가특별약관|특별약관|보장)\s*$", "", s); s = re.sub(r"보장", "", s)
    return nc.nk(s)
def aff(name):
    return nc.nk(" ".join(re.findall(AFF, name or "")))
G = {"2.기왕증 미보상": "미보상", "3.기왕증 보상": "보상", "4.세부보장별 상이": "세부보장별 상이"}
exp = collections.defaultdict(collections.Counter)
for d in X["data"]:
    if d["gubun"] in G:
        exp[(dkey(d["cov"]), aff(d["cov"]))][G[d["gubun"]]] += 1
rows = [x for x in R if x["proc"].startswith("다른 구분")]
st = collections.Counter(); mism = collections.defaultdict(list)
for x in rows:
    e = exp.get((dkey(x["cov"]), aff(x["cov"])))
    if not e:
        st["DATA에 같은 키·접사 없음"] += 1; continue
    top = e.most_common(1)[0][0]
    if x["pay"] == top:
        st["일치"] += 1
    else:
        st["불일치"] += 1; mism[(dkey(x["cov"]), aff(x["cov"]), top, x["pay"])].append(x)
print(dict(st))
json.dump(dict(st), open(os.path.join(D, "work", "review3_stats.json"), "w"), ensure_ascii=False)
json.dump([{"key": k[0], "aff": k[1], "data": k[2], "new": k[3], "n": len(v), "ex": v[0]["cov"], "prod": v[0]["prod"], "id": v[0]["id"], "ev": v[0]["ev"][:400]}
           for k, v in sorted(mism.items(), key=lambda z: -len(z[1]))], open(os.path.join(D, "work", "review3.json"), "w"), ensure_ascii=False)
print("불일치 묶음", len(mism), collections.Counter((k[2], k[3]) for k in mism))
