import argparse
import io
import os
import sys

_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Appended, not inserted: this must not take precedence over the standard
# library, or a stray module in the parent directory would shadow it.
if _parent not in sys.path and os.path.isdir(os.path.join(_parent, "release_notes")):
    sys.path.append(_parent)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from release_notes.ado_client import ADOClient
from release_notes.generator import export, generate_all


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate software release notes from Azure DevOps and GitLab data."
    )
    parser.add_argument(
        "release_id",
        type=int,
        help="Azure DevOps Release ID to generate notes for.",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "html", "csv", "all"],
        default="all",
        help="Output format(s) (default: all).",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print to stdout instead of exporting to file.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use the bundled mock release instead of Azure DevOps.",
    )
    args = parser.parse_args()

    try:
        client = ADOClient(use_mock=args.mock)
    except ValueError as exc:
        parser.error(str(exc))

    if args.stdout:
        if args.format == "all":
            print("note: --stdout with --format all only prints markdown; use --format markdown|html|csv to be explicit.", file=sys.stderr)
        try:
            md, html, csv_content, _ = generate_all(args.release_id, ado_client=client)
        except (NotImplementedError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        if args.format == "html":
            sys.stdout.write(html)
        elif args.format == "csv":
            sys.stdout.write(csv_content)
        else:
            sys.stdout.write(md)
        return

    formats: list[str] = []
    if args.format == "all":
        formats = ["md", "html", "csv"]
    elif args.format == "html":
        formats = ["html"]
    elif args.format == "csv":
        formats = ["csv"]
    else:
        formats = ["md"]

    try:
        md_path, html_path, csv_path = export(args.release_id, ado_client=client)
    except (NotImplementedError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    for fmt in formats:
        if fmt == "md":
            print(f"Exported to {md_path}")
        elif fmt == "html":
            print(f"Exported to {html_path}")
        elif fmt == "csv":
            print(f"Exported to {csv_path}")


if __name__ == "__main__":
    main()
