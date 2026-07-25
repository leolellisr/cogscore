from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


BenchmarkName = Literal[
    "sensory_buffer",
    "attention_posner",
    "motivation",
    "learning",
]

RunMode = Literal["vnc", "headless"]


class HealthResponse(BaseModel):
    status: str
    project: str
    storage_root: str


class JobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    input_json: str
    output_json: str | None = None
    log_path: str | None = None
    error_message: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None


class ArchitectureResponse(BaseModel):
    id: str
    name: str
    version: str
    author: str | None = None
    interface_type: str
    status: str
    storage_path: str
    image_tag: str | None = None
    manifest_json: str
    created_at: str
    validated_at: str | None = None
    error_message: str | None = None


class UploadArchitectureResponse(BaseModel):
    ok: bool
    architecture_id: str
    validation_job_id: str
    message: str


class RunExperimentRequest(BaseModel):
    architecture_id: str
    benchmark: BenchmarkName = "sensory_buffer"
    scene: str | None = None
    episodes: int = Field(default=1, ge=1)
    mode: RunMode = "vnc"
    seed: int = Field(default=777, ge=0)

    # Sensory parameters
    trials_per_delay: int = Field(default=3, ge=1)
    delays_ms: list[int] = Field(
        default_factory=lambda: [0, 50, 100, 220, 500, 1000]
    )
    resolution: int = Field(default=64, ge=8)
    patch_size: int = Field(default=8, ge=1)

    # Attention Posner parameters
    posner_experiments: list[int] = Field(
        default_factory=lambda: [1, 2, 3, 4, 5]
    )
    trials_per_experiment: int = Field(default=20, ge=1)
    map_width: int = Field(default=32, ge=8)
    map_height: int = Field(default=32, ge=8)
    cycles_per_trial: int = Field(default=30, ge=1)

    # Motivation parameters
    motivation_experiments: list[int] = Field(
        default_factory=lambda: [1, 2, 3, 4, 5]
    )
    cycles_per_motivation_trial: int = Field(default=30, ge=1)

    # Learning parameters used for online experiment execution.
    # These fields do not define the uploaded result-bundle layout.
    learning_stages: list[str] = Field(
        default_factory=lambda: [
            "Substage1",
            "Substage2",
            "Substage3",
            "Substage4",
            "Substage5",
        ]
    )
    learning_tests: list[str] = Field(
        default_factory=lambda: ["testA", "testB", "testAB"]
    )
    steps_per_episode: int = Field(default=100, ge=1)
    aggregate_n: int = Field(default=5, ge=1)

    @model_validator(mode="after")
    def validate_benchmark_specific_fields(self) -> "RunExperimentRequest":
        if self.benchmark == "sensory_buffer":
            if not self.delays_ms:
                raise ValueError("delays_ms must contain at least one delay")
            if any(delay < 0 for delay in self.delays_ms):
                raise ValueError("delays_ms cannot contain negative values")

        elif self.benchmark == "attention_posner":
            if not self.posner_experiments:
                raise ValueError("posner_experiments cannot be empty")
            invalid = sorted(set(self.posner_experiments) - {1, 2, 3, 4, 5})
            if invalid:
                raise ValueError(f"invalid Posner experiment ids: {invalid}")

        elif self.benchmark == "motivation":
            if not self.motivation_experiments:
                raise ValueError("motivation_experiments cannot be empty")
            invalid = sorted(set(self.motivation_experiments) - {1, 2, 3, 4, 5})
            if invalid:
                raise ValueError(f"invalid motivation experiment ids: {invalid}")

        elif self.benchmark == "learning":
            if not self.learning_stages:
                raise ValueError("learning_stages cannot be empty")
            if not self.learning_tests:
                raise ValueError("learning_tests cannot be empty")

        return self


class RunExperimentResponse(BaseModel):
    ok: bool
    run_id: str
    job_id: str
    message: str


class ReplotRequest(BaseModel):
    benchmark: BenchmarkName | Literal["all"] = "all"


class ReplotJobResponse(BaseModel):
    benchmark: BenchmarkName
    job_id: str


class ReplotResponse(BaseModel):
    ok: bool
    message: str
    jobs: list[ReplotJobResponse]


class ExperimentRunResponse(BaseModel):
    id: str
    architecture_id: str
    benchmark: BenchmarkName
    scene: str | None = None
    status: str
    parameters_json: str
    result_path: str | None = None
    job_id: str | None = None
    created_at: str
    finished_at: str | None = None
    error_message: str | None = None


class ResultBundleParameters(BaseModel):
    seed: int | None = None
    x_points: int = Field(default=50, ge=2)
    smooth_window: int = Field(default=7, ge=1)
    episodes: int | None = Field(default=None, ge=1)
    trials_per_experiment: int | None = Field(default=None, ge=1)
    aggregate_n: int | None = Field(default=None, ge=1)


class ResultBundleSource(BaseModel):
    type: str = "uploaded_results"
    author: str | None = None
    notes: str | None = None


class ResultBundleManifest(BaseModel):
    agent_name: str = Field(min_length=1)
    architecture_name: str = Field(min_length=1)
    benchmark: BenchmarkName
    benchmark_version: str = Field(min_length=1)
    cogscore_version: str = Field(min_length=1)
    run_name: str = Field(min_length=1)
    date: str
    parameters: ResultBundleParameters = Field(default_factory=ResultBundleParameters)
    source: ResultBundleSource = Field(default_factory=ResultBundleSource)

    # Learning-specific metadata. Optional for backward compatibility.
    result_layout: str | None = None
    experiments: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_learning_manifest(self) -> "ResultBundleManifest":
        if self.benchmark == "learning":
            expected = "benchmark_out/AGENT/EXPERIMENT"
            if self.result_layout not in {None, expected}:
                raise ValueError(
                    f"learning result_layout must be '{expected}', "
                    f"got '{self.result_layout}'"
                )
            if not self.experiments:
                raise ValueError(
                    "learning manifest must list at least one experiment"
                )
        return self


class ImportedResultRunResponse(BaseModel):
    id: str
    benchmark: BenchmarkName
    agent_name: str
    run_name: str
    result_path: str
    status: str


class UploadResultsResponse(BaseModel):
    ok: bool
    message: str
    run: dict
    job: dict
    warnings: list[str] = Field(default_factory=list)


class RetryJobResponse(BaseModel):
    ok: bool
    source_job_id: str
    job_id: str
    message: str


class RetryExperimentRunResponse(BaseModel):
    ok: bool
    source_run_id: str
    run_id: str
    job_id: str
    message: str


class SimulatorControlRequest(BaseModel):
    action: Literal["start", "stop", "restart"]
    scene: str | None = None


class SimulatorControlResponse(BaseModel):
    ok: bool
    job_id: str
    message: str
