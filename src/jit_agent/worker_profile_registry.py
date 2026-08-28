"""Application-owned registry for bounded transient worker execution profiles.

Capabilities describe *what* Prometheist can do. Worker profiles describe *how*
one bounded execution role is performed. A capability resolves to a private root
worker profile; composite deterministic workers may in turn invoke narrow LLM
workers. LLM workers never discover or address arbitrary worker implementations.

The registry also owns each LLM role's information aperture. ``project_packet``
constructs the minimum task-specific packet from broader application state, while
``validate_packet`` rejects missing or unexpected fields. Persona access is an
explicit response-surface privilege rather than a generic model instruction.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
import hashlib
from typing import Any, Mapping

from jit_agent.capability_registry import DEFAULT_REGISTRY, CapabilityRegistry


WORKER_PROFILE_REGISTRY_VERSION = "worker-profile-registry-v1"
PRIMARY_OLLAMA_MODEL_POOL = "ollama-primary"


class WorkerExecutionMode(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"


class PersonaAccess(str, Enum):
    FORBIDDEN = "FORBIDDEN"
    REQUIRED = "REQUIRED"


@dataclass(frozen=True, slots=True)
class WorkerPacketContract:
    """Closed, minimum-necessary model/application packet contract."""

    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        required = tuple(value.strip() for value in self.required_fields)
        optional = tuple(value.strip() for value in self.optional_fields)
        if any(not value for value in (*required, *optional)):
            raise ValueError("worker packet fields must not be blank")
        if len(required) != len(set(required)):
            raise ValueError("worker packet required fields must be unique")
        if len(optional) != len(set(optional)):
            raise ValueError("worker packet optional fields must be unique")
        if set(required).intersection(optional):
            raise ValueError("worker packet required and optional fields must not overlap")
        object.__setattr__(self, "required_fields", required)
        object.__setattr__(self, "optional_fields", optional)

    @property
    def allowed_fields(self) -> frozenset[str]:
        return frozenset((*self.required_fields, *self.optional_fields))

    def project_packet(self, application_state: Mapping[str, Any]) -> dict[str, Any]:
        """Project broader application state into the worker's minimum packet."""

        missing = [field for field in self.required_fields if field not in application_state]
        if missing:
            raise ValueError(f"worker packet is missing required fields: {missing}")
        packet = {
            field: application_state[field]
            for field in (*self.required_fields, *self.optional_fields)
            if field in application_state
        }
        self.validate_packet(packet)
        return packet

    def validate_packet(self, packet: Mapping[str, Any]) -> None:
        missing = [field for field in self.required_fields if field not in packet]
        if missing:
            raise ValueError(f"worker packet is missing required fields: {missing}")
        unexpected = sorted(set(packet).difference(self.allowed_fields))
        if unexpected:
            raise ValueError(f"worker packet contains unregistered fields: {unexpected}")


@dataclass(frozen=True, slots=True)
class WorkerProfile:
    """Private application-owned execution profile for one transient role."""

    worker_profile_id: str
    description: str
    execution_mode: WorkerExecutionMode
    packet_contract: WorkerPacketContract
    output_schema_name: str
    system_prompt: str | None = None
    persona_access: PersonaAccess = PersonaAccess.FORBIDDEN
    model_pool_id: str | None = None
    delegated_worker_profile_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        worker_profile_id = self.worker_profile_id.strip()
        description = self.description.strip()
        output_schema_name = self.output_schema_name.strip()
        prompt = self.system_prompt.strip() if self.system_prompt is not None else None
        model_pool_id = self.model_pool_id.strip() if self.model_pool_id is not None else None
        delegates = tuple(value.strip() for value in self.delegated_worker_profile_ids)
        if not worker_profile_id or not description or not output_schema_name:
            raise ValueError("worker profile identity, description, and output schema are required")
        if any(not value for value in delegates) or len(delegates) != len(set(delegates)):
            raise ValueError("delegated worker profile ids must be non-empty and unique")

        if self.execution_mode is WorkerExecutionMode.LLM:
            if not prompt:
                raise ValueError("LLM worker profile requires a narrow system prompt")
            if not model_pool_id:
                raise ValueError("LLM worker profile requires a model pool")
        else:
            if prompt is not None:
                raise ValueError("deterministic worker profile must not carry a system prompt")
            if model_pool_id is not None:
                raise ValueError("deterministic worker profile must not bind an LLM model pool")
            if self.persona_access is not PersonaAccess.FORBIDDEN:
                raise ValueError("deterministic worker profile cannot receive persona instructions")

        if self.persona_access is PersonaAccess.REQUIRED and self.execution_mode is not WorkerExecutionMode.LLM:
            raise ValueError("persona instructions are valid only for an LLM response worker")

        object.__setattr__(self, "worker_profile_id", worker_profile_id)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "output_schema_name", output_schema_name)
        object.__setattr__(self, "system_prompt", prompt)
        object.__setattr__(self, "model_pool_id", model_pool_id)
        object.__setattr__(self, "delegated_worker_profile_ids", delegates)

    @property
    def system_prompt_sha256(self) -> str | None:
        if self.system_prompt is None:
            return None
        return hashlib.sha256(self.system_prompt.encode("utf-8")).hexdigest()


