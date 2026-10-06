# Results changelog

Changes that affect how results in this folder should be read. Results files themselves are never edited.

## 2026-09-27: commit history rewritten (commit messages only)

The commit messages on branch `router-core-and-eval` were reworded, which gave every commit a new hash.
No file changed: each rewritten commit has exactly the same tree (file contents) as the original.

`run_meta.json` files and `test_runs.log` recorded the original hashes. Use this table to find the code
a run was made with:

| original commit | rewritten commit | tree (identical for both) | subject |
|---|---|---|---|
| `08e1d06` | `4ff771b` | `10222d0` | Add routing core, testing agent and first dev run |
| `9541e71` | `63a9daf` | `69661cf` | Update data provenance: team drafted and verified |
| `d6ef095` | `428e225` | `d2d8646` | Freeze thresholds tuned on dev |
| `e8833c1` | `53360ff` | `c56ccbf` | Add frozen-config dev, test and simulated runs |

So the dev, test and simulated runs that record `d6ef095622` were made with the code in `428e225`.
Check with `git rev-parse 428e225^{tree}` (prints `d2d8646...`).

## 2026-10-06: v1 dev run reproduced after adding the Azure provider (`20261006-190504_dev`)

`config.yaml` gained a `providers.azure` block and `zenai/providers.py` gained an Azure provider, `chat_text` and an
embedding-size check. Routing code, thresholds, prompts and data did not change, and the default provider is still
Gemini, so v1 cache keys are unchanged (`tests/test_providers_azure.py` pins two of them).

`20261006-190504_dev` re-ran the dev evaluation with `--baselines` from the cache: 0 API calls, 175 cache hits, and
`predictions.csv` equals `20260927-032739_dev` on every column except `latency_ms`. Its `config_sha256` differs from
the older run only because `config.yaml` gained the `providers` block. Its `run_meta.json` says `dirty: true` because
it ran on top of commit `c0b3b48` before the Azure changes were committed. The v1 numbers to quote remain those of the
runs made on 2026-09-27.
