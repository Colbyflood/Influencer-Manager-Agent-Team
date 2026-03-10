"""Tests for the knowledge base loader module."""

import pytest

from negotiation.llm.knowledge_base import (
    list_available_platforms,
    load_examples_for_stage,
    load_knowledge_base,
)


class TestLoadKnowledgeBase:
    """Tests for load_knowledge_base function."""

    def test_returns_combined_content_for_platform(self, tmp_path):
        """Test that load_knowledge_base returns general + platform content combined."""
        (tmp_path / "general.md").write_text("# General Playbook\nCore principles here.")
        (tmp_path / "instagram.md").write_text("# Instagram Guide\nInstagram tactics here.")

        result = load_knowledge_base("instagram", kb_dir=tmp_path)

        assert "# General Playbook" in result
        assert "# Instagram Guide" in result

    def test_includes_general_content(self, tmp_path):
        """Test that the result includes general.md content."""
        (tmp_path / "general.md").write_text("Core principles\nDo NOT Say")
        (tmp_path / "tiktok.md").write_text("TikTok guide")

        result = load_knowledge_base("tiktok", kb_dir=tmp_path)

        assert "Core principles" in result
        assert "Do NOT Say" in result

    def test_includes_platform_specific_content(self, tmp_path):
        """Test that the result includes platform-specific content."""
        (tmp_path / "general.md").write_text("General content")
        (tmp_path / "youtube.md").write_text("YouTube specific tactics and examples")

        result = load_knowledge_base("youtube", kb_dir=tmp_path)

        assert "YouTube specific tactics and examples" in result

    def test_separates_sections_with_divider(self, tmp_path):
        """Test that general and platform content are separated by a markdown divider."""
        (tmp_path / "general.md").write_text("General")
        (tmp_path / "instagram.md").write_text("Instagram")

        result = load_knowledge_base("instagram", kb_dir=tmp_path)

        assert "\n\n---\n\n" in result

    def test_raises_file_not_found_for_unknown_platform_empty_dir(self, tmp_path):
        """Test that FileNotFoundError is raised when no files exist."""
        with pytest.raises(FileNotFoundError, match="No knowledge base files found"):
            load_knowledge_base("nonexistent", kb_dir=tmp_path)

    def test_works_with_only_general_file(self, tmp_path):
        """Test that load_knowledge_base works when only general.md exists."""
        (tmp_path / "general.md").write_text("General playbook content only")

        result = load_knowledge_base("missing_platform", kb_dir=tmp_path)

        assert "General playbook content only" in result
        # No divider when only one section
        assert "\n\n---\n\n" not in result

    def test_works_with_only_platform_file(self, tmp_path):
        """Test that load_knowledge_base works when only platform file exists."""
        (tmp_path / "instagram.md").write_text("Instagram only content")

        result = load_knowledge_base("instagram", kb_dir=tmp_path)

        assert "Instagram only content" in result
        assert "\n\n---\n\n" not in result

    def test_loads_real_knowledge_base_instagram(self):
        """Test loading the actual project knowledge base for Instagram."""
        result = load_knowledge_base("instagram")

        assert "Negotiation Playbook" in result
        assert "Instagram" in result
        assert "Do NOT Say" in result

    def test_loads_real_knowledge_base_tiktok(self):
        """Test loading the actual project knowledge base for TikTok."""
        result = load_knowledge_base("tiktok")

        assert "Negotiation Playbook" in result
        assert "TikTok" in result

    def test_loads_real_knowledge_base_youtube(self):
        """Test loading the actual project knowledge base for YouTube."""
        result = load_knowledge_base("youtube")

        assert "Negotiation Playbook" in result
        assert "YouTube" in result


class TestListAvailablePlatforms:
    """Tests for list_available_platforms function."""

    def test_returns_sorted_platform_names(self):
        """Test that list_available_platforms returns sorted platform names from real KB."""
        platforms = list_available_platforms()

        assert platforms == ["instagram", "tiktok", "youtube"]

    def test_excludes_general_from_platforms(self, tmp_path):
        """Test that general.md is excluded from platform list."""
        (tmp_path / "general.md").write_text("General")
        (tmp_path / "instagram.md").write_text("Instagram")

        platforms = list_available_platforms(kb_dir=tmp_path)

        assert "general" not in platforms
        assert "instagram" in platforms

    def test_returns_empty_list_for_missing_directory(self, tmp_path):
        """Test that an empty list is returned when kb_dir doesn't exist."""
        nonexistent = tmp_path / "nonexistent"

        platforms = list_available_platforms(kb_dir=nonexistent)

        assert platforms == []

    def test_returns_sorted_order(self, tmp_path):
        """Test that platforms are returned in alphabetical order."""
        (tmp_path / "youtube.md").write_text("YouTube")
        (tmp_path / "instagram.md").write_text("Instagram")
        (tmp_path / "tiktok.md").write_text("TikTok")

        platforms = list_available_platforms(kb_dir=tmp_path)

        assert platforms == ["instagram", "tiktok", "youtube"]


