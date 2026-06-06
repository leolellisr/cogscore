from __future__ import annotations

import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ALLOWED_BENCHMARKS = {
    "motivation",
    "attention_posner",
    "sensory_buffer",
    "learning",
}

CURRENTLY_SUPPORTED_BENCHMARKS = {
    "motivation",
    "attention_posner",
}

REQUIRED_MANIFEST_FIELDS = [
    "agent_name",
    "architecture_name",
    "benchmark",
    "benchmark_version",
    "cogscore_version",
    "run_name",
    "date",
    "parameters",
    "source",
]

COMMON_CSV_PATTERNS = [
    "*_summary_episode_*.csv",
    "*_per_trial_episode_*.csv",
    "*_java_steps_*.csv",
]

MOTIVATION_RECOMMENDED_FILES = [
    "motivation_marta_trials.txt",
]


@dataclass
class BundleValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]
    manifest: dict[str, Any] | None
    root: Path | None
    temp_dir: Path | None
    file_counts: dict[str, int]


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        raise ValueError("manifest.yaml is empty")

    if not isinstance(data, dict):
        raise ValueError("manifest.yaml must contain a YAML object")

    return data


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            errors.append(f"Missing required manifest field: {field}")

    benchmark = manifest.get("benchmark")

    if benchmark is not None and benchmark not in ALLOWED_BENCHMARKS:
        errors.append(
            f"Invalid benchmark '{benchmark}'. "
            f"Allowed values: {', '.join(sorted(ALLOWED_BENCHMARKS))}"
        )

    if benchmark in ALLOWED_BENCHMARKS and benchmark not in CURRENTLY_SUPPORTED_BENCHMARKS:
        errors.append(
            f"Benchmark '{benchmark}' is reserved but not currently supported by this MVP."
        )

    parameters = manifest.get("parameters")
    if parameters is not None and not isinstance(parameters, dict):
        errors.append("Manifest field 'parameters' must be an object")

    source = manifest.get("source")
    if source is not None and not isinstance(source, dict):
        errors.append("Manifest field 'source' must be an object")

    return errors


def count_matching_files(folder: Path, patterns: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}

    for pattern in patterns:
        counts[pattern] = len(list(folder.glob(pattern)))

    return counts


def validate_benchmark_out(root: Path, manifest: dict[str, Any]) -> tuple[list[str], list[str], dict[str, int]]:
    errors: list[str] = []
    warnings: list[str] = []

    benchmark_out = root / "benchmark_out"

    if not benchmark_out.exists():
        return ["Missing required folder: benchmark_out/"], warnings, {}

    if not benchmark_out.is_dir():
        return ["benchmark_out exists but is not a directory"], warnings, {}

    counts = count_matching_files(benchmark_out, COMMON_CSV_PATTERNS)
    total_csvs = sum(counts.values())

    if total_csvs == 0:
        errors.append(
            "benchmark_out/ must contain at least one recognized CSV file: "
            + ", ".join(COMMON_CSV_PATTERNS)
        )

    benchmark = manifest.get("benchmark")

    if benchmark == "motivation":
        for filename in MOTIVATION_RECOMMENDED_FILES:
            if not (benchmark_out / filename).exists():
                warnings.append(
                    f"Recommended motivation file not found: benchmark_out/{filename}"
                )

    return errors, warnings, counts


def check_zip_safety(zip_path: Path) -> list[str]:
    errors: list[str] = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            p = Path(member)

            if p.is_absolute():
                errors.append(f"Unsafe absolute path in zip: {member}")

            if ".." in p.parts:
                errors.append(f"Unsafe parent path in zip: {member}")

    return errors


def extract_zip_to_temp(zip_path: Path) -> tuple[Path, Path]:
    temp_dir = Path(tempfile.mkdtemp(prefix="cogscore_bundle_"))

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(temp_dir)

    entries = [p for p in temp_dir.iterdir()]

    if (temp_dir / "manifest.yaml").exists():
        return temp_dir, temp_dir

    if len(entries) == 1 and entries[0].is_dir() and (entries[0] / "manifest.yaml").exists():
        return entries[0], temp_dir

    return temp_dir, temp_dir


def validate_result_bundle(path: Path) -> BundleValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    manifest: dict[str, Any] | None = None
    root: Path | None = None
    temp_dir: Path | None = None
    file_counts: dict[str, int] = {}

    if not path.exists():
        return BundleValidationResult(
            valid=False,
            errors=[f"Path does not exist: {path}"],
            warnings=[],
            manifest=None,
            root=None,
            temp_dir=None,
            file_counts={},
        )

    if path.is_file():
        if path.suffix.lower() != ".zip":
            return BundleValidationResult(
                valid=False,
                errors=["Input file must be a .zip file"],
                warnings=[],
                manifest=None,
                root=None,
                temp_dir=None,
                file_counts={},
            )

        safety_errors = check_zip_safety(path)

        if safety_errors:
            return BundleValidationResult(
                valid=False,
                errors=safety_errors,
                warnings=[],
                manifest=None,
                root=None,
                temp_dir=None,
                file_counts={},
            )

        root, temp_dir = extract_zip_to_temp(path)

    elif path.is_dir():
        root = path
        temp_dir = None

    else:
        return BundleValidationResult(
            valid=False,
            errors=[f"Input path is neither file nor directory: {path}"],
            warnings=[],
            manifest=None,
            root=None,
            temp_dir=None,
            file_counts={},
        )

    manifest_path = root / "manifest.yaml"

    if not manifest_path.exists():
        return BundleValidationResult(
            valid=False,
            errors=["Missing required file: manifest.yaml"],
            warnings=warnings,
            manifest=None,
            root=root,
            temp_dir=temp_dir,
            file_counts={},
        )

    try:
        manifest = load_manifest(manifest_path)
    except Exception as exc:
        return BundleValidationResult(
            valid=False,
            errors=[f"Could not read manifest.yaml: {exc}"],
            warnings=warnings,
            manifest=None,
            root=root,
            temp_dir=temp_dir,
            file_counts={},
        )

    errors.extend(validate_manifest(manifest))

    benchmark_errors, benchmark_warnings, file_counts = validate_benchmark_out(root, manifest)

    errors.extend(benchmark_errors)
    warnings.extend(benchmark_warnings)

    return BundleValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        manifest=manifest,
        root=root,
        temp_dir=temp_dir,
        file_counts=file_counts,
    )
