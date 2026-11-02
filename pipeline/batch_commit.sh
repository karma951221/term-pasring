#!/usr/bin/env bash
# 남은 PDF 중 작은 것부터 N개 처리 → 색인·보고서 갱신 → 커밋·푸시 (중간 결과 보존용)
# 사용: bash pipeline/batch_commit.sh <N> [jobs]
set -e
cd "$(dirname "$0")/.."
N=${1:-10}; J=${2:-4}
python3 pipeline/run.py extract --jobs "$J" --batch "$N" | tail -n +1 | grep -E "FAILED|완료|처리 대상" || true
python3 pipeline/run.py index
python3 pipeline/report.py
DONE=$(ls out/work | grep -cE '^p[0-9a-f]{8}\.json$')
git add out pipeline
git commit -qm "Parse batch: ${DONE}/98 PDFs done

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018KnErD2ZQJoPKDHsXqw2W6"
for i in 1 2 3 4 5; do git push -q origin HEAD 2>/dev/null && break; sleep $((2**i)); done
echo "pushed ${DONE}/98"
