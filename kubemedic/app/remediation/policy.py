"""Checks that run before a proposal can be approved or executed.

The executor never sees this module's user text. It only receives a typed action.
"""

import re

from app.config import Settings
from app.remediation.errors import PolicyError
from app.remediation.models import Remediation

ALLOWED_ACTIONS = {"restart_deployment", "rollback_deployment", "scale_deployment"}
_NAME = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
_ACTOR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,63}$")


def validate_target(remediation: Remediation, settings: Settings) -> None:
    if remediation.action not in ALLOWED_ACTIONS:
        raise PolicyError("Action is not on the remediation allowlist.")
    if remediation.target_kind != "Deployment":
        raise PolicyError("Only Deployments can be remediated.")
    if remediation.namespace != settings.namespace:
        raise PolicyError("Remediation is limited to the watched namespace.")
    if not _NAME.match(remediation.target_name or ""):
        raise PolicyError("Deployment name is not a DNS label.")
    if remediation.action == "scale_deployment":
        replicas = remediation.replicas
        if not isinstance(replicas, int) or isinstance(replicas, bool):
            raise PolicyError("Scale requires an integer replica count.")
        if replicas < 1 or replicas > settings.remediation_max_replicas:
            raise PolicyError(
                f"Replica count must be from 1 to {settings.remediation_max_replicas}."
            )
    elif remediation.replicas is not None:
        raise PolicyError("Replica count is only valid for scale_deployment.")


def validate_approval(approved_by: str, confirm: bool, reason: str) -> None:
    if confirm is not True:
        raise PolicyError("Confirmation is required.")
    if not isinstance(approved_by, str) or not _ACTOR.match(approved_by):
        raise PolicyError("approved_by must be a short name, not a credential.")
    if reason is None:
        return
    if not isinstance(reason, str) or len(reason) > 280:
        raise PolicyError("Approval reason must be 280 characters or fewer.")
