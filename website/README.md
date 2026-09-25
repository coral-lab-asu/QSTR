# Q-STR research website

A dependency-free, static research site based on the **refined, named-author
manuscript**, not the anonymous submission. No API keys, analytics, external
fonts, framework build, or model calls are needed.

## Preview

From the QSTR root:

```bash
python -m http.server 8080 --bind 127.0.0.1 --directory website
```

Open <http://localhost:8080>. Use an HTTP server rather than opening the HTML
with `file://`, because the results explorer loads `results.json` with fetch.

## Contents and evidence

- `index.html`: research narrative, illustrative task example, findings,
  authors, resources, limitations, and provisional manuscript citation.
- `styles.css`: responsive styling with reduced-motion and focus support.
- `app.js`: example switcher, results filters, full table, and citation copy.
- `results.json`: 18 transcribed model–strategy rows from manuscript Table 3.
- `assets/qstr-paper.pdf`: unchanged copy of
  `QSTR_paper/QSTR_refined_EACL/latex/acl_latex.pdf` supplied by the authors.

Paper sections supporting the main findings:

| Website claim | Manuscript evidence |
| --- | --- |
| Coverage / controlled sizes | §4.4–4.5, Table 1 |
| PK recovery versus exact table match | §6, Table 3 |
| RowCoT cell accuracy | §6.2, Table 3 |
| Execution pressure and weighted RMSE | §7.5, Appendix E |
| Output pressure and undercounting | §7.5, Appendix F |
| Generation and validation | §4, Appendix B |

The hero cricket example is invented for explanation and explicitly marked as
an illustration, not an observed match, dataset item, or model prediction.
All model performance is manuscript-reported, not a new experiment.
The full suite applies only to Llama and Qwen; closed models have two strategies.
Neither the number of CSVs nor current preparation output is substituted for
the paper's benchmark population.

## Release checks before public launch

The site documents, rather than silently resolves, outstanding release issues:

- The manuscript's 620 source matches versus 638 released CSVs.
- The controlled split was not found in tracked release artifacts.
- Historical ground-truth mismatches and missing provenance/license details.
- No confirmed archival venue, DOI, or publication year for the citation.

Do not label the paper accepted at a venue without author confirmation. Update
the site and citation when authoritative publication details are available.
When updating the paper, check PDF page anchors and result values together.

## Deployment

The organization repository is <https://github.com/coral-lab-asu/QSTR>.
Research code and data live on `main`; this site is maintained on the separate
`website` branch, created from `main`. Site changes should be committed and
pushed to `website`, not merged into `main` unless that layout is intentional.

The `website/` directory is the complete deployable artifact. It uses relative
asset paths, so it works at a domain root or a GitHub Pages project subpath.
Upload its contents to a static host, or use a GitHub Pages Actions deployment
that uploads `website/` as the Pages artifact. No deployment or repository
settings changes are performed automatically. Deploying the public site is a
separate step requiring approval.

For GitHub Pages, use an Actions deployment checking out the `website` branch
and uploading its `website/` directory. The branch-based Pages selector cannot
publish an arbitrary `website/` subfolder (it offers root or `docs/`). The
expected project URL is `https://coral-lab-asu.github.io/QSTR/` after deployment;
creating the branch alone does not publish a live website.

## Checks

```bash
python -m pytest -q tests/test_website.py
node --check website/app.js
```

The tests check local links, duplicate IDs, result dimensions and key reported
values, and the included PDF. Browser checks should additionally exercise
both example views, both strategy filters, all metric selections, citation
copying, and horizontal overflow at phone and desktop widths.

Initial verification: all 72 numeric values in the 18 results rows matched
the manuscript's LaTeX table. Headless Chrome checks passed for the example
switcher, strategy selection, RMSE selection, citation copy/selection fallback,
and results loading with no JavaScript exceptions. No page-level horizontal
overflow was found at 320, 390, 768, and 1440 pixel widths. The PDF copy has
SHA-256 `d9b4d0ec473a13a16942792a998ddfaa6c77d9c48ba05fed896726123555151c`.
