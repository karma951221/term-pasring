"""최종 산출물: 기왕증_보상_트리거분류.md / .tsv (+ 표 4 TSV)  — classify.py · judge_new.py 다음에 실행"""
import collections, json, os, re
D = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(D, "work")
rows = json.load(open(os.path.join(W, "rows.json"), encoding="utf-8"))
dec = json.load(open(os.path.join(W, "decisions.json"), encoding="utf-8"))
NJ = json.load(open(os.path.join(W, "new_judged.json"), encoding="utf-8"))
X = json.load(open(os.path.join(W, "xlsx.json"), encoding="utf-8"))
cname = {c["code"]: c["name"] for c in X["covlist"]}
CL = {"A": "A 검토대상", "B": "B 기왕증 무관", "C": "C 확인 필요"}
# 3-1 편입 상품담보 수
add = collections.Counter(x["code"] for x in NJ if x["proc"].startswith("3-1"))
for r in rows:
    r["new"] = "N"; r["how"] = "DATA"
    if add[r["code"]]:
        r["n"] += add[r["code"]]
        r["note"] = (r["note"] + " · " if r["note"] else "") + f"10/31 신규 상품담보 +{add[r['code']]}"
# 10/31 신규 대표담보(판매 고지유형 전부 보상 또는 세부보장별 상이)
NEWC = {
    "COV000876": ("T4+T2", "검사 + 주요치료·재활치료 세부보장", "A", "통합치료비 결정 적용"),
    "COV000871": ("T2", "질병 또는 상해로 수술(1-5종, 체증형)", "A", "수술비Ⅱ(1-5종)과 같은 문형"),
    "COV000877": ("T3+T2", "장기요양 판정 후 재가·시설급여 · 질병 요양병원 입원", "A", "사용자 결정"),
    "COV000878": ("T3+T2", "장기요양 판정 후 재가·시설급여 · 질병 요양병원 입원", "A", "사용자 결정"),
    "COV000879": ("T1+T3", "치매또는파킨슨질환 진단확정 + 장기요양 판정", "A", "사용자 결정"),
    "COV000880": ("T1+T3", "치매또는파킨슨질환 진단확정 + 장기요양 판정", "A", "사용자 결정"),
    "COV000633": ("T2", "질병으로 사망", "A", ""),
    "COV000634": ("T2", "질병으로 사망", "A", ""),
    "COV000717": ("T2", "질병 또는 상해 치료 목적 창상봉합술", "A", "「진단된 질병 또는 상해의 치료를 목적으로」"),
    "COV000695": ("T6+T2", "상해 골절 · 질병 또는 상해 치료 목적 도수정복술", "A", "사용자 결정"),
    "COV000466": ("T7", "구급차 이용 응급실 내원(중증도 등급)", "B", "응급실 결정 적용"),
    "COV000603": ("T3", "공적 판정(중증외상 산정특례 등록)", "B", "T3 기본 분류 · 기존 UNRELATED(산정특례) 전례"),
    "COV000614": ("T3", "공적 판정(중증화상 산정특례 등록)", "B", "T3 기본 분류 · 기존 UNRELATED(산정특례) 전례"),
}
for code, (tc, td, cls, nt) in NEWC.items():
    xs = [x for x in NJ if x.get("code") == code]
    ev = next((x["ev"] for x in xs if x["pay"] == "보상"), xs[0]["ev"] if xs else "")
    ev = re.sub(r"^\[보상\]\s*", "", ev).split(" / [미보상]")[0]
    pays = collections.Counter(x["pay"] for x in xs)
    note = [nt] if nt else []
    if pays.get("세부보장별 상이"):
        note.append(f"세부보장별 상이 {pays['세부보장별 상이']}건(질병 세부보장 미보상)")
    note.append("담보목록 코드(이전 조사 DATA에 없음)")
    rows.append({"code": code, "name": cname.get(code, ""), "n": len(xs), "tcode": tc, "tdesc": td, "cls": cls,
                 "ev": ev[:260] + ("…" if len(ev) > 260 else ""), "note": " · ".join(note), "new": "Y", "how": "담보목록 이름 일치"})
