"""Every filesystem location the project uses, in one place.

Layout (repo root first):
    .env, .cache/, .data/       local secrets, LLM/embedding cache, runtime state (all git-ignored)
    code/                       Python packages, config.yaml, config/, kb/, static/, web/, tests/
    test-data/                  datasets (dev_set.csv, test_set.csv, examples.jsonl, simulated_*.csv) and results/
    docs/                       API.md, RETRIEVAL.md, POLICY.md
    prompts/                    prompt versions (v1/ .. v4/, final/)
"""
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]  # code/
REPO_ROOT = CODE.parent

# code/
CONFIG_FILE = CODE / "config.yaml"
CONFIG_DIR = CODE / "config"
KB = CODE / "kb"
STATIC = CODE / "static"
KB_SEARCH_CACHE = CODE / ".cache" / "kb_search"  # helpdesk BM25 index (git-ignored by the `.cache/` rule)

# test-data/
TEST_DATA = REPO_ROOT / "test-data"
DATA = TEST_DATA  # the datasets that used to live in data/
RESULTS = TEST_DATA / "results"

# docs/ and prompts/
DOCS = REPO_ROOT / "docs"
POLICY = DOCS / "POLICY.md"
PROMPTS = REPO_ROOT / "prompts"

# repo root, git-ignored
ENV_FILE = REPO_ROOT / ".env"
CACHE = REPO_ROOT / ".cache"  # also the base for relative cache paths in config.yaml (kb.local_dir)
RUNTIME = REPO_ROOT / ".data"
