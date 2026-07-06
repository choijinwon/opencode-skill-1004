import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from common.project_analyzer import build_report, print_model_list, print_text, print_verbose_text, select_project


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an MLflow model project using the skill pack checklist.")
    parser.add_argument("--project", help="model project path. If omitted, the script auto-selects a candidate.")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON output")
    parser.add_argument("--list", action="store_true", help="print model/sample choices")
    parser.add_argument("--verbose", action="store_true", help="print detailed analysis checks")
    parser.add_argument("--no-write-check", action="store_true", help="skip temporary write permission check")
    parser.add_argument("--strict-exit", action="store_true", help="return non-zero when checks contain warn/block statuses")
    args = parser.parse_args()

    project, reason = select_project(args.project)
    report = build_report(project, reason, write_check=not args.no_write_check)
    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    elif args.list:
        print_model_list(report)
    elif args.verbose:
        print_verbose_text(report)
    else:
        print_text(report)

    if args.strict_exit:
        if any(check.status == "block" for check in report.checks):
            return 2
        if any(check.status == "warn" for check in report.checks):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
