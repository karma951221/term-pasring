# term-pasring

메리츠 공시용 통합약관 PDF를 **상품 × 항목** 단위로 잘라 **조 › 항 › 호 › 목** 구조의 JSON으로 만든 결과물과 파이프라인.
방법은 `통합약관_파싱_매뉴얼.md`, 지시는 `통합약관_파싱_클라우드프롬프트.md` 를 따른다. 규칙 기반(PyMuPDF)만 쓰고 OCR·LLM 호출은 없다.

## 결과물

| 경로 | 내용 |
|---|---|
| `out/web/index.json` | 상품(주계약 98 · 독립특약 86)과 항목 색인 |
| `out/web/items/<id>.json` | 항목별 구조화 본문 (`head` + `arts[].blocks[]`, 모든 블록에 `p,c,y0,y1`) |
| `out/work/plan.json` | 목차 파싱 · 항목 · 경계 · 독립특약 소유 PDF |
| `out/work/p<hash>.json` | PDF별 항목 범위 · 통계 · QA 결과 · 이슈 |
| `out/work/report.md` | 통계 · 확인 필요 목록 · PDF별 표 · 입력 중복 |
| `out/work/issues.json` | 확인 필요 전체 목록 |
| `terms_out.zip` | `out/` 전체 압축본 |

## 실행

```bash
pip install pymupdf pillow
python pipeline/run.py plan                  # ① 목차 + ② 항목·경계
python pipeline/run.py extract --jobs 4      # ③ 본문 구조화 (완료한 PDF는 건너뜀)
python pipeline/run.py index                 # ④ 색인 + 이슈
python pipeline/report.py                    # 보고서
python pipeline/qa.py <파일명 일부>           # 상품 1개 QA
python pipeline/dump_item.py <item_id> [줄수] # 사람이 읽는 덤프
python pipeline/export_md.py [상품명 일부]    # (선택) 항목별 markdown → out/md/
bash pipeline/batch_commit.sh <N> [jobs]     # 남은 PDF N개 처리 후 커밋·푸시
```

입력 PDF는 `input/` 에 둔다. 다른 위치면 환경변수 `TERMS_SRC` 로 지정한다.

## 매뉴얼과 다르게 처리한 점

- 항 기호 정규식에서 줄머리 `-` 는 항으로 보지 않는다. 이 약관에서 `-` 는 글머리표이고 항 기호는 PUA `U+F000` 이다.
- 표지 제목에 '보통약관'이 없는 주계약(저축보험 3종)은 관(`제N관`)이 있는 첫 묶음을 보통약관으로 본다.
- 특별약관 목차가 번호 대신 `■`·원문자로 나열된 경우(연금저축 노후생활지킴이보험)는 그 줄을 특별약관 항목으로 본다.
- 원문 단 이미지(매뉴얼 §4.5)는 만들지 않았다.
