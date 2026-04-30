"""Command-line entry point.

Example:

    python -m charter_parser charter.pdf --first-page 6 --last-page 39 \\
        --output clauses.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from charter_parser.llm_client import (
    DEFAULT_MODEL,
    ClauseExtractionError,
    extract_clauses,
)
from charter_parser.pdf_extractor import extract_pages


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="charter_parser",
        description="Extract numbered clauses from a maritime charter party PDF.",
    )
    p.add_argument("pdf", type=Path, help="Path to the input PDF.")
    p.add_argument(
        "--first-page",
        type=int,
        default=6,
        help="First page of Part II (1-indexed, inclusive). Default: 6.",
    )
    p.add_argument(
        "--last-page",
        type=int,
        default=39,
        help="Last page of Part II (1-indexed, inclusive). Default: 39.",
    )
    p.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("clauses.json"),
        help="Where to write the JSON output. Default: ./clauses.json",
    )
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Claude model id. Default: {DEFAULT_MODEL}.",
    )
    p.add_argument(
        "--dump-text",
        type=Path,
        help="If set, also write the cleaned PDF text to this path (useful for debugging).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _build_parser().parse_args(argv)

    if not args.pdf.is_file():
        print(f"error: {args.pdf} is not a file", file=sys.stderr)
        return 2
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "error: ANTHROPIC_API_KEY is not set. Put it in a .env file or "
            "export it before running.",
            file=sys.stderr,
        )
        return 2

    print(
        f"Extracting text from {args.pdf} pages {args.first_page}-{args.last_page}...",
        file=sys.stderr,
    )
    text = extract_pages(args.pdf, first=args.first_page, last=args.last_page)

    if args.dump_text:
        args.dump_text.write_text(text, encoding="utf-8")
        print(f"  wrote cleaned text to {args.dump_text}", file=sys.stderr)

    print(f"Calling {args.model} to extract clauses...", file=sys.stderr)
    try:
        clauses = extract_clauses(text, model=args.model)
    except ClauseExtractionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    payload = [c.model_dump() for c in clauses]
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(payload)} clauses to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
