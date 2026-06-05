"""
Agent Manager — reads ECC agent definitions from vendor/ecc/agents/.

Each agent is a .md file with YAML frontmatter:
    ---
    name: agent-name
    description: What this agent does
    tools: [...]
    model: ...
    ---
    ... full agent definition ...

Progressive disclosure:
  - get_agents_catalog() returns only name+description for the system prompt.
  - load_agent_content(agent_id) loads full markdown on demand (via load_agent tool).
"""

import re
from pathlib import Path

AGENTS_DIR = Path(__file__).parent.parent.parent / "vendor" / "ecc" / "agents"


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter fields from a markdown file."""
    fm = {}
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return fm
    for line in match.group(1).splitlines():
        kv = line.split(":", 1)
        if len(kv) == 2:
            fm[kv[0].strip()] = kv[1].strip()
    return fm


def _extract_first_paragraph(text: str) -> str:
    """Extract the first non-empty paragraph after frontmatter as a fallback description."""
    # Strip frontmatter
    body = re.sub(r"^---\s*\n.*?\n---\s*\n?", "", text, flags=re.DOTALL)
    # Skip headings, find first paragraph
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Return first non-heading, non-empty line (truncated)
        return stripped[:200]
    return "No description"


class AgentManager:
    def __init__(self):
        self.agents: dict[str, dict] = self._discover_agents()

    def _discover_agents(self) -> dict:
        """Scan AGENTS_DIR and load name+description of each agent."""
        agents = {}
        if not AGENTS_DIR.exists():
            return agents

        for agent_file in sorted(AGENTS_DIR.glob("*.md")):
            try:
                with open(agent_file, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            fm = _parse_frontmatter(content)
            agent_id = agent_file.stem  # e.g. "architect" from "architect.md"
            name = fm.get("name", agent_id)
            desc = fm.get("description", _extract_first_paragraph(content))

            agents[agent_id] = {
                "id": agent_id,
                "name": name,
                "description": desc,
                "path": str(agent_file),
            }

        return agents

    def get_agents_catalog(self) -> str:
        """Return a summarized catalog of available agents for the system prompt.

        Only includes top 15 most commonly useful agents to keep prompt size manageable.
        All 61 agents remain available via the `load_agent` tool.
        """
        if not self.agents:
            return ""

        # Priority agents that are most commonly useful
        priority_agent_ids = [
            "planner", "architect", "code-reviewer", "security-reviewer",
            "build-error-resolver", "tdd-guide", "python-reviewer",
            "fastapi-reviewer", "debugger", "refactorer",
            "performance-optimizer", "documentation-writer",
            "devops-engineer", "database-architect", "e2e-runner",
        ]

        catalog = "\n## Available Agents\n"
        catalog += "Use the `load_agent` tool to load a specialist agent's full definition.\n\n"

        shown = 0
        for agent_id in priority_agent_ids:
            if agent_id in self.agents:
                info = self.agents[agent_id]
                catalog += f"- **{agent_id}**: {info['description']}\n"
                shown += 1

        for agent_id, info in self.agents.items():
            if shown >= 15:
                break
            if agent_id not in priority_agent_ids:
                catalog += f"- **{agent_id}**: {info['description']}\n"
                shown += 1

        remaining = len(self.agents) - shown
        if remaining > 0:
            catalog += f"\n_...and {remaining} more specialist agents available. Use `load_agent` with any agent name._\n"

        return catalog

    def load_agent_content(self, agent_id: str) -> str:
        """Load the full content of a specific agent definition."""
        agent = self.agents.get(agent_id)
        if not agent:
            return f"Error: Agent '{agent_id}' not found. Available agents: {', '.join(self.agents.keys())}"

        try:
            with open(agent["path"], "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error loading agent '{agent_id}': {e}"


# Module-level singleton
agent_manager = AgentManager()
