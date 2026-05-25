from __future__ import annotations

from typing import Any, Protocol

from .models import BookProject, Chapter, WritingContext
from .strategies import ThemeStrategy, get_strategy


class IGenreEngine(Protocol):
    def get_genre_name(self) -> str:
        ...

    def get_supported_themes(self) -> list[str]:
        ...

    def get_theme_strategy(self, theme_name: str) -> ThemeStrategy:
        ...

    def write_chapter(self, project: BookProject, context: WritingContext) -> Chapter:
        ...


class FictionGenreEngine:
    def get_genre_name(self) -> str:
        return "fiction"

    def get_supported_themes(self) -> list[str]:
        return ["mystery", "sci_fi", "xuanhuan"]

    def get_theme_strategy(self, theme_name: str) -> ThemeStrategy:
        return get_strategy(theme_name)

    def write_chapter(self, project: BookProject, context: WritingContext) -> Chapter:
        strategy = self.get_theme_strategy(project.meta["theme"])
        chapter_no = len(project.chapters) + 1
        title, text = strategy.build_chapter_text({"creation_params": project.creation_params}, chapter_no)
        from .models import new_id

        return Chapter(
            id=new_id("chapter"),
            chapter_no=chapter_no,
            title=title,
            text=text,
            outline_summary=context.immediate_context.get("outline_summary", ""),
        )


def build_default_context(project: BookProject) -> WritingContext:
    previous = project.chapters[-1] if project.chapters else None
    current_no = len(project.chapters) + 1
    outline = project.outline[current_no - 1] if current_no <= len(project.outline) else {}
    return WritingContext(
        style_anchor={
            "pov": project.creation_params.get("narrative_pov"),
            "tone": project.creation_params.get("tone", []),
        },
        structural_summary={
            "plot_structure": project.plot_structure,
            "outline_progress": f"{len(project.chapters)}/{len(project.outline)}",
        },
        narrative_state={
            "characters": project.characters,
            "foreshadows": project.foreshadowing_registry,
            "tracking_tables": project.theme_tracking_tables,
        },
        immediate_context={
            "previous_chapter_tail": previous.text[-240:] if previous else "",
            "outline_summary": outline.get("summary", ""),
            "chapter_no": current_no,
        },
    )