order = {"A": 0, "C": 1, "B": 2}
rows.sort(key=lambda r: (order[r["cls"]], r["code"]))
TN = {"T1": "질병 진단", "T2": "질병 원인 사망·입원·수술·치료", "T3": "공적 판정·결정", "T4": "검사 시행", "T5": "출생·신생아 상태",
      "T6": "상해 사고", "T7": "의료 이용 사건", "T8": "치아 치료", "T9": "기타"}
old = [r for r in rows if r["new"] == "N"]; new = [r for r in rows if r["new"] == "Y"]
cc = collections.Counter(r["cls"] for r in rows); cn = collections.Counter()
for r in rows: cn[r["cls"]] += r["n"]
tcount = collections.Counter(r["tcode"] for r in rows)
L = ["# 기왕증 보상(3-1) 대표담보 트리거 분류", "",
     "> 작성 2026-11-03 · 입력 `기왕증_보상_트리거분류_입력.md`(3-1 대표담보 80 · 상품담보 383 · 원문 211묶음) + 10/31 판매 약관 98개(§5 신규 담보).",
     "> 판정 규칙(「보험기간 중 + 진단확정」)은 그대로 두고, 그 규칙을 적용할 **대상인지**만 지급사유 트리거로 가렸다.", "",
     "## 요약", "",
     f"- 대상: 기존 3-1 대표담보 {len(old)}개 · 상품담보 {sum(r['n'] for r in old)}건(10/18 383 + 10/31 신규 편입 {sum(add.values())}) · 10/31 신규 대표담보 {len(new)}개 · 상품담보 {sum(r['n'] for r in new)}건", "",
     "| 분류 | 대표담보(기존 · 신규) | 상품담보 |", "|---|---:|---:|"]
for k in "ACB":
    L.append(f"| {CL[k]} | {cc[k]} ({sum(1 for r in old if r['cls']==k)} · {sum(1 for r in new if r['cls']==k)}) | {cn[k]} |")
L += ["", "| 트리거 | 대표담보 |", "|---|---:|"] + [f"| {k} {' + '.join(TN[t] for t in k.split('+'))} | {v} |" for k, v in sorted(tcount.items())]
L += ["", "## 표 1 — 대표담보 단위 (A → C → B, 코드순)", "",
      "| 대표담보코드 | 대표담보명 | 상품담보 수 | 트리거 | 분류 | 트리거 근거(원문 인용, 한 문장) | 비고 |", "|---|---|---:|---|---|---|---|"]
for r in rows:
    ev = r["ev"].replace("|", "\\|")
    L.append(f"| {r['code']} | {r['name']}{' `신규`' if r['new']=='Y' else ''} | {r['n']} | {r['tcode']} {r['tdesc']} | {CL[r['cls']]} | 「{ev}」 | {r['note']} |")
L += ["", "## 표 2 — 사용자 결정 목록", "", "| 질문 | 답 | 적용한 대표담보 |", "|---|---|---|"]
for q, a, cs, _ in dec:
    L.append(f"| {q} | {a} | {', '.join(cs)} |")
L += ["| (10/31 신규 · 코드) 프리미엄 건강보험 「…진단비(체증형,10년후2배지급)」 코드 | 체증형은 별도 채번하지 않고 기본 진단비 코드 사용 (25%체증형만 별도 코드) | COV000220 · 217 · 215 · 218 · 786 · 190 · 197 · 176 |",
      "| (10/31 신규 · 코드) 암 통합입통원일당(직접치료…) 2종 · 간병인사용 치매주요질환입원일당(…, 전환용) 2종 코드 | **명시 답 없음** — 제안대로 적용, 확인 필요 | 874(요양병원입원포함) · 875(암중점치료기관) · 865(plus, 요양병원제외) · 866(요양병원) |", ""]
L += ["## 표 3 — 상품담보별로 트리거가 갈린 대표담보", "",
      "없음. 같은 대표담보 안의 원문 묶음은 고지 접사 · 조 번호 · 금액 표만 다르고 트리거 문장은 같았다.",
      "참고로 10/31 신규 장기요양돌봄지원금 4종(COV000877~880)은 트리거는 같고 **보상여부**만 고지유형별로 갈린다. 355Ⅱ간편은 ④ 「질병의 치료를 목적으로 요양병원 입원」(보상), 일반심사는 「진단확정된 질병의 치료를 목적으로」(④만 미보상).", ""]
