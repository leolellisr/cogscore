#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

import yaml


def safe_slug(value: str) -> str:
    cleaned = "".join(
        ch if ch.isalnum() or ch in {"_", "-", "."} else "_"
        for ch in str(value).strip()
    )
    cleaned = "_".join(part for part in cleaned.split("_") if part)

    if not cleaned:
        return "unnamed"

    return cleaned


def zip_directory(source_dir: Path, output_zip: Path) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            if path.is_file():
                arcname = path.relative_to(source_dir)
                zf.write(path, arcname)


def create_manifest(args: argparse.Namespace) -> dict[str, Any]:
    parameters: dict[str, Any] = {
        "seed": args.seeds[0],
        "seeds": args.seeds,
        "x_points": args.x_points,
        "smooth_window": args.smooth_window,
    }

    if args.episodes is not None:
        parameters["episodes"] = args.episodes

    if args.trials_per_experiment is not None:
        parameters["trials_per_experiment"] = args.trials_per_experiment

    return {
        "agent_name": args.agent_name,
        "architecture_name": args.architecture_name,
        "benchmark": args.benchmark,
        "benchmark_version": args.benchmark_version,
        "cogscore_version": args.cogscore_version,
        "run_name": args.run_name,
        "date": args.date,
        "parameters": parameters,
        "source": {
            "type": "uploaded_results",
            "author": args.author,
            "notes": args.notes,
        },
    }


def create_bundle(args: argparse.Namespace) -> Path:
    benchmark_out = args.benchmark_out.resolve()

    if not benchmark_out.exists():
        raise FileNotFoundError(f"benchmark_out folder not found: {benchmark_out}")

    if not benchmark_out.is_dir():
        raise NotADirectoryError(f"benchmark_out is not a directory: {benchmark_out}")

    if benchmark_out.name != "benchmark_out":
        print(
            "[WARN] The input folder is not named benchmark_out. "
            "It will still be copied as benchmark_out inside the bundle."
        )

    output_zip = args.output.resolve()

    temp_dir = Path(tempfile.mkdtemp(prefix="cogscore_make_bundle_"))

    try:
        bundle_root = temp_dir / "bundle"
        bundle_root.mkdir(parents=True, exist_ok=True)

        manifest = create_manifest(args)

        manifest_path = bundle_root / "manifest.yaml"
        with manifest_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                manifest,
                f,
                sort_keys=False,
                allow_unicode=True,
            )

        destination_benchmark_out = bundle_root / "benchmark_out"

        if args.benchmark == "learning":
            # Learning comparisons require the hierarchy:
            # benchmark_out / AGENT / EXPERIMENT / ... / nrewards.txt
            #
            # The supplied --benchmark-out directory normally contains the
            # experiment folders directly (for example Te1/ and Te2/).  Place
            # those folders below the agent name without changing the bundle
            # format used by the other benchmarks.
            nrewards_files = sorted(benchmark_out.rglob("nrewards.txt"))

            if not nrewards_files:
                raise ValueError(
                    "Learning benchmark_out does not contain any nrewards.txt files: "
                    f"{benchmark_out}"
                )

            experiment_names = sorted(
                {
                    path.relative_to(benchmark_out).parts[0]
                    for path in nrewards_files
                    if len(path.relative_to(benchmark_out).parts) >= 2
                }
            )

            if not experiment_names:
                raise ValueError(
                    "Could not infer learning experiment folders. Expected paths like "
                    "EXPERIMENT/seed/profile/nrewards.txt inside --benchmark-out."
                )

            agent_dir = destination_benchmark_out / safe_slug(args.agent_name)
            shutil.copytree(benchmark_out, agent_dir)

            manifest["result_layout"] = "benchmark_out/AGENT/EXPERIMENT"
            manifest["experiments"] = experiment_names

            # Rewrite the manifest after adding learning-specific metadata.
            with manifest_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(
                    manifest,
                    f,
                    sort_keys=False,
                    allow_unicode=True,
                )

            print(
                "[INFO] Learning bundle layout: "
                f"benchmark_out/{safe_slug(args.agent_name)}/<experiment>/..."
            )
            print(f"[INFO] Learning experiments: {', '.join(experiment_names)}")
        else:
            shutil.copytree(benchmark_out, destination_benchmark_out)

        optional_dir = bundle_root / "optional"
        optional_dir.mkdir(exist_ok=True)

        notes_path = optional_dir / "notes.md"
        notes_path.write_text(args.notes + "\n", encoding="utf-8")

        zip_directory(bundle_root, output_zip)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return output_zip


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a CogScore result_bundle.zip from an existing benchmark_out folder."
    )

    parser.add_argument(
        "--benchmark-out",
        type=Path,
        required=True,
        help="Path to existing benchmark_out folder.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output zip path.",
    )

    parser.add_argument(
        "--agent-name",
        required=True,
        help="Agent name, e.g., Substage1 or Substage3.",
    )

    parser.add_argument(
        "--architecture-name",
        default="CONAIM",
        help="Architecture name.",
    )

    parser.add_argument(
        "--benchmark",
        required=True,
        choices=["motivation", "attention_posner", "sensory_buffer", "learning"],
        help="Benchmark name.",
    )

    parser.add_argument(
        "--benchmark-version",
        required=True,
        help="Benchmark version, e.g., motivation_v1 or posner_v1.",
    )

    parser.add_argument(
        "--cogscore-version",
        default="0.1.0",
        help="CogScore version or git reference.",
    )

    parser.add_argument(
        "--run-name",
        required=True,
        help="Human-readable run name.",
    )

    parser.add_argument(
        "--date",
        default=str(date.today()),
        help="Run date in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--episodes",
        type=int,
        default=None,
        help="Number of episodes.",
    )

    parser.add_argument(
        "--trials-per-experiment",
        type=int,
        default=None,
        help="Number of trials per experiment.",
    )


    parser.add_argument(
        "--seed",
        "--seeds",
        dest="seeds",
        type=int,
        action="append",
        required=True,
        help=(
            "Random seed. Use --seed once or repeat --seed/--seeds "
            "to record multiple seeds."
        ),
    )

    parser.add_argument(
        "--x-points",
        type=int,
        default=50,
        help="Plot x-points.",
    )

    parser.add_argument(
        "--smooth-window",
        type=int,
        default=7,
        help="Plot smoothing window.",
    )

    parser.add_argument(
        "--author",
        default="Leonardo",
        help="Author/source name.",
    )

    parser.add_argument(
        "--notes",
        default="Imported from existing local CogScore results.",
        help="Notes for this result bundle.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    output_zip = create_bundle(args)

    print(f"[OK] Created result bundle: {output_zip}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
