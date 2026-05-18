from app.logging import get_logger

logger = get_logger(__name__)


def notify_pipeline_complete(episode_title: str) -> None:
    """
    Show a Windows desktop toast notification when the pipeline finishes.
    Silently skips if plyer is not installed or notifications are unsupported.
    """
    try:
        from plyer import notification
        notification.notify(
            title="Transcrire — Complete",
            message=f'"{episode_title}" has been fully processed.',
            app_name="Transcrire",
            timeout=8,
        )
        logger.info({"event": "toast_notification_sent", "episode": episode_title})
    except Exception as e:
        # Notification failure should never crash the pipeline
        logger.warning({"event": "toast_notification_failed", "error": str(e)})


def notify_stage_failed(stage: str, episode_title: str) -> None:
    """Show a toast when a stage fails so the user knows without watching the screen."""
    try:
        from plyer import notification
        notification.notify(
            title=f"Transcrire — {stage} Failed",
            message=f'"{episode_title}" encountered an error during {stage}.',
            app_name="Transcrire",
            timeout=10,
        )
    except Exception as e:
        logger.warning({"event": "toast_notification_failed", "error": str(e)})