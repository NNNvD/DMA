# Branch Management and Cleanup

This repository now treats `main` as the single source of truth. To consolidate work and delete side branches, run the following locally (requires a clean working tree):

1. Ensure you have all branches and the latest `main`:
   ```bash
   git fetch --all --prune
   git checkout main
   git pull origin main --ff-only
   ```
2. For each feature branch you want to merge:
   ```bash
   git checkout <branch-name>
   git rebase main
   git checkout main
   git merge --no-ff <branch-name>
   git push origin main
   git push origin --delete <branch-name>
   ```
3. If a branch should be retained temporarily (e.g., long-running work), keep pushing it regularly so protections stay current.

Repository settings also now delete branches automatically after pull requests are merged to `main`, which helps keep only the primary branch around.
