"""
PostHog integration for product analytics, error tracking and performance monitoring.
Free tier: 1M events/month. Cloud: https://app.posthog.com
"""
import posthog
from config.settings import settings

_initialized = False


def init_posthog():
    global _initialized
    if _initialized:
        return
    if not settings.posthog_api_key:
        return
    posthog.project_api_key = settings.posthog_api_key
    posthog.host = settings.posthog_host
    _initialized = True


def identify(user_id: str, properties: dict | None = None):
    """Identify a user in PostHog."""
    if not settings.posthog_api_key or not _initialized:
        return
    try:
        posthog.identify(user_id, properties or {})
    except Exception:
        pass


def capture(user_id: str, event: str, properties: dict | None = None):
    """Capture an event in PostHog."""
    if not settings.posthog_api_key or not _initialized:
        return
    try:
        posthog.capture(user_id, event, properties or {})
    except Exception:
        pass


def capture_exception(user_id: str, exception: Exception, context: dict | None = None):
    """Capture an exception in PostHog."""
    if not settings.posthog_api_key or not _initialized:
        return
    try:
        props = {
            "error_type": type(exception).__name__,
            "error_message": str(exception)[:500],
            **(context or {}),
        }
        posthog.capture(user_id, "$exception", props)
    except Exception:
        pass
