import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal
from app.evaluation.metrics import recall_at_k
from app.retrieval.retriever import search_chunks


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _format_metrics(metrics_by_k: dict[int, float], ks: list[int]) -> str:
    return "  ".join(f"R@{k}={metrics_by_k[k]:.3f}" for k in ks)


def _snippet(text: str, limit: int = 60) -> str:
    flat = " ".join(text.split())
    return flat[:limit] + ("..." if len(flat) > limit else "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run retrieval evaluation")
    parser.add_argument(
        "--eval-file",
        default="examples/eval_items.example.json",
        help="Path to a JSON array of evaluation items",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        nargs="+",
        default=[5],
        help="One or more K values, e.g. --top-k 5 10 20",
    )
    parser.add_argument(
        "--dump",
        type=int,
        default=0,
        metavar="N",
        help="Print the top N retrieved chunks for every item",
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        default=None,
        help="Only evaluate the given item IDs",
    )
    args = parser.parse_args()

    ks = sorted(dict.fromkeys(args.top_k))
    max_k = ks[-1]
    items = json.loads(Path(args.eval_file).read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise SystemExit(f"{args.eval_file} must contain a JSON array")
    if args.ids:
        wanted = set(args.ids)
        items = [item for item in items if item.get("id") in wanted]

    overall: dict[int, list[float]] = defaultdict(list)
    by_split: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_category: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    evaluated = 0
    skipped = 0
    zero_hits = 0

    with SessionLocal() as db:
        for item in items:
            if not item.get("expected_sources"):
                skipped += 1
                print(f"{item.get('id', '?')} skipped (no expected sources)")
                continue

            retrieved = search_chunks(
                db,
                int(item["course_id"]),
                item["question"],
                top_k=max_k,
            )
            scores = {k: recall_at_k(item["expected_sources"], retrieved, k) for k in ks}
            split = item.get("split", "unspecified")
            category = item.get("category", "unspecified")
            evaluated += 1
            if scores[ks[0]] == 0:
                zero_hits += 1
            for k in ks:
                overall[k].append(scores[k])
                by_split[split][k].append(scores[k])
                by_category[category][k].append(scores[k])

            score_text = " ".join(f"R@{k}={scores[k]:.2f}" for k in ks)
            print(f"{item.get('id', '?')} [{split}/{category}] {score_text}")
            if args.dump:
                expected = ", ".join(
                    f"{source.get('document')} p{source.get('page')}"
                    for source in item["expected_sources"]
                )
                print(f"    expected: {expected}")
                for rank, result in enumerate(retrieved[: args.dump], start=1):
                    title = f" title={result.title!r}" if result.title else ""
                    print(
                        f"    #{rank} {result.document} p{result.page} "
                        f"score={result.score:.2f}{title} | {_snippet(result.text)}"
                    )

    if not evaluated:
        print("no items evaluated")
        return

    print()
    print(f"== Overall (n={evaluated}) ==")
    print(_format_metrics({k: _mean(overall[k]) for k in ks}, ks))
    print(f"zero-hit@{ks[0]}: {zero_hits}/{evaluated}")

    print()
    print("== By split ==")
    for split in sorted(by_split):
        n = len(by_split[split][ks[0]])
        print(f"{split} (n={n}): " + _format_metrics(
            {k: _mean(by_split[split][k]) for k in ks}, ks
        ))

    print()
    print("== By category ==")
    for category in sorted(by_category):
        n = len(by_category[category][ks[0]])
        print(f"{category} (n={n}): " + _format_metrics(
            {k: _mean(by_category[category][k]) for k in ks}, ks
        ))

    if skipped:
        print()
        print(f"skipped={skipped} (items without expected sources)")


if __name__ == "__main__":
    main()
