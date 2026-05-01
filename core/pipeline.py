from dataclasses import dataclass
from typing import Optional

from domain.enums import Stage, JobStatus
from domain.models import Job
from core.state_machine import validate_transition
from storage.repositories.jobs_repo import JobsRepository
from storage.repositories.episodes_repo import EpisodesRepository
from storage.repositories.assets_repo import AssetsRepository
from events.emitter import emitter
from app.logging import get_logger

logger = get_logger(__name__)

STAGE_ORDER = [Stage.FETCH, Stage.TRANSCRIBE, Stage.CAPTION, Stage.IMAGE]


@dataclass
class PipelineStatus:
    """Snapshot of an episode's current pipeline state."""
    episode_id: str
    completed_stages: list[Stage]
    pending_stages: list[Stage]
    active_job: Optional[Job]
    completion_level: int        # 0–4: how many stages are complete
    available_actions: list[str]


class Pipeline:
    """
    Coordinates stage sequencing and job lifecycle for a single episode.

    Rules:
    - Stages run in STAGE_ORDER sequence
    - A stage cannot start until the previous one has succeeded
    - Re-running a completed stage is allowed (idempotency check happens in the worker)
    - Interface layer calls only enqueue_* and get_status — never runs stages directly
    """

    def __init__(
        self,
        jobs_repo: JobsRepository,
        episodes_repo: EpisodesRepository,
        assets_repo: AssetsRepository,
    ):
        self._jobs = jobs_repo
        self._episodes = episodes_repo
        self._assets = assets_repo

    def enqueue_stage(self, episode_id: str, stage: Stage) -> Job:
        """Create a QUEUED job for a specific stage after validating prerequisites."""
        self._assert_prerequisites_met(episode_id, stage)
        job = self._jobs.create(episode_id, stage)
        emitter.emit("stage_queued", {"episode_id": episode_id, "stage": stage.value, "job_id": job.id})
        logger.info({"event": "stage_queued", "stage": stage.value, "episode_id": episode_id})
        return job

    def enqueue_full(self, episode_id: str) -> list[Job]:
        """Queue all four stages for unattended full-pipeline processing."""
        jobs = []
        for stage in STAGE_ORDER:
            job = self._jobs.create(episode_id, stage)
            jobs.append(job)
            emitter.emit("stage_queued", {"episode_id": episode_id, "stage": stage.value})
        logger.info({"event": "full_pipeline_queued", "episode_id": episode_id})
        return jobs

    def transition_job(self, job_id: str, new_status: JobStatus) -> Job:
        """Apply a validated status transition. Raises ValueError if illegal."""
        job = self._jobs.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        validate_transition(job.status, new_status)
        self._jobs.update_status(job_id, new_status)
        emitter.emit("job_status_changed", {
            "job_id": job_id,
            "from": job.status.value,
            "to": new_status.value,
        })
        return self._jobs.get_by_id(job_id)

    def get_status(self, episode_id: str) -> PipelineStatus:
        """Return a full status snapshot derived from the jobs table."""
        jobs = self._jobs.get_jobs_for_episode(episode_id)
        completed = self._get_completed_stages(jobs)
        pending = [s for s in STAGE_ORDER if s not in completed]
        active = next((j for j in jobs if j.status == JobStatus.RUNNING), None)

        return PipelineStatus(
            episode_id=episode_id,
            completed_stages=completed,
            pending_stages=pending,
            active_job=active,
            completion_level=len(completed),
            available_actions=self._derive_available_actions(completed, active),
        )

    def get_available_actions(self, episode_id: str) -> list[str]:
        """Convenience method — returns only the action list from get_status."""
        return self.get_status(episode_id).available_actions

    # ── Private helpers ──────────────────────────────────────────────────────

    def _get_completed_stages(self, jobs: list[Job]) -> list[Stage]:
        return [
            stage for stage in STAGE_ORDER
            if any(j.stage == stage and j.status == JobStatus.SUCCESS for j in jobs)
        ]

    def _assert_prerequisites_met(self, episode_id: str, stage: Stage) -> None:
        index = STAGE_ORDER.index(stage)
        if index == 0:
            return
        jobs = self._jobs.get_jobs_for_episode(episode_id)
        completed = self._get_completed_stages(jobs)
        for req in STAGE_ORDER[:index]:
            if req not in completed:
                raise ValueError(
                    f"Cannot enqueue {stage.value}: {req.value} has not completed successfully."
                )

    def _derive_available_actions(
        self, completed: list[Stage], active: Optional[Job]
    ) -> list[str]:
        if active:
            return ["view_progress"]

        if not completed:
            return ["fetch"]

        actions = []
        next_stage_map = {
            Stage.FETCH: "transcribe",
            Stage.TRANSCRIBE: "generate_captions",
            Stage.CAPTION: "create_image",
        }
        last = completed[-1]
        if last in next_stage_map:
            actions.append(next_stage_map[last])

        # Re-run actions for completed stages
        rerun_map = {
            Stage.FETCH: "re_fetch",
            Stage.TRANSCRIBE: "re_transcribe",
            Stage.CAPTION: "regenerate_caption",
            Stage.IMAGE: "regenerate_image",
        }
        for stage in completed:
            actions.append(rerun_map[stage])

        if len(completed) == len(STAGE_ORDER):
            actions.append("run_full_pipeline")

        return actions