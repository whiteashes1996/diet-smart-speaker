class SmartSpeakerError(Exception):
    pass


class TransientError(SmartSpeakerError):
    """Retryable: network blip, empty STT, etc."""


class FatalError(SmartSpeakerError):
    """Non-retryable: missing mic permission, bad config."""
