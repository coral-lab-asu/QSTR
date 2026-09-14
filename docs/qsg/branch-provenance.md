# Branch and artifact provenance

This document records the repository state used for the knowledge-transfer
refactor. Generated results are evidence of experiments, not replacements for
the code that produced them.

| Reference | Commit | Role |
| --- | --- | --- |
| `main` | `403415273216d36ea33e3028602847a0a62c2c55` | Common baseline |
| `origin/naman-exp` | `11b69bcf66f7f649c030baa2465770ee38163915` | Experimental/results line |
| `origin/naman_syn_data` | `a8b00566e273f93912aa8cb7994d2bb0ae506be6` | Synthetic-data line |

At the start of the refactor, the checked-out QSG worktree was on branch
`Ritam`, pointing at the `naman-exp` commit, with pre-existing uncommitted
changes to results, datasets, evaluation code, and analysis scripts. Those
changes must remain user-owned and must not be reset or overwritten.

## Branch relationship

The two requested refs are not incremental variants of one implementation.
`naman-exp` contains the large baseline and result tree. `naman_syn_data`
removes most baseline artifacts and adds `synData/`, session transcripts, and
synthetic experiment records. Reconciliation therefore requires a deliberate
merge of capabilities, not a blind branch merge.

## Artifact policy

- Source, configuration, schemas, tests, and runbooks belong in version control.
- Raw datasets may be retained locally or tracked according to size and
  licensing constraints.
- Generated results should carry a run manifest containing commit, seed,
  inputs, model, and command.
- Temporary files, caches, logs, and credentials must never be treated as
  canonical source artifacts.
