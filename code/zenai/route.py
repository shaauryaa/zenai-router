"""CLI: python -m zenai.route "message" [--json]"""
import argparse
import sys
import textwrap

from .router import Router


def print_table(result) -> None:
    rows = [("#", "topic", "LLM", "kNN (share)", "conf", "action")]
    for i, t in enumerate(result.topics, 1):
        rows.append((str(i), textwrap.shorten(t.text, 42), t.llm_domain or "-",
                     f"{t.knn_domain} ({t.knn_share:.2f})", f"{t.confidence:.2f}", t.action))
    widths = [max(len(r[c]) for r in rows) for c in range(len(rows[0]))]
    for n, row in enumerate(rows):
        print("  ".join(cell.ljust(w) for cell, w in zip(row, widths)))
        if n == 0:
            print("  ".join("-" * w for w in widths))
    for i, t in enumerate(result.topics, 1):
        nbrs = ", ".join(f"{n.id} {n.domain} {n.similarity:.2f}" for n in t.neighbours[:3])
        print(f"\n[{i}] request_type={t.request_type}  agree={t.agree}  auto_routed={t.auto_routed}")
        print(textwrap.fill(f"reason: {t.reason}", 100, subsequent_indent="    "))
        print(f"top-3 neighbours: {nbrs}")
    print(f"\nMESSAGE -> action={result.action}  primary={result.primary_domain}  "
          f"secondary={result.secondary_domain}  auto_routed={result.auto_routed}  "
          f"({result.model}, {result.latency_ms:.0f} ms)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Route one student message.")
    parser.add_argument("message")
    parser.add_argument("--json", action="store_true", help="print the full RouteResult as JSON")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    router = Router()
    result = router.route(args.message)
    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print_table(result)
    print(f"provider: {router.provider.stats()}", file=sys.stderr)


if __name__ == "__main__":
    main()
