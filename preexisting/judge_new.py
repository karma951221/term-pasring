"""§5-2·3 새 상품담보 보상여부 판정 + 대표담보코드 붙이기"""
import json, os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from new_cov import nk, ckey  # noqa
D = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1]
X = json.load(open(os.path.join(D, "work", "xlsx.json"), encoding="utf-8"))
rows = [r for r in json.load(open(os.path.join(D, "work", "cov1031.json"), encoding="utf-8")) if not r["known"]]
AFF = r"\((?:[^()]*간편가입|[^()]*건강가입|편한가입|[^()]*고지[^()]*가입|예약|1년감액형|2년감액형|전환용)\)"


def dkey(name):
    s = re.sub(r"^\s*\d{1,3}(-\d{1,2})?\s*\.\s*", "", name or "")
    s = re.sub(r"^\s*갱신형\s*", "", s)
    s = re.sub(AFF, "", s)
    s = s.replace("태아가입용", "")
    s = re.sub(r"\s*(보장\s*특별약관|추가특별약관|특별약관|보장)\s*$", "", s)
    s = re.sub(r"보장", "", s)
    return nk(s)


def affix(name):
    return " ".join(re.findall(AFF, name or ""))


# DATA: 담보 키 → 대표담보코드(최빈)
dk = collections.defaultdict(collections.Counter)
for d in X["data"]:
    if d["code"]:
        dk[dkey(d["cov"])][d["code"]] += 1
covname = {nk(c["name"]): c["code"] for c in X["covlist"]}
covname_all = {c["code"]: c["name"] for c in X["covlist"]}
code_gubun = collections.defaultdict(collections.Counter)
for d in X["data"]:
    if d["code"]:
        code_gubun[d["code"]][d["gubun"]] += 1
target = {t["code"] for t in X["target"]}
SENT_SPLIT = re.compile(r"(?<=다\.)\s+|(?<=[.。])\s+(?=[가-힣「])")
PERIOD = re.compile(r"보험기간\s*중")
DIAG = re.compile(r"진단\s*확정|진단받|진단을\s*받|진단되")


def pay_blocks(it):
    """지급사유 조의 본문 항·호(세부보장 위임이면 세부보장 조의 「N.(보험금의 지급사유)」 소절)"""
    arts = it["arts"]
    pa = next((a for a in arts if re.search(r"보험금의\s*지급사유|보상하는\s*손해", a["title"] or "")), None)
    if pa is None:
        return None, []
    txt = " ".join(b.get("text", "") for b in pa["blocks"])
    out = []
    m = re.search(r"제\s*\d+\s*조\s*\((세부보장[^)]*)\)\s*에서\s*정", txt)
    if m:
        sub = next((a for a in arts if "세부보장" in (a["title"] or "")), None)
        if sub:
            on = False
            for b in sub["blocks"]:
                t = b.get("text", "")
                if re.match(r"^\s*\d+\s*\.?\s*\(\s*보험금의\s*지급사유\s*\)", t) or (b["t"] == "호" and t.startswith("(보험금의 지급사유)")):
                    on = True
                    continue
                if on and (re.match(r"^\s*\d+\s*\.?\s*\(", t) and b["t"] in ("호", "문단") or b["t"] == "박스" and re.match(r"^[①-⑳]", t)):
                    on = False
                if on and b["t"] not in ("박스", "표", "그림") and "자동갱신" not in t:
                    out.append(t)
            return "세부보장", out
    for b in pa["blocks"]:
        t = b.get("text", "")
        if b["t"] in ("박스", "표", "그림") or "자동갱신" in t:
            continue
        out.append(t)
    return "지급사유", out


def judge(texts):
    """지급 문장이 있는 항마다 판정: 전부 미보상 → 미보상, 섞이면 세부보장별 상이, 없으면 보상"""
    verdicts, ev_no, ev_yes = [], None, None
    for t in texts:
        sents = SENT_SPLIT.split(t)
        bad = next((s for s in sents if PERIOD.search(s) and DIAG.search(s)), None)
        if bad:
            verdicts.append("미보상"); ev_no = ev_no or bad.strip()
        elif "지급" in t and PERIOD.search(t):
            verdicts.append("보상"); ev_yes = ev_yes or next((s for s in sents if PERIOD.search(s)), t).strip()
    if "미보상" in verdicts and "보상" in verdicts:
        return "세부보장별 상이", f"[보상] {ev_yes} / [미보상] {ev_no}"
    if "미보상" in verdicts:
        return "미보상", ev_no
    return "보상", (ev_yes or (texts[0] if texts else ""))