class WorkerProfileRegistry:
    """Private execution registry paired with the public capability registry."""

    def __init__(self, *, version: str = WORKER_PROFILE_REGISTRY_VERSION) -> None:
        normalized = version.strip()
        if not normalized:
            raise ValueError("worker profile registry version must not be blank")
        self.version = normalized
        self._profiles: dict[str, WorkerProfile] = {}
        self._capability_executor_bindings: dict[str, str] = {}

    def register(self, profile: WorkerProfile) -> None:
        if profile.worker_profile_id in self._profiles:
            raise ValueError(f"worker profile already registered: {profile.worker_profile_id}")
        self._profiles[profile.worker_profile_id] = profile

    def bind_capability_executor(self, executor_key: str, worker_profile_id: str) -> None:
        normalized_executor = executor_key.strip()
        normalized_profile = worker_profile_id.strip()
        if not normalized_executor or not normalized_profile:
            raise ValueError("capability executor binding values must not be blank")
        if normalized_executor in self._capability_executor_bindings:
            raise ValueError(f"capability executor already bound: {normalized_executor}")
        self.get(normalized_profile)
        self._capability_executor_bindings[normalized_executor] = normalized_profile

    def get(self, worker_profile_id: str) -> WorkerProfile:
        try:
            return self._profiles[worker_profile_id]
        except KeyError as exc:
            raise KeyError(f"unknown worker profile: {worker_profile_id}") from exc

    def profiles(self) -> tuple[WorkerProfile, ...]:
        return tuple(self._profiles[key] for key in sorted(self._profiles))

    def llm_profiles(self) -> tuple[WorkerProfile, ...]:
        return tuple(
            profile
            for profile in self.profiles()
            if profile.execution_mode is WorkerExecutionMode.LLM
        )

    def delegated_profiles(self, worker_profile_id: str) -> tuple[WorkerProfile, ...]:
        profile = self.get(worker_profile_id)
        return tuple(self.get(value) for value in profile.delegated_worker_profile_ids)

    def resolve_capability(
        self,
        capability_id: str,
        *,
        capability_registry: CapabilityRegistry = DEFAULT_REGISTRY,
    ) -> WorkerProfile:
        registration = capability_registry.get(capability_id)
        try:
            profile_id = self._capability_executor_bindings[registration.executor]
        except KeyError as exc:
            raise KeyError(
                f"capability executor has no worker profile binding: {registration.executor}"
            ) from exc
        return self.get(profile_id)

    def validate_capability_bindings(
        self,
        *,
        capability_registry: CapabilityRegistry = DEFAULT_REGISTRY,
    ) -> None:
        for descriptor in capability_registry.descriptors():
            self.resolve_capability(
                descriptor.capability_id,
                capability_registry=capability_registry,
            )
        for profile in self.profiles():
            self.delegated_profiles(profile.worker_profile_id)


