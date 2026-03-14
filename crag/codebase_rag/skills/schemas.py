from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SkillMetadata(BaseModel):
    """Metadata for a skill, parsed from TOML frontmatter."""
    name: str
    description: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    project_types: List[str] = Field(default_factory=list)
    priority: int = 10  # Higher means more important


class Skill(BaseModel):
    """A complete skill with metadata and content."""
    metadata: SkillMetadata
    content: str
    file_path: Optional[str] = None

    def to_prompt(self) -> str:
        """Converts the skill to a formatted prompt block."""
        header = f"### SKILL: {self.metadata.name}"
        if self.metadata.description:
            header += f" ({self.metadata.description})"
        
        return f"{header}\n{self.content}\n"