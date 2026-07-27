# Manual Gates

Human verification checkpoints. Fill in Result after running each gate.

## Wake gate
- Date:
- Tester:
- Result:  # PASS / FAIL — run: `python scripts/manual_wake_test.py`
- Threshold used: 0.5
- Notes: Automation (Task 2A) shipped; physical sign-off recommended before kitchen use.

## STT gate
- Date:
- Tester:
- Result:  # PASS / FAIL — run: `python scripts/manual_stt_test.py`
- Utterance 1 (expect 鸡蛋):
- Transcript 1:
- Utterance 2 (expect 米饭):
- Transcript 2:
- Notes: Automation (Task 3A) shipped; needs `STT_API_KEY`.

## E2E kitchen gate
- Date:
- Tester:
- Result:  # PASS / FAIL — run: `smart-speaker`
- Checklist:
  - [ ] hey jarvis → cue
  - [ ] log lunch eggs → confirmed
  - [ ] remaining kcal from MCP numbers
  - [ ] dinner advice cites summary
- Notes:
