"""Knowledge base loader for negotiation guidance and platform-specific content.

Loads Markdown files from the knowledge_base/ directory at project root and
combines general + platform-specific content for system prompt injection.
"""

from pathlib import Path

# Resolve from src/negotiation/llm/ up 3 levels to project root, then into knowledge_base/
DEFAULT_KB_DIR = Path(__file__).resolve().parents[3] / "knowledge_base"


def load_knowledge_base(
    platform: str,
    kb_dir: Path = DEFAULT_KB_DIR,
) -> str:
    """Load knowledge base content for a given platform.

    Loads the general playbook + platform-specific file,
    concatenated for system prompt injection.

    Args:
        platform: One of 'instagram', 'tiktok', 'youtube'.
        kb_dir: Path to the knowledge_base directory.

    Returns:
        Combined markdown content ready for system prompt injection.

    Raises:
        FileNotFoundError: If neither general.md nor {platform}.md exists in kb_dir.
    """
    sections: list[str] = []

    general_path = kb_dir / "general.md"
    if general_path.exists():
        sections.append(general_path.read_text(encoding="utf-8"))

    platform_path = kb_dir / f"{platform}.md"
    if platform_path.exists():
        sections.append(platform_path.read_text(encoding="utf-8"))

    if not sections:
        msg = (
            f"No knowledge base files found in {kb_dir}. "
            f"Expected at least general.md or {platform}.md"
        )
        raise FileNotFoundError(msg)

    return "\n\n---\n\n".join(sections)


def list_available_platforms(kb_dir: Path = DEFAULT_KB_DIR) -> list[str]:
    """List all available platform knowledge base files.

    Scans kb_dir for .md files, excluding general.md, and returns
    the sorted list of platform names (file stems).

    Args:
        kb_dir: Path to the knowledge_base directory.

    Returns:
        Sorted list of platform names (e.g., ['instagram', 'tiktok', 'youtube']).
    """
    if not kb_dir.exists():
        return []

    return sorted(p.stem for p in kb_dir.glob("*.md") if p.stem != "general")
