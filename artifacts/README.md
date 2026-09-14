# Artifact policy

Generated datasets, model responses, evaluation logs, notebooks, and paper
figures are experiment artifacts. Keep them outside the source tree or in
external artifact storage when they are large.

The published cricket snapshot under `data/data_final/` is a versioned
exception, covered by `data/MANIFEST.sha256`. New runs go in `artifacts/runs/`.

Compact synthetic outputs imported from `naman_syn_data` are retained under
`pipelines/synthetic_data/synData/` as provenance fixtures. New runs belong in
`artifacts/runs/`, which is ignored by Git.

Every retained artifact should include:

- QSTR commit
- command and configuration
- input dataset/checksum
- model/provider
- random seed
- timestamp

Do not commit API keys or raw provider responses that contain credentials.
