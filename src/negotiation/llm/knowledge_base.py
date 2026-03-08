"""Knowledge base loader for negotiation guidance and platform-specific content.

Loads Markdown files from the knowledge_base/ directory at project root and
combines general + platform-specific content for system prompt injection.
Supports stage-aware example selection via YAML frontmatter filtering.
"""

from __future__ import annotations

from pathlib import Path

try:
    import yaml  # type: ignore[import-untyped]

    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

# Resolve from src/negotiation/llm/ up 3 levels to project root, then into knowledge_base/
DEFAULT_KB_DIR = Path(__file__).resolve().parents[3] / "knowledge_base"


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content.

    Splits on ``---`` delimiters and returns (metadata_dict, body_text).
    If no frontmatter is found, returns ({}, full_content).
    """
    if not content.startswith("---"):
        return {}, content

    # Find closing delimiter
    end_idx = content.index("---", 3)
    yaml_block = content[3:end_idx].strip()
    body = content[end_idx + 3 :].strip()

    if _HAS_YAML:
        meta = yaml.safe_load(yaml_block) or {}
    else:
        # Manual parse for simple key-value / list frontmatter
        meta: dict = {}
        current_key: str | None = None
        for line in yaml_block.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("- ") and current_key is not None:
                meta[current_key].append(stripped[2:].strip().strip('"').strip("'"))
            elif ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if val in ("", "[]"):
                    meta[key] = []
                    current_key = key
                elif val == "null":
                    meta[key] = None
                    current_key = None
                else:
                    meta[key] = val
                    current_key = None

    return meta, body


def load_examples_for_stage(
    stage: str,
    platform: str | None = None,
    kb_dir: Path = DEFAULT_KB_DIR,
) -> str:
    """Load email examples filtered by negotiation stage.

    Scans the ``examples/`` subdirectory for ``.md`` files with YAML
    frontmatter and returns those whose ``stages`` list contains *stage*.

    Args:
        stage: Negotiation stage to filter by (e.g. ``'counter_sent'``).
        platform: Optional platform filter. When provided, includes examples
            whose platform is ``None``/null **or** matches *platform*.
        kb_dir: Path to the knowledge_base directory.

    Returns:
        Concatenated markdown string of matching examples, each preceded by
        its title as a heading.  Empty string when nothing matches.
    """
    examples_dir = kb_dir / "examples"
    if not examples_dir.exists():
        return ""

    matches: list[str] = []

    for md_file in sorted(examples_dir.glob("*.md")):
        raw = md_file.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)

        stages = meta.get("stages", [])
        if not isinstance(stages, list) or stage not in stages:
            continue

        # Platform filter
        if platform is not None:
            example_platform = meta.get("platform")
            if example_platform is not None and example_platform != platform:
                continue

        title = meta.get("title", md_file.stem)
        matches.append(f"### {title}\n\n{body}")

    return "\n\n---\n\n".join(matches)


def load_knowledge_base(
    platform: str,
    kb_dir: Path = DEFAULT_KB_DIR,
    stage: str | None = None,
) -> str:
    """Load knowledge base content for a given platform.

    Loads the general playbook + platform-specific file,
    concatenated for system prompt injection.  When *stage* is provided,
    appends relevant email examples filtered by negotiation stage.

    Args:
        platform: One of 'instagram', 'tiktok', 'youtube'.
        kb_dir: Path to the knowledge_base directory.
        stage: Optional negotiation stage for example filtering.

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

    result = "\n\n---\n\n".join(sections)

    # Append stage-filtered examples when stage is provided
    if stage:
        examples = load_examples_for_stage(stage, platform=platform, kb_dir=kb_dir)
        if examples:
            result += "\n\n## Relevant Email Examples\n\n" + examples

    return result


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