# 표 4
L += ["## 표 4 — 10/31 신규 상품담보 전체", "",
      f"이전 조사 DATA 의 (상품명, 상품담보명)에 없는 10/31 약관 상품담보 {len(NJ)}건. 근거 문장은 120자까지. 같은 내용 TSV: `기왕증_신규상품담보.tsv`.", ""]
pc = collections.Counter(x["proc"].split("(")[0].split(" ·")[0] for x in NJ)
L += ["| 처리 | 건수 |", "|---|---:|"] + [f"| {k} | {v} |" for k, v in pc.most_common()] + [""]
L += ["| 상품명 | 상품담보명 | 고지 접사 | 보상여부 | 근거 문장 | 대표담보코드 | 코드 근거 | 처리 |", "|---|---|---|---|---|---|---|---|"]
ordp = {"3-1 편입": 0, "새 대표담보": 1, "다른 구분": 2, "범위 밖": 3}
def pk(x):
    return (ordp.get(x["proc"].split("(")[0].split(" ·")[0], 9), x.get("code") or "", x["prod"])
T4 = []
for x in sorted(NJ, key=pk):
    proc = x["proc"]
    if proc.startswith("새 대표담보"):
        proc = "3-1 신규 대표담보(표 1)" if x["code"] in NEWC else "새 대표담보 · 고지유형별 미보상 포함(3-1 아님)"
    ev = (x.get("ev") or "").replace("|", "\\|").replace("\n", " ")
    T4.append([x["prod"], x["cov"], x.get("affix", ""), x.get("pay", ""), ev, x.get("code", ""), x.get("how", ""), proc])
    L.append("| " + " | ".join([x["prod"], x["cov"], x.get("affix", ""), x.get("pay", ""), ev[:120] + ("…" if len(ev) > 120 else ""),
                                  x.get("code", ""), x.get("how", ""), proc]) + " |")
L += ["", "## 표 5 — 임시 채번 목록", "", "없음. 코드가 안 붙던 담보는 사용자 결정에 따라 모두 기존 코드에 맞췄다(표 2).", ""]
L += ["## 방법 메모", "",
      "- §1~§4: 입력 묶음의 지급사유 원문(항·호)으로 트리거를 정했다. 근거 문장은 입력 원문에서 그대로 인용했다.",
      "- §5: 10/31 약관 98개를 배경 음영 수정 후 다시 파싱한 결과를 썼다. 새 상품담보는 상품명(버전 숫자 · 무배당 · 고지유형 접미 무시)과 상품담보명으로 DATA 와 맞췄다.",
      "- §5 보상여부: 지급사유 조(세부보장 위임이면 「N.(보험금의 지급사유)」 소절)의 항마다 「보험기간 중」과 진단확정(진단확정 · 진단받 · 진단되)이 한 문장에 있으면 미보상. 항별 결과가 섞이면 「세부보장별 상이」(이전 조사의 4.세부보장별 상이와 같은 뜻). 박스 · 표 · 「자동갱신」 항은 제외.",
      "- 범위 밖: 상해 · 비용손해 · 재물손해 · 배상책임 · 반려동물 · 실손 담보와, 지급사유가 상해·재물이거나 저축·연금인 보통약관.", ""]
open(os.path.join(D, "기왕증_보상_트리거분류.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
with open(os.path.join(D, "기왕증_보상_트리거분류.tsv"), "w", encoding="utf-8") as f:
    f.write("대표담보코드\t대표담보명\t분류(A/B/C)\t트리거코드\t트리거설명\t근거문장\t비고\t신규(Y/N)\t코드근거\n")
    for r in rows:
        f.write("\t".join([r["code"], r["name"], r["cls"], r["tcode"], r["tdesc"], r["ev"].replace("\t", " "), r["note"], r["new"], r["how"]]) + "\n")
with open(os.path.join(D, "기왕증_신규상품담보.tsv"), "w", encoding="utf-8") as f:
    f.write("상품명\t상품담보명\t고지접사\t보상여부\t근거문장\t대표담보코드\t코드근거\t처리\n")
    for t in T4:
        f.write("\t".join(str(v).replace("\t", " ").replace("\n", " ") for v in t) + "\n")
print("대표담보", len(rows), dict(cc), "상품담보", dict(cn), "· 표4", len(T4), dict(pc))
