"""Tests for domain enumerations and platform-deliverable mappings."""

import pytest

from negotiation.domain.types import (
    PLATFORM_DELIVERABLES,
    DeliverableType,
    NegotiationState,
    Platform,
    get_platform_for_deliverable,
    validate_platform_deliverable,
)


class TestPlatformEnum:
    """Tests for the Platform enum."""

    def test_has_exactly_three_members(self):
        assert len(Platform) == 3

    def test_members(self):
        assert Platform.INSTAGRAM == "instagram"
        assert Platform.TIKTOK == "tiktok"
        assert Platform.YOUTUBE == "youtube"

    def test_string_serialization(self):
        assert str(Platform.INSTAGRAM) == "instagram"
        assert str(Platform.TIKTOK) == "tiktok"
        assert str(Platform.YOUTUBE) == "youtube"

    def test_from_string(self):
        assert Platform("instagram") == Platform.INSTAGRAM
        assert Platform("tiktok") == Platform.TIKTOK
        assert Platform("youtube") == Platform.YOUTUBE

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            Platform("facebook")


class TestDeliverableTypeEnum:
    """Tests for the DeliverableType enum."""

    def test_has_exactly_eight_members(self):
        assert len(DeliverableType) == 8

    def test_instagram_types(self):
        assert DeliverableType.INSTAGRAM_POST == "instagram_post"
        assert DeliverableType.INSTAGRAM_STORY == "instagram_story"
        assert DeliverableType.INSTAGRAM_REEL == "instagram_reel"

    def test_tiktok_types(self):
        assert DeliverableType.TIKTOK_VIDEO == "tiktok_video"
        assert DeliverableType.TIKTOK_STORY == "tiktok_story"

    def test_youtube_types(self):
        assert DeliverableType.YOUTUBE_DEDICATED == "youtube_dedicated"
        assert DeliverableType.YOUTUBE_INTEGRATION == "youtube_integration"
        assert DeliverableType.YOUTUBE_SHORT == "youtube_short"

    def test_string_round_trip(self):
        for dt in DeliverableType:
            assert DeliverableType(str(dt)) == dt


class TestNegotiationStateEnum:
    """Tests for the NegotiationState enum."""

    def test_has_exactly_eight_members(self):
        assert len(NegotiationState) == 8

    def test_all_states_present(self):
        expected = {
            "initial_offer",
            "awaiting_reply",
            "counter_received",
            "counter_sent",
            "agreed",
            "rejected",
            "escalated",
            "stale",
        }
        actual = {str(s) for s in NegotiationState}
        assert actual == expected

    def test_string_round_trip(self):
        for state in NegotiationState:
            assert NegotiationState(str(state)) == state


class TestPlatformDeliverables:
    """Tests for the PLATFORM_DELIVERABLES mapping."""

    def test_all_eight_deliverable_types_mapped(self):
        all_mapped = set()
        for types in PLATFORM_DELIVERABLES.values():
            all_mapped.update(types)
        assert len(all_mapped) == 8
        assert all_mapped == set(DeliverableType)

    def test_instagram_has_three_types(self):
        assert len(PLATFORM_DELIVERABLES[Platform.INSTAGRAM]) == 3

    def test_tiktok_has_two_types(self):
        assert len(PLATFORM_DELIVERABLES[Platform.TIKTOK]) == 2

    def test_youtube_has_three_types(self):
        assert len(PLATFORM_DELIVERABLES[Platform.YOUTUBE]) == 3

    def test_no_overlap_between_platforms(self):
        instagram = PLATFORM_DELIVERABLES[Platform.INSTAGRAM]
        tiktok = PLATFORM_DELIVERABLES[Platform.TIKTOK]
        youtube = PLATFORM_DELIVERABLES[Platform.YOUTUBE]
        assert instagram.isdisjoint(tiktok)
        assert instagram.isdisjoint(youtube)
        assert tiktok.isdisjoint(youtube)


class TestGetPlatformForDeliverable:
    """Tests for the get_platform_for_deliverable helper."""

    @pytest.mark.parametrize(
        "deliverable_type,expected_platform",
        [
            (DeliverableType.INSTAGRAM_POST, Platform.INSTAGRAM),
            (DeliverableType.INSTAGRAM_STORY, Platform.INSTAGRAM),
            (DeliverableType.INSTAGRAM_REEL, Platform.INSTAGRAM),
            (DeliverableType.TIKTOK_VIDEO, Platform.TIKTOK),
            (DeliverableType.TIKTOK_STORY, Platform.TIKTOK),
            (DeliverableType.YOUTUBE_DEDICATED, Platform.YOUTUBE),
            (DeliverableType.YOUTUBE_INTEGRATION, Platform.YOUTUBE),
            (DeliverableType.YOUTUBE_SHORT, Platform.YOUTUBE),
        ],
    )
    def test_returns_correct_platform(self, deliverable_type, expected_platform):
        assert get_platform_for_deliverable(deliverable_type) == expected_platform


class TestValidatePlatformDeliverable:
    """Tests for the validate_platform_deliverable helper."""

    @pytest.mark.parametrize(
        "platform,deliverable_type",
        [
            (Platform.INSTAGRAM, DeliverableType.INSTAGRAM_POST),
            (Platform.INSTAGRAM, DeliverableType.INSTAGRAM_STORY),
            (Platform.INSTAGRAM, DeliverableType.INSTAGRAM_REEL),
            (Platform.TIKTOK, DeliverableType.TIKTOK_VIDEO),
            (Platform.TIKTOK, DeliverableType.TIKTOK_STORY),
            (Platform.YOUTUBE, DeliverableType.YOUTUBE_DEDICATED),
            (Platform.YOUTUBE, DeliverableType.YOUTUBE_INTEGRATION),
            (Platform.YOUTUBE, DeliverableType.YOUTUBE_SHORT),
        ],
    )
    def test_valid_pairs_pass(self, platform, deliverable_type):
        # Should not raise
        validate_platform_deliverable(platform, deliverable_type)

    @pytest.mark.parametrize(
        "platform,deliverable_type",
        [
            (Platform.INSTAGRAM, DeliverableType.TIKTOK_VIDEO),
            (Platform.INSTAGRAM, DeliverableType.YOUTUBE_SHORT),
            (Platform.TIKTOK, DeliverableType.INSTAGRAM_REEL),
            (Platform.TIKTOK, DeliverableType.YOUTUBE_DEDICATED),
            (Platform.YOUTUBE, DeliverableType.INSTAGRAM_POST),
            (Platform.YOUTUBE, DeliverableType.TIKTOK_STORY),
        ],
    )
    def test_invalid_pairs_raise_value_error(self, platform, deliverable_type):
        with pytest.raises(ValueError, match="is not valid for"):
            validate_platform_deliverable(platform, deliverable_type)
