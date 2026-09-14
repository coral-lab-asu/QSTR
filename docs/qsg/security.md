# Security and reproducibility

- API keys are supplied through environment variables such as
  `GEMINI_API_KEY`; they must not appear in source, notebooks, or artifacts.
- If a key has ever been committed, revoke/rotate it with the provider before
  reusing the repository.
- A history scan found the old key in three historical QSG commits, including
  the current `naman-exp` tip. Removing those historical blobs requires a
  coordinated history rewrite and force-update; it is intentionally not done
  automatically because the QSG worktree contains unrelated uncommitted work.
- Keep local `.env` files untracked.
- Run commands from the repository root or pass explicit paths; do not rely on
  machine-specific absolute paths.
- Every generated artifact should record commit, command, seed, input paths,
  model/provider, and timestamp.
