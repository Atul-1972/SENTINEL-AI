"""One-command practical demonstration; all generated files stay in assessment/."""

import argparse
from pathlib import Path

from assessment.prepare_demo import prepare_demo
from assessment.workflow import ASSESSMENT, run_workflow, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Use the clearly labelled historical replay.")
    parser.add_argument("--new-data", type=Path, help="Your incoming labelled CSV.")
    parser.add_argument("--gate-data", type=Path, help="Separate labelled holdout, never used for candidate fitting.")
    parser.add_argument("--batch-origin", choices=["historical_replay", "new_labelled_batch"])
    args = parser.parse_args()
    if args.demo:
        if args.new_data or args.gate_data or args.batch_origin:
            parser.error("--demo cannot be combined with manual input arguments.")
        incoming, holdout = prepare_demo()
        origin = "historical_replay"
    else:
        if not all((args.new_data, args.gate_data, args.batch_origin)):
            parser.error("Use --demo or supply --new-data, --gate-data and --batch-origin.")
        incoming, holdout, origin = args.new_data, args.gate_data, args.batch_origin
    report = run_workflow(incoming, holdout, origin=origin)
    write_json(ASSESSMENT / "runs/latest.json", {
        "run_id": report["run_id"], "directory": report["output_directory"],
        "status": report["status"], "decision": report["quality_gate"]["decision"],
    })
    print(f"\nOpen: {Path(report['output_directory']) / 'report.html'}")
    print("Gate rejection is a valid completed assessment outcome; the champion remains active.")


if __name__ == "__main__":
    main()
