"""Tests for the knowledge base loader module."""

import pytest

from negotiation.llm.knowledge_base import list_available_platforms, load_knowledge_base


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
