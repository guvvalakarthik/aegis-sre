"""Independent deny-by-default remediation safety controller."""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Any, Callable, Mapping, Protocol


class RiskClass(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class Decision(StrEnum):
    DENIED = "denied"
    APPROVED = "approved"
    ROLLED_BACK = "rolled_back"
    COMPLETED = "completed"
    KILLED = "killed"


@dataclass(frozen=True)
class ActionRequest:
    request_id: str
    action: str
    target: str
    environment: str
    risk: RiskClass
    parameters: Mapping[str, str]
    proposal_text: str = ""

    def digest(self) -> str:
        payload = json.dumps({
            "request_id": self.request_id, "action": self.action, "target": self.target,
            "environment": self.environment, "risk": int(self.risk),
            "parameters": dict(sorted(self.parameters.items())),
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class Approval:
    principal: str
    request_digest: str
    expires_at: float
    signature: str


@dataclass(frozen=True)
class Policy:
    allowed_actions: frozenset[str]
    allowed_targets: frozenset[str]
    allowed_environments: frozenset[str]
    required_approval_risk: RiskClass = RiskClass.HIGH
    approver_roles: frozenset[str] = frozenset({"approver"})

    def permits(self, request: ActionRequest) -> bool:
        return (
            request.action in self.allowed_actions
            and request.target in self.allowed_targets
            and request.environment in self.allowed_environments
        )


@dataclass(frozen=True)
class AuditRecord:
    sequence: int
    request_id: str
    decision: Decision
    actor: str
    reason: str
    previous_hash: str
    record_hash: str
    timestamp: float


class SafetyExecutor(Protocol):
    def dry_run(self, request: ActionRequest) -> None:
        ...

    def canary(self, request: ActionRequest) -> None:
        ...

    def apply(self, request: ActionRequest) -> None:
        ...

    def rollback(self, request: ActionRequest) -> None:
        ...

    def health_check(self, request: ActionRequest) -> bool:
        ...


class SafetyController:
    def __init__(self, policy: Policy, *, approval_secret: bytes) -> None:
        if not approval_secret:
            raise ValueError("approval secret is required")
        self.policy = policy
        self._approval_secret = approval_secret
        self._kill_switch = False
        self._audit: list[AuditRecord] = []
        self._lock = threading.RLock()

    def sign_approval(self, principal: str, request: ActionRequest, expires_at: float) -> Approval:
        if not principal or expires_at <= time.time():
            raise ValueError("approval principal and future expiry are required")
        digest = request.digest()
        signature = hmac.new(self._approval_secret, f"{principal}:{digest}:{expires_at}".encode(), hashlib.sha256).hexdigest()
        return Approval(principal, digest, expires_at, signature)

    def set_kill_switch(self, enabled: bool, *, actor: str) -> None:
        if not actor:
            raise ValueError("kill-switch actor is required")
        with self._lock:
            self._kill_switch = enabled
            self._record(ActionRequest("kill-switch", "kill-switch", "controller", "system", RiskClass.CRITICAL, {}), Decision.KILLED if enabled else Decision.APPROVED, actor, "kill switch changed")

    def authorize(self, request: ActionRequest, *, actor: str, roles: frozenset[str], approval: Approval | None = None) -> None:
        with self._lock:
            if self._kill_switch:
                self._record(request, Decision.DENIED, actor, "kill switch enabled")
                raise PermissionError("kill switch enabled")
            if not actor or not roles or not self.policy.permits(request):
                self._record(request, Decision.DENIED, actor, "policy denied")
                raise PermissionError("policy denied")
            if request.risk >= self.policy.required_approval_risk:
                if approval is None or not self._valid_approval(request, approval, roles):
                    self._record(request, Decision.DENIED, actor, "approval required or invalid")
                    raise PermissionError("authenticated approval required")
            self._record(request, Decision.APPROVED, actor, "policy and approval checks passed")

    def execute(
        self,
        request: ActionRequest,
        executor: SafetyExecutor,
        *,
        actor: str,
        roles: frozenset[str],
        approval: Approval | None = None,
    ) -> Decision:
        self.authorize(request, actor=actor, roles=roles, approval=approval)
        try:
            executor.dry_run(request)
            executor.canary(request)
            executor.apply(request)
            if not executor.health_check(request):
                raise RuntimeError("health gate failed")
            self._record(request, Decision.COMPLETED, actor, "health gate passed")
            return Decision.COMPLETED
        except Exception as exc:
            try:
                executor.rollback(request)
            except Exception as rollback_error:
                self._record(request, Decision.DENIED, actor, f"rollback failed: {rollback_error}")
                raise RuntimeError("remediation and rollback failed; escalate") from exc
            self._record(request, Decision.ROLLED_BACK, actor, f"verification failed: {exc}")
            return Decision.ROLLED_BACK

    def audit_log(self) -> tuple[AuditRecord, ...]:
        with self._lock:
            return tuple(self._audit)

    def _valid_approval(self, request: ActionRequest, approval: Approval, roles: frozenset[str]) -> bool:
        if not roles.intersection(self.policy.approver_roles) or approval.expires_at <= time.time():
            return False
        expected = hmac.new(
            self._approval_secret,
            f"{approval.principal}:{approval.request_digest}:{approval.expires_at}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return approval.request_digest == request.digest() and hmac.compare_digest(expected, approval.signature)

    def _record(self, request: ActionRequest, decision: Decision, actor: str, reason: str) -> None:
        previous = self._audit[-1].record_hash if self._audit else "GENESIS"
        sequence = len(self._audit) + 1
        timestamp = time.time()
        payload = f"{sequence}|{request.request_id}|{decision.value}|{actor}|{reason}|{previous}|{timestamp}"
        record_hash = hashlib.sha256(payload.encode()).hexdigest()
        self._audit.append(AuditRecord(sequence, request.request_id, decision, actor, reason, previous, record_hash, timestamp))
