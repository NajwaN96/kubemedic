class PolicyError(Exception):
    """The action is not on the allowlist or the approval is incomplete."""


class RemediationDisabled(Exception):
    """Remediation is off. Approval is still required when it is turned on."""


class ExecutionError(Exception):
    """A typed action could not be applied. The message is safe to store."""