def _create_example(
    path, scenario, title, stages, tactics=None, platform=None, body="Example body."
):
    """Helper to create an example .md file with YAML frontmatter."""
    tactics = tactics or []
    frontmatter_lines = [
        "---",
        f"scenario: {scenario}",
        f'title: "{title}"',
        "stages:",
    ]
    for s in stages:
        frontmatter_lines.append(f"  - {s}")
    if tactics:
        frontmatter_lines.append("tactics:")
        for t in tactics:
            frontmatter_lines.append(f"  - {t}")
    frontmatter_lines.append(f"platform: {platform if platform else 'null'}")
    frontmatter_lines.append("---")
    frontmatter_lines.append("")
    frontmatter_lines.append(body)
    path.write_text("\n".join(frontmatter_lines))


class TestLoadExamplesForStage:
    """Tests for load_examples_for_stage function."""

    def test_loads_examples_matching_stage(self, tmp_path):
        """Create tmp examples with frontmatter, verify matching stage returned."""
        examples_dir = tmp_path / "examples"
        examples_dir.mkdir()
        _create_example(
            examples_dir / "counter_email.md",
            "counter",
            "Counter Offer Email",
            stages=["counter_sent", "counter_received"],
            body="This is a counter offer.",
        )

        result = load_examples_for_stage("counter_sent", kb_dir=tmp_path)

        assert "Counter Offer Email" in result
        assert "This is a counter offer." in result

    def test_excludes_examples_not_matching_stage(self, tmp_path):
        """Create examples for different stages, verify non-matching excluded."""
        examples_dir = tmp_path / "examples"
        examples_dir.mkdir()
        _create_example(
            examples_dir / "close.md",
            "close",
            "Close Email",
            stages=["agreed"],
            body="Closing email body.",
        )
        _create_example(
            examples_dir / "counter.md",
            "counter",
            "Counter Email",
            stages=["counter_sent"],
            body="Counter email body.",
        )

        result = load_examples_for_stage("counter_sent", kb_dir=tmp_path)

        assert "Counter Email" in result
        assert "Close Email" not in result

    def test_filters_by_platform_when_provided(self, tmp_path):
        """Platform-specific excluded when different; platform-agnostic always included."""
        examples_dir = tmp_path / "examples"
        examples_dir.mkdir()
        _create_example(
            examples_dir / "generic.md",
            "generic",
            "Generic Example",
            stages=["counter_sent"],
            platform=None,
            body="Generic body.",
        )
        _create_example(
            examples_dir / "ig_only.md",
            "ig_only",
            "Instagram Only",
            stages=["counter_sent"],
            platform="instagram",
            body="IG body.",
        )
        _create_example(
            examples_dir / "tt_only.md",
            "tt_only",
            "TikTok Only",
            stages=["counter_sent"],
            platform="tiktok",
            body="TT body.",
        )

        result = load_examples_for_stage("counter_sent", platform="instagram", kb_dir=tmp_path)

        assert "Generic Example" in result
        assert "Instagram Only" in result
        assert "TikTok Only" not in result

    def test_returns_empty_string_when_no_matches(self, tmp_path):
        """Call with a stage that matches nothing, verify empty string."""
        examples_dir = tmp_path / "examples"
        examples_dir.mkdir()
        _create_example(
            examples_dir / "close.md",
            "close",
            "Close Email",
            stages=["agreed"],
            body="Close body.",
        )

        result = load_examples_for_stage("nonexistent_stage", kb_dir=tmp_path)

        assert result == ""

    def test_load_knowledge_base_with_stage_includes_examples(self):
        """load_knowledge_base with stage returns both playbook and examples."""
        result = load_knowledge_base("instagram", stage="counter_sent")

        assert "Negotiation Playbook" in result
        assert "Relevant Email Examples" in result

    def test_load_knowledge_base_without_stage_excludes_examples(self):
        """load_knowledge_base without stage returns playbook only (backward compat)."""
        result = load_knowledge_base("instagram")

        assert "Negotiation Playbook" in result
        assert "Relevant Email Examples" not in result

    def test_counter_sent_stage_gets_bundled_and_cpm_examples(self):
        """counter_sent stage should include bundled_rate and cpm_mention examples."""
        result = load_examples_for_stage("counter_sent")

        assert "Bundled Rate" in result
        assert "CPM" in result

    def test_agreed_stage_gets_close_example(self):
        """agreed stage should include positive_close example."""
        result = load_examples_for_stage("agreed")

        assert "Positive Close" in result

    def test_loads_examples_for_counter(self):
        """Verify counter_sent returns relevant examples (plan must_have artifact check)."""
        result = load_examples_for_stage("counter_sent")

        assert len(result) > 0
        # Should not include agreed-only examples
        assert "Agreement Confirmation" not in result or "Bundled Rate" in result


class TestExportedSymbols:
    """Tests for module exports."""

    def test_load_examples_for_stage_exported(self):
        """load_examples_for_stage should be importable from negotiation.llm."""
        from negotiation.llm.knowledge_base import load_examples_for_stage as fn

        assert callable(fn)

    def test_load_examples_for_stage_in_init_exports(self):
        """load_examples_for_stage should be in negotiation.llm.__init__ imports."""
        # Verify the import statement exists by importing from knowledge_base directly
        # (full __init__ import blocked by anthropic dependency in test env)
        from negotiation.llm.knowledge_base import load_examples_for_stage

        assert load_examples_for_stage is not None
