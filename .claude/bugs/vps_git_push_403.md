---
name: VPS git push 403 error
description: VPS 上 weekly_review.py git push 失敗，GitHub HTTPS auth 被拒
status: open
found: 2026-04-06
file: daily-advisor/weekly_review.py (git_push function)
---

## 問題

VPS 手動跑 `weekly_review.py --prepare` 時，JSON 產出成功但 git push 失敗：
```
remote: Permission to huansbox/mlb-fantasy.git denied to huansbox.
fatal: unable to access 'https://github.com/huansbox/mlb-fantasy.git/': The requested URL returned error: 403
```

## 影響

- weekly_review.py 的 `git_push()` 會 commit + push JSON 到 GitHub
- push 失敗 = JSON 留在 VPS 本地但不會同步到 GitHub
- 不影響資料產出和分析，但其他機器（Mac）無法直接 git pull 拿到 JSON

## 可能原因

- GitHub Personal Access Token (PAT) 過期
- VPS 使用 HTTPS remote 而非 SSH（`git remote -v` 確認）
- PAT 權限不足

## 確認步驟

```bash
ssh root@107.175.30.172
cd /opt/mlb-fantasy
git remote -v                    # 確認 remote URL（HTTPS or SSH）
git config credential.helper     # 確認 credential 儲存方式
cat ~/.git-credentials           # 如果用 store helper，查 token
```

## 修復方向

1. **如果是 PAT 過期**：重新產生 PAT 並更新 VPS credential
2. **如果是 HTTPS**：考慮改用 SSH remote（`git remote set-url origin git@github.com:huansbox/mlb-fantasy.git`），用 deploy key 不會過期
3. **定期維護**：如果繼續用 PAT，需記錄過期日並定期更新

## 臨時解法

目前用 `scp` 從 VPS 拉 JSON 到本機，不影響工作流程。
