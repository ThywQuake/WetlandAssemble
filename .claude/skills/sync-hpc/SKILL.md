---
name: sync-hpc
description: Sync codes to HPC cluster
disable-model-invocation: true
---

## Steps
1. Open another terminal and run `cd ~/Code/WA`
2. Run `bash .claude/skills/sync-hpc/sync_up.sh` to sync codes to HPC cluster
3. Verify the sync by checking the logs in the terminal, usually it should show `sent xx bytes` and `received xx bytes` after the sync is complete.
4. If there are any errors, tell me and let me run the sync manually.