def _deterministic_profile(
    worker_profile_id: str,
    description: str,
    required_fields: tuple[str, ...],
    output_schema_name: str,
    *,
    delegated_worker_profile_ids: tuple[str, ...] = (),
) -> WorkerProfile:
    return WorkerProfile(
        worker_profile_id=worker_profile_id,
        description=description,
        execution_mode=WorkerExecutionMode.DETERMINISTIC,
        packet_contract=WorkerPacketContract(required_fields=required_fields),
        output_schema_name=output_schema_name,
        delegated_worker_profile_ids=delegated_worker_profile_ids,
    )


def _llm_profile(
    worker_profile_id: str,
    description: str,
    required_fields: tuple[str, ...],
    output_schema_name: str,
    system_prompt: str,
    *,
    persona_access: PersonaAccess = PersonaAccess.FORBIDDEN,
) -> WorkerProfile:
    return WorkerProfile(
        worker_profile_id=worker_profile_id,
        description=description,
        execution_mode=WorkerExecutionMode.LLM,
        packet_contract=WorkerPacketContract(required_fields=required_fields),
        output_schema_name=output_schema_name,
        system_prompt=system_prompt,
        persona_access=persona_access,
        model_pool_id=PRIMARY_OLLAMA_MODEL_POOL,
    )


