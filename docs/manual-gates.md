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

## Remote MCP gate
- Date:
- Tester:
- Result:  # PASS / FAIL — run: `python scripts/manual_mcp_log_food.py --name 鸡蛋 --pieces 2 --meal 午`
- Needs: `MCP_HEALTH_URL` + `MCP_HEALTH_TOKEN` (user1)
- Notes: `log_food` then `get_day` should show the new entry on the remote server.

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
