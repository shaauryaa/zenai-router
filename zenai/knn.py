"""Signal B: k-nearest-neighbour vote over the labelled examples in data/examples.jsonl."""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import DATA
from .schemas import Neighbour


@dataclass
class KNNResult:
    domain: str
    shares: dict[str, float]  # fraction of the k neighbours per domain
    neighbours: list[Neighbour]  # most similar first

    def share(self, domain: str | None) -> float:
        return self.shares.get(domain, 0.0) if domain else 0.0


def vote(neighbours: list[Neighbour]) -> KNNResult:
    """Majority domain among neighbours; ties broken by summed similarity."""
    counts: dict[str, int] = {}
    sims: dict[str, float] = {}
    for n in neighbours:
        counts[n.domain] = counts.get(n.domain, 0) + 1
        sims[n.domain] = sims.get(n.domain, 0.0) + n.similarity
    winner = max(counts, key=lambda d: (counts[d], sims[d]))
    shares = {d: c / len(neighbours) for d, c in counts.items()}
    return KNNResult(domain=winner, shares=shares, neighbours=neighbours)


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.where(norms == 0, 1, norms)


class KNNIndex:
    def __init__(self, provider, k: int, examples_path: Path = DATA / "examples.jsonl"):
        with open(examples_path, encoding="utf-8") as f:
            self.examples = [json.loads(line) for line in f if line.strip()]
        self.provider = provider
        self.k = min(k, len(self.examples))
        vectors = provider.embed([e["text"] for e in self.examples])
        self.matrix = _normalize(np.array(vectors, dtype=float))

    def query_many(self, texts: list[str]) -> list[KNNResult]:
        """One embedding request for all texts, then a cosine-similarity vote for each."""
        queries = _normalize(np.array(self.provider.embed(texts), dtype=float))
        results = []
        for sims in queries @ self.matrix.T:
            top = np.argsort(-sims, kind="stable")[: self.k]
            neighbours = [Neighbour(id=self.examples[i]["id"], domain=self.examples[i]["domain"],
                                    similarity=round(float(sims[i]), 4)) for i in top]
            results.append(vote(neighbours))
        return results
