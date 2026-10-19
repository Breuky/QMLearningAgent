import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal
from app.evaluation.metrics import recall_at_k
from app.retrieval.retriever import search_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Run retrieval evaluation")
    parser.add_argument(
        "--eval-file",
        default="examples/eval_items.example.json",
        help="Path to a JSON array of evaluation items",
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    items = json.loads(Path(args.eval_file).read_text(encoding="utf-8"))
    scores: list[float] = []
    skipped = 0

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
                top_k=args.top_k,
            )
            score = recall_at_k(
                item.get("expected_sources", []),
                retrieved,
                args.top_k,
            )
            scores.append(score)
            print(f"{item.get('id', '?')} Recall@{args.top_k}={score:.2f}")

    if scores:
        print(f"mean Recall@{args.top_k}={sum(scores) / len(scores):.3f}")
    if skipped:
        print(f"skipped={skipped} (items without expected sources)")


if __name__ == "__main__":
    main()
