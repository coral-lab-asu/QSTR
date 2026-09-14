# Data policy

QSTR code expects source tables and datasets to be supplied through explicit
paths. The original workspace contained large cricket/soccer corpora under
QSG and CMT2; they are not copied into the initial repository commit.

Recommended local layout:

```text
data/raw/cricket/
data/raw/soccer/
data/generated/
```

Record the source location, checksum, schema version, and licensing status in
the run manifest for any experiment that uses local data.
