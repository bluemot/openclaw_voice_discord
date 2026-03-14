import os
import re
import toml
from typing import List, Optional, Set
from loguru import logger
from pathlib import Path

from .schemas import Skill, SkillMetadata


class SkillsRegistry:
    """
    Manages loading and matching of domain-specific skills.
    Skills are stored as Markdown files with TOML frontmatter.
    """
    def __init__(self, skills_dir: Optional[str] = None):
        if skills_dir is None:
            # Default to 'skills' directory in the project root
            self.skills_dir = Path(__file__).parent.parent.parent.parent / "skills"
        else:
            self.skills_dir = Path(skills_dir)
            
        self.skills: List[Skill] = []
        self._load_skills()

    def _load_skills(self) -> None:
        """Loads all .md files from the skills directory."""
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return

        for file_path in self.skills_dir.glob("*.md"):
            try:
                skill = self._parse_skill_file(file_path)
                if skill:
                    self.skills.append(skill)
                    logger.info(f"Loaded skill: {skill.metadata.name}")
            except Exception as e:
                logger.error(f"Failed to load skill from {file_path}: {e}")

    def _parse_skill_file(self, file_path: Path) -> Optional[Skill]:
        """Parses a skill file with TOML frontmatter (delimited by +++)."""
        content = file_path.read_text(encoding="utf-8")
        
        # Regex to match +++ toml +++ content
        pattern = r"^\+\+\+\s*\n(.*?)\n\+\+\+\s*\n(.*)$"
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            logger.debug(f"No frontmatter found in {file_path}")
            return None
            
        toml_str = match.group(1)
        md_content = match.group(2).strip()
        
        try:
            metadata_dict = toml.loads(toml_str)
            metadata = SkillMetadata(**metadata_dict)
            return Skill(
                metadata=metadata,
                content=md_content,
                file_path=str(file_path)
            )
        except Exception as e:
            logger.error(f"Error parsing metadata in {file_path}: {e}")
            return None

    def get_relevant_skills(
        self, 
        query: str, 
        project_type: Optional[str] = None,
        limit: int = 3
    ) -> List[Skill]:
        """
        Matches skills based on keywords in the query and project type.
        Returns skills sorted by priority.
        """
        query_lower = query.lower()
        matched_skills = []

        for skill in self.skills:
            # Match by project type (if specified)
            if project_type and skill.metadata.project_types:
                if project_type.lower() not in [pt.lower() for pt in skill.metadata.project_types]:
                    continue

            # Match by keywords in query
            keyword_match = False
            for kw in skill.metadata.keywords:
                if kw.lower() in query_lower:
                    keyword_match = True
                    break
            
            if keyword_match or not skill.metadata.keywords:
                matched_skills.append(skill)

        # Sort by priority (descending)
        matched_skills.sort(key=lambda s: s.metadata.priority, reverse=True)
        
        return matched_skills[:limit]

    def format_skills_for_prompt(self, skills: List[Skill]) -> str:
        """Formats a list of skills into a single prompt block."""
        if not skills:
            return ""
            
        sections = [skill.to_prompt() for skill in skills]
        combined = "\n---\n".join(sections)
        
        return f"\n\n[SYSTEM DOMAIN SKILLS]\n{combined}\n"

    def reload(self) -> None:
        """Reload all skills from disk."""
        self.skills.clear()
        self._load_skills()