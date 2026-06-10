"""
Skill Manager — reads ECC skill definitions from vendor/ecc/skills/.

Each skill is a subdirectory containing a SKILL.md file with YAML frontmatter:
    ---
    name: skill-name
    description: Short description
    ---
    # Skill Title
    ... full instructions ...

Progressive disclosure:
  - get_skills_catalog() returns only name+description for the system prompt.
  - load_skill_content(skill_id) loads full markdown on demand (via load_skill tool).
"""

import re
from pathlib import Path

# Skills are discovered from two roots, in priority order:
#  1. LOCAL_SKILLS_DIR — SmartAgent's own skills (tracked in this repo, owned by us).
#  2. VENDOR_SKILLS_DIR — bundled ECC skills (vendor/ecc is a separate embedded repo).
# Local skills win on id collisions so our curated versions override vendor ones.
LOCAL_SKILLS_DIR = Path(__file__).parent / "skills"
VENDOR_SKILLS_DIR = Path(__file__).parent.parent.parent / "vendor" / "ecc" / "skills"
# Back-compat alias (some code/tests referenced SKILLS_DIR).
SKILLS_DIR = VENDOR_SKILLS_DIR


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter fields from a markdown file using regex.

    Avoids a hard dependency on PyYAML for this simple key: value format.
    """
    fm = {}
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return fm
    for line in match.group(1).splitlines():
        kv = line.split(":", 1)
        if len(kv) == 2:
            fm[kv[0].strip()] = kv[1].strip()
    return fm


class SkillManager:
    def __init__(self):
        self.skills: dict[str, dict] = self._discover_skills()

    def _discover_skills(self) -> dict:
        """Scan vendor + local skill roots; load just name+description of each skill.

        Vendor first, then local — so local (SmartAgent's own) skills override any
        vendor skill with the same id.
        """
        skills = {}
        for root in (VENDOR_SKILLS_DIR, LOCAL_SKILLS_DIR):
            if not root.exists():
                continue
            for skill_dir in sorted(root.iterdir()):
                if not skill_dir.is_dir():
                    continue

                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue

                try:
                    with open(skill_file, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception:
                    continue

                fm = _parse_frontmatter(content)
                name = fm.get("name", skill_dir.name)
                desc = fm.get("description", "No description")

                skills[skill_dir.name] = {
                    "id": skill_dir.name,
                    "name": name,
                    "description": desc,
                    "path": str(skill_file),
                }

        return skills

    def get_skills_catalog(self) -> str:
        """Return a summarized catalog of available skills for the system prompt.

        Only includes the top 30 most commonly useful skills to keep prompt size manageable.
        All 246 skills remain available via the `load_skill` tool.
        """
        if not self.skills:
            return ""

        # Priority skills that are most commonly useful.
        # The first three are SmartAgent's core discipline skills (ported from Nexus):
        # research before building, debug before rewriting, clean usable UI.
        priority_skill_ids = [
            "research-first-design", "systematic-debugging", "ui-blueprint",
            "search-first", "verification-loop", "tdd-workflow", "security-review",
            "code-review", "backend-patterns", "python-patterns", "django-patterns",
            "fastapi-patterns", "api-design", "database-patterns", "docker-patterns",
            "git-workflow", "debugging", "error-handling", "logging-patterns",
            "testing-patterns", "performance-optimization", "refactoring",
            "documentation", "ci-cd", "monitoring", "dependency-management",
            "architecture-review", "data-validation", "async-patterns",
            "caching-patterns", "migration-patterns", "deployment", "code-generation",
        ]

        catalog = "\n## Available Skills\n"
        catalog += "Use the `load_skill` tool to load full instructions for any skill.\n\n"

        shown = 0
        # Show priority skills first
        for skill_id in priority_skill_ids:
            if skill_id in self.skills:
                info = self.skills[skill_id]
                catalog += f"- **{skill_id}**: {info['description']}\n"
                shown += 1

        # Fill remaining slots with other skills (up to 30 total)
        for skill_id, info in self.skills.items():
            if shown >= 30:
                break
            if skill_id not in priority_skill_ids:
                catalog += f"- **{skill_id}**: {info['description']}\n"
                shown += 1

        remaining = len(self.skills) - shown
        if remaining > 0:
            catalog += f"\n_...and {remaining} more skills available. Use `load_skill` with any skill name to load its instructions._\n"

        return catalog

    def load_skill_content(self, skill_id: str) -> str:
        """Load the full content of a specific skill."""
        skill = self.skills.get(skill_id)
        if not skill:
            return f"Error: Skill '{skill_id}' not found. Use get_skills_catalog() to see available skills."

        try:
            with open(skill["path"], "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error loading skill '{skill_id}': {e}"

    def reload(self):
        """Re-discover all skills (vendor + runtime extensions)."""
        self.skills = self._discover_skills()
        # Also load runtime extensions
        from pathlib import Path
        ext_skills_dir = Path("./data/extensions/skills")
        if ext_skills_dir.exists():
            for skill_dir in ext_skills_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue
                try:
                    content = skill_file.read_text(encoding="utf-8")
                    fm = _parse_frontmatter(content)
                    self.skills[skill_dir.name] = {
                        "id": skill_dir.name,
                        "name": fm.get("name", skill_dir.name),
                        "description": fm.get("description", "Runtime-created skill"),
                        "path": str(skill_file),
                    }
                except Exception:
                    continue


# Module-level singleton
skill_manager = SkillManager()
