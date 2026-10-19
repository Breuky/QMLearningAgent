import argparse
from pathlib import Path

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a document through the API")
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--file", required=True)
    args = parser.parse_args()

    path = Path(args.file)
    with path.open("rb") as handle:
        response = requests.post(
            f"{args.api_base.rstrip('/')}/api/courses/{args.course_id}/documents",
            files={"file": (path.name, handle)},
            timeout=120,
        )

    print(response.status_code)
    print(response.text)
    response.raise_for_status()


if __name__ == "__main__":
    main()
