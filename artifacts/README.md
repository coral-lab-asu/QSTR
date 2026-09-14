# Artifact policy

Generated datasets, model responses, evaluation logs, notebooks, and paper
figures are experiment artifacts. Keep them outside the source tree or in
external artifact storage when they are large.

Every retained artifact should include:

- QSTR commit
- command and configuration
- input dataset/checksum
- model/provider
- random seed
- timestamp

Do not commit API keys or raw provider responses that contain credentials.