@lru_cache(maxsize=None)
def default_worker_profile_registry() -> WorkerProfileRegistry:
    """Build the production registry from the prompts used by active call sites."""

    from jit_agent.budgeted_evidence_llm import (
        _CURRENT_FALLBACK_SELECTION_SYSTEM_PROMPT,
        _EXACT_SOURCE_COMPOSITION_SYSTEM_PROMPT,
        _PRODUCTION_RESPONSE_POLICY_SYSTEM_PROMPT,
    )
    from jit_agent.evidence_bound_llm import (
        _AUTHORITY_BOUND_RESPOND_SYSTEM_PROMPT,
        _EXACT_SOURCE_SELECTION_SYSTEM_PROMPT,
    )
    from jit_agent.llm import (
        _CROSS_REFERENCE_SELECTION_PROMPT,
        _DEEPER_RESEARCH_SELECTION_PROMPT,
        _FOCUSED_RECALL_SELECTION_PROMPT,
    )
    from jit_agent.pre_cognitive_response_runtime import _FINAL_READINESS_SYSTEM_PROMPT
    from jit_agent.pre_cognitive_specialists import (
        _CAPABILITY_SELECTOR_SYSTEM_PROMPT,
        _EVIDENCE_SUFFICIENCY_SYSTEM_PROMPT,
    )

    registry = WorkerProfileRegistry()

    for profile in (
        _llm_profile(
            "evidence_sufficiency_verifier",
            "Decide only whether supplied current/evidence material can support the requested answer.",
            (
                "current_percept",
                "phase",
                "activated_evidence",
                "completed_capability_results",
            ),
            "EvidenceSufficiencyDecision",
            _EVIDENCE_SUFFICIENCY_SYSTEM_PROMPT,
        ),
        _llm_profile(
            "capability_selector",
            "Select only application-catalog indices that could close an established evidence gap.",
            (
                "current_percept",
                "phase",
                "activated_evidence",
                "capability_catalog",
                "completed_capability_results",
            ),
            "CapabilitySelectionDecision",
            _CAPABILITY_SELECTOR_SYSTEM_PROMPT,
        ),
        _llm_profile(
            "final_readiness",
            "Decide terminal response readiness after all allowed acquisition work has ended.",
            ("current_percept", "final_evidence", "capability_results"),
            "FinalReadinessDecision",
            _FINAL_READINESS_SYSTEM_PROMPT,
        ),
        _llm_profile(
            "response_policy_classifier",
            "Classify source admissibility and response surface from current authority only.",
            ("current_percept",),
            "ResponsePolicy",
            _PRODUCTION_RESPONSE_POLICY_SYSTEM_PROMPT,
        ),
        _llm_profile(
            "fallback_literal_selector",
            "Select only an explicit current-message literal for unsupported-evidence fallback.",
            ("current_percept",),
            "CurrentFallbackSelection",
            _CURRENT_FALLBACK_SELECTION_SYSTEM_PROMPT,
        ),
        _llm_profile(
            "memory_research_candidate_selector",
            "Select canonical memory candidates for deeper associative investigation.",
            ("current_task", "candidate_memory"),
            "MemoryCandidateSelection",
            _DEEPER_RESEARCH_SELECTION_PROMPT,
        ),
        _llm_profile(
            "cross_reference_candidate_selector",
            "Select canonical memory candidates that should be investigated jointly.",
            ("current_task", "candidate_memory"),
            "CrossReferenceCandidateSelection",
            _CROSS_REFERENCE_SELECTION_PROMPT,
        ),
        _llm_profile(
            "focused_recall_candidate_selector",
            "Select the canonical memory candidate for the deepest bounded recall profile.",
            ("current_task", "candidate_memory"),
            "FocusedMemoryCandidateSelection",
            _FOCUSED_RECALL_SELECTION_PROMPT,
        ),
        _llm_profile(
            "exact_source_substring_selector",
            "Select an exact admitted source substring for mechanical user-facing return.",
            ("current_percept", "admitted_source_candidates"),
            "ExactSourceSelection",
            _EXACT_SOURCE_SELECTION_SYSTEM_PROMPT,
        ),
        _llm_profile(
            "exact_source_composition_selector",
            "Select exact admitted source fragments and formatting for mechanical composition.",
            ("current_percept", "admitted_source_candidates"),
            "ExactSourceComposition",
            _EXACT_SOURCE_COMPOSITION_SYSTEM_PROMPT,
        ),
        _llm_profile(
            "final_response",
            "Realize an already-authorized natural-language response in the user-facing persona.",
            (
                "current_percept",
                "final_response_directive",
                "admitted_evidence",
                "admitted_capability_results",
                "personality_prompt",
            ),
            "TextAnswer",
            _AUTHORITY_BOUND_RESPOND_SYSTEM_PROMPT,
            persona_access=PersonaAccess.REQUIRED,
        ),
    ):
        registry.register(profile)

    for profile in (
        _deterministic_profile(
            "pre_cognitive_assessment",
            "Compose demand-driven specialist outputs into one durable pre-cognitive assessment.",
            (
                "current_percept",
                "phase",
                "activated_evidence",
                "capability_catalog",
                "completed_capability_results",
            ),
            "PreCognitiveAssessment",
            delegated_worker_profile_ids=(
                "evidence_sufficiency_verifier",
                "capability_selector",
            ),
        ),
        _deterministic_profile(
            "jit_memory_executor",
            "Execute bounded internal memory retrieval under application-owned provenance rules.",
            ("current_task", "memory_request", "sequence_boundary"),
            "CapabilityExecution",
        ),
        _deterministic_profile(
            "deeper_research_executor",
            "Resolve a deeper-research capability through canonical candidate selection and retrieval.",
            ("current_task", "candidate_memory", "execution_identity", "sequence_boundary"),
            "CapabilityExecution",
            delegated_worker_profile_ids=("memory_research_candidate_selector",),
        ),
        _deterministic_profile(
            "cross_reference_executor",
            "Resolve a cross-reference capability through joint candidate selection and retrieval.",
            ("current_task", "candidate_memory", "execution_identity", "sequence_boundary"),
            "CapabilityExecution",
            delegated_worker_profile_ids=("cross_reference_candidate_selector",),
        ),
        _deterministic_profile(
            "focused_recall_executor",
            "Resolve a focused-recall capability through one candidate selection and retrieval.",
            ("current_task", "candidate_memory", "execution_identity", "sequence_boundary"),
            "CapabilityExecution",
            delegated_worker_profile_ids=("focused_recall_candidate_selector",),
        ),
        _deterministic_profile(
            "final_response_finalizer",
            "Finalize response permission, source policy, evidence bindings, and persona binding.",
            ("current_percept", "acquisition_result", "personality_binding"),
            "FinalResponseDirective",
            delegated_worker_profile_ids=(
                "final_readiness",
                "response_policy_classifier",
                "fallback_literal_selector",
            ),
        ),
    ):
        registry.register(profile)

    registry.bind_capability_executor("jit_memory", "jit_memory_executor")
    registry.bind_capability_executor("deeper_research", "deeper_research_executor")
    registry.bind_capability_executor("cross_reference", "cross_reference_executor")
    registry.bind_capability_executor("focused_recall", "focused_recall_executor")
    registry.validate_capability_bindings()
    return registry
