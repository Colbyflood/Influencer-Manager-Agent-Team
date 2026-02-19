"""Domain enumerations and platform-deliverable mappings for the negotiation agent."""

from enum import StrEnum


class Platform(StrEnum):
    """Supported social media platforms."""

    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"


class DeliverableType(StrEnum):
    """Platform-specific deliverable types for influencer content."""

    # Instagram
    INSTAGRAM_POST = "instagram_post"
    INSTAGRAM_STORY = "instagram_story"
    INSTAGRAM_REEL = "instagram_reel"
    # TikTok
    TIKTOK_VIDEO = "tiktok_video"
    TIKTOK_STORY = "tiktok_story"
    # YouTube
    YOUTUBE_DEDICATED = "youtube_dedicated"
    YOUTUBE_INTEGRATION = "youtube_integration"
    YOUTUBE_SHORT = "youtube_short"


class NegotiationState(StrEnum):
    """States in the negotiation lifecycle."""

    INITIAL_OFFER = "initial_offer"
    AWAITING_REPLY = "awaiting_reply"
    COUNTER_RECEIVED = "counter_received"
    COUNTER_SENT = "counter_sent"
    AGREED = "agreed"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    STALE = "stale"


# Mapping of platforms to their valid deliverable types
PLATFORM_DELIVERABLES: dict[Platform, set[DeliverableType]] = {
    Platform.INSTAGRAM: {
        DeliverableType.INSTAGRAM_POST,
        DeliverableType.INSTAGRAM_STORY,
        DeliverableType.INSTAGRAM_REEL,
    },
    Platform.TIKTOK: {
        DeliverableType.TIKTOK_VIDEO,
        DeliverableType.TIKTOK_STORY,
    },
    Platform.YOUTUBE: {
        DeliverableType.YOUTUBE_DEDICATED,
        DeliverableType.YOUTUBE_INTEGRATION,
        DeliverableType.YOUTUBE_SHORT,
    },
}


def get_platform_for_deliverable(deliverable_type: DeliverableType) -> Platform:
    """Look up which platform a deliverable type belongs to.

    Args:
        deliverable_type: The deliverable type to look up.

    Returns:
        The platform that owns the given deliverable type.

    Raises:
        ValueError: If the deliverable type is not mapped to any platform.
    """
    for platform, types in PLATFORM_DELIVERABLES.items():
        if deliverable_type in types:
            return platform
    raise ValueError(f"Unknown deliverable type: {deliverable_type}")


def validate_platform_deliverable(
    platform: Platform, deliverable_type: DeliverableType
) -> None:
    """Validate that a deliverable type is valid for the given platform.

    Args:
        platform: The platform to validate against.
        deliverable_type: The deliverable type to validate.

    Raises:
        ValueError: If the deliverable type is not valid for the given platform.
    """
    valid_types = PLATFORM_DELIVERABLES.get(platform, set())
    if deliverable_type not in valid_types:
        raise ValueError(
            f"{deliverable_type} is not valid for {platform}. "
            f"Valid types: {', '.join(sorted(valid_types))}"
        )
