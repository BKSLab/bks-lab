"""Safe durable collection and exact-version analysis progress."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


CollectionState = Literal["queued", "running", "completed", "failed", "cancelled"]


class AnalysisBlockedReasons(BaseModel):
    missing_llm: int = Field(default=0, ge=0, description="Versions awaiting LLM configuration.", examples=[0])
    paused: int = Field(default=0, ge=0, description="Versions awaiting automatic backlog resume.", examples=[0])
    insufficient_text: int = Field(default=0, ge=0, description="Versions without enough retained text.", examples=[0])
    unavailable: int = Field(default=0, ge=0, description="Removed, duplicate, superseded or skipped versions.", examples=[0])


class CollectionAnalysisStatus(BaseModel):
    scope: Literal["new_updated"] = Field(default="new_updated", description="Only new or updated observed content versions.", examples=["new_updated"])
    total: int = Field(default=0, ge=0, description="Distinct observed versions in scope.", examples=[8])
    queued: int = Field(default=0, ge=0, description="Runnable queued analysis versions.", examples=[2])
    running: int = Field(default=0, ge=0, description="Versions currently being analyzed.", examples=[1])
    completed: int = Field(default=0, ge=0, description="Versions with a saved analysis.", examples=[4])
    failed: int = Field(default=0, ge=0, description="Versions with a terminal failed or cancelled attempt.", examples=[0])
    blocked: int = Field(default=0, ge=0, description="Versions that cannot currently be analyzed.", examples=[1])
    pending: int = Field(default=0, ge=0, description="Schedulable versions not yet queued by the bounded backlog pass.", examples=[0])
    blocked_reasons: AnalysisBlockedReasons = Field(default_factory=AnalysisBlockedReasons, description="Mutually exclusive blocked-version counts.")


class CollectionCounters(BaseModel):
    sources_total: int = Field(default=0, ge=0, description="Durable collection target count.", examples=[6])
    sources_done: int = Field(default=0, ge=0, description="Sources with a terminal collection state, including failures.", examples=[3])
    sources_queued: int = Field(default=0, ge=0, description="Sources awaiting collection.", examples=[2])
    sources_running: int = Field(default=0, ge=0, description="Sources currently being collected.", examples=[1])
    sources_completed: int = Field(default=0, ge=0, description="Successfully collected sources.", examples=[3])
    sources_failed: int = Field(default=0, ge=0, description="Sources with a failed or cancelled collection.", examples=[0])
    new: int = Field(default=0, ge=0, description="New stored materials.", examples=[5])
    updated: int = Field(default=0, ge=0, description="Updated stored materials.", examples=[2])
    unchanged: int = Field(default=0, ge=0, description="Unchanged retained materials; no implied model work.", examples=[10])
    skipped: int = Field(default=0, ge=0, description="Skipped collection candidates.", examples=[1])
    warnings: int = Field(default=0, ge=0, description="Safe collection warning count.", examples=[0])


class CollectionSourceStatus(BaseModel):
    source_slug: str = Field(description="Stable source address captured for this collection.", examples=["example"])
    source_name: str = Field(description="Source display name.", examples=["Example"])
    status: CollectionState = Field(description="Latest attempt state for this source in the selected job.", examples=["running"])
    new: int = Field(default=0, ge=0, description="New stored materials.", examples=[0])
    updated: int = Field(default=0, ge=0, description="Updated stored materials.", examples=[0])
    unchanged: int = Field(default=0, ge=0, description="Unchanged retained materials.", examples=[0])
    skipped: int = Field(default=0, ge=0, description="Skipped collection candidates.", examples=[0])
    warnings: int = Field(default=0, ge=0, description="Collection warnings.", examples=[0])
    analysis: CollectionAnalysisStatus = Field(default_factory=CollectionAnalysisStatus, description="Exact-version analysis of new and updated materials.")
    error: str | None = Field(default=None, description="Safe collection failure or warning.", examples=[None])


class CollectionJobStatus(BaseModel):
    slug: str = Field(description="Stable selected collection job address.", examples=["all-sources-2026-10-15-080000"])
    status: CollectionState = Field(description="Durable collection queue state.", examples=["completed"])
    source_slug: str | None = Field(description="Source scope, or null for all selected sources.", examples=[None])
    source_name: str | None = Field(description="Scoped source display name.", examples=[None])
    created_at: datetime = Field(description="Queue creation time.")
    started_at: datetime | None = Field(description="Latest worker acquisition time.")
    completed_at: datetime | None = Field(description="Collection terminal time, independent of analysis.")
    error: str | None = Field(description="Safe collection job error.", examples=[None])


class CollectionStatus(BaseModel):
    job: CollectionJobStatus | None = Field(default=None, description="Selected active or most relevant recent collection.")
    busy: bool = Field(default=False, description="Collection or runnable analysis still has work; blocked versions do not imply activity.", examples=[True])
    collection: CollectionCounters = Field(default_factory=CollectionCounters, description="Latest source attempts, without counting retries twice.")
    analysis: CollectionAnalysisStatus = Field(default_factory=CollectionAnalysisStatus, description="Aggregated exact-version analysis counters.")
    sources: list[CollectionSourceStatus] = Field(default_factory=list, description="Selected job targets and their collection and analysis state.")
    active_jobs: int = Field(default=0, ge=0, description="All queued or running collection jobs, including other manual requests.", examples=[1])
