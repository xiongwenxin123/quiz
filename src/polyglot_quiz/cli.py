from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from .models import QuizRequest
from .pipeline import QuizPipeline, QuizQualityError
from .providers import OpenAICompatibleProvider, ProviderError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="polyglot-quiz",
        description="Generate a grounded EN/JA/ES learning quiz from text or a URL.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="Generate a quiz from a JSON request")
    generate.add_argument("request", type=Path, help="Path to a QuizRequest JSON file")
    generate.add_argument("-o", "--output", type=Path, help="Output path (default: stdout)")
    schema = subparsers.add_parser("schema", help="Print the request JSON schema")
    schema.add_argument("-o", "--output", type=Path, help="Output path (default: stdout)")
    return parser


def _write(value: str, output: Path | None) -> None:
    if output:
        output.write_text(value + "\n", encoding="utf-8")
    else:
        print(value)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "schema":
        _write(json.dumps(QuizRequest.model_json_schema(), ensure_ascii=False, indent=2), args.output)
        return 0

    try:
        request = QuizRequest.model_validate_json(args.request.read_text(encoding="utf-8"))
        provider = OpenAICompatibleProvider.from_env()
        package = QuizPipeline(provider).generate(request)
        _write(package.model_dump_json(indent=2), args.output)
        return 0
    except (OSError, ValidationError, ProviderError, QuizQualityError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
