# ZEN AI Router

Routing-only prototype for a campus assistant (Microsoft Innovate 2026, Problem Statement 18 "One Front Door for Everything").
It does not answer questions. It takes one student message (English or Hinglish), splits it into topics, picks a campus
domain for each topic, scores confidence, and decides: answer, clarify, handoff or refuse.

## Rules (must follow)

- Domains: IT, FEES, ACADEMICS, HOSTEL, CAMPUS_SERVICES, OUT_OF_SCOPE. Actions: answer, clarify, handoff, refuse.
- data/test_set.csv and data/simulated_v1.csv are TEST data. Never use them to write prompts, pick examples, choose keywords or tune thresholds. Only data/dev_set.csv may be used for tuning. Never copy any test question text into code, prompts or examples.
- Never invent or hand-edit results. Every number must come from a file in results/.
- Every LLM and embedding call goes through the cached provider in zenai/providers.py.

## Layout

- `zenai/`: router package
- `evaluation/`: testing agent (evaluator, baselines, tuning); `python -m evaluation.check_data` validates data/
- `tests/`: pytest
- `data/`: datasets, do not edit
- `results/`: run outputs, one folder per run, committed to git
- `.cache/`: LLM/embedding response cache, gitignored
- `config.yaml`: provider, kNN, confidence weights, thresholds