PROP = ("손해", "특수건물", "화재", "도난", "임시거주비", "복구비용", "임대료", "법률비용", "차액지원", "배상", "누출")
OUTPROD = ("펫퍼민트", "실손", "저축", "연금", "모아Rich")
for r in rows:
    if r["scope"] == "대상" and (any(k in r["cov"] for k in PROP) or (r["kind"] == "보통약관" and any(k in r["prod"] for k in OUTPROD))):
        r["scope"] = "범위 밖"
def user_code(cov):
    """사용자 결정(2026-11-03): 코드 미정 그룹 매칭"""
    if "통합입통원일당" in cov:
        return "COV000875" if "암중점치료기관" in cov else ("COV000874" if "요양병원입원포함" in cov else "")
    if "치매주요질환입원일당" in cov and "전환용" in cov:
        return "COV000865" if "요양병원제외" in cov else "COV000866"
    if "체증형,10년후2배지급" in cov:  # 프리미엄 건강보험 체증형은 별도 채번 없이 기본 진단비 코드 (25%체증형만 별도 코드)
        k = dkey(cov.replace("(체증형,10년후2배지급)", ""))
        return dk[k].most_common(1)[0][0] if k in dk else covname.get(k, "")
    return ""


res = []
for r in rows:
    if r["scope"] != "대상":
        res.append({**r, "pay": "", "ev": "", "code": "", "how": "", "proc": "범위 밖"})
        continue
    it = json.load(open(os.path.join(OUT, "web", "items", r["id"] + ".json"), encoding="utf-8"))
    where, texts = pay_blocks(it)
    if r["kind"] == "보통약관" and (where is None or any("위임" in t or "보장조항에서" in t for t in texts)):
        res.append({**r, "pay": "", "ev": "", "code": "", "how": "", "proc": "범위 밖(보통약관 지급사유 위임·없음)"})
        continue
    if where is None:
        pay, ev = "판정불가", "지급사유 조 못 찾음"
    else:
        pay, ev = judge(texts)
    if r["kind"] == "보통약관":
        first = texts[0] if texts else ""
        if "상해" in first.split("지급합니다")[0] or "화재" in first or ("상해" in ev and "질병" not in ev.replace("질병으로 인한 사망은 제외", "")):
            res.append({**r, "pay": pay, "ev": ev[:300], "code": "", "how": "", "proc": "범위 밖(보통약관 상해·재물)"})
            continue
        m = re.search(r"([^\s]+?)\s*으?로\s*지급합니다", first)
        r = {**r, "cov": m.group(1) if m else r["cov"]}  # 보통약관은 지급 담보명으로 코드 매칭
    k = dkey(r["cov"])
    code, how = "", ""
    if k in dk:
        code, how = dk[k].most_common(1)[0][0], "DATA 같은 키"
    elif k in covname:
        code, how = covname[k], "담보목록 이름 일치"
    elif user_code(r["cov"]):
        code, how = user_code(r["cov"]), "사용자 지정"
    res.append({**r, "pay": pay, "ev": ev[:1500], "where": where, "dkey": k, "affix": affix(r["cov"]), "code": code, "how": how})
for x in res:
    if x.get("code"):
        g = code_gubun.get(x["code"])
        if x["code"] in target:
            x["proc"] = "3-1 편입" + (" · 3-1→3-2 로 바뀜" if x["pay"] == "미보상" else "")
        elif g:
            x["proc"] = "다른 구분(" + g.most_common(1)[0][0] + ")"
        else:
            x["proc"] = "새 대표담보(담보목록 코드)"
    elif "proc" in x:
        pass
    else:
        x["proc"] = "코드 미정"
json.dump(res, open(os.path.join(D, "work", "new_judged.json"), "w"), ensure_ascii=False)
c = collections.Counter(x["proc"].split("(")[0].split(" ·")[0] for x in res)
print("새 상품담보", len(res), dict(c))
print("판정", collections.Counter(x["pay"] for x in res if x["pay"]))
print("코드 근거", collections.Counter(x["how"] for x in res if x.get("how")))
un = [x for x in res if x["proc"] == "코드 미정"]
print("코드 미정 담보 키 수", len({x["dkey"] for x in un}))
print("3-1 편입 대표담보", collections.Counter(x["code"] for x in res if x["proc"].startswith("3-1")).most_common(30))
