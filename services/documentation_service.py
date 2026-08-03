from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata


DOCUMENTATION_DIR = Path(__file__).resolve().parent.parent / "documentation"
INITIAL_DOCUMENT = "introduction.md"
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class DocumentationSection:
    title: str
    level: int
    line_index: int


@dataclass(frozen=True)
class DocumentationDocument:
    filename: str
    title: str
    content: str
    sections: tuple[DocumentationSection, ...]


@dataclass(frozen=True)
class DocumentationSearchResult:
    filename: str
    title: str
    subtitle: str
    excerpt: str


class DocumentationService:
    def __init__(self, documentation_dir: Path = DOCUMENTATION_DIR):
        self.documentation_dir = documentation_dir

    def list_documents(self) -> list[DocumentationDocument]:
        documents = [
            self._load_document(path)
            for path in self.documentation_dir.glob("*.md")
            if path.is_file()
        ]
        return sorted(documents, key=self._document_sort_key)

    def get_document(self, filename: str) -> DocumentationDocument | None:
        safe_name = Path(filename).name
        path = self.documentation_dir / safe_name
        if path.suffix.lower() != ".md" or not path.is_file():
            return None
        return self._load_document(path)

    def search(
        self,
        query: str,
        documents: list[DocumentationDocument] | None = None,
        *,
        limit: int = 12,
    ) -> list[DocumentationSearchResult]:
        documents = documents if documents is not None else self.list_documents()
        tokens = [token for token in _normalize(query).split() if token]

        if not tokens:
            return [
                DocumentationSearchResult(
                    filename=document.filename,
                    title=document.title,
                    subtitle="Documento",
                    excerpt=_first_meaningful_line(document.content),
                )
                for document in documents[:limit]
            ]

        results: list[tuple[int, DocumentationSearchResult]] = []
        for document in documents:
            searchable_document = _normalize(f"{document.title} {document.filename}")
            if _matches_all(tokens, searchable_document):
                results.append(
                    (
                        80,
                        DocumentationSearchResult(
                            filename=document.filename,
                            title=document.title,
                            subtitle="Documento",
                            excerpt=_first_meaningful_line(document.content),
                        ),
                    )
                )

            for section in document.sections:
                searchable_section = _normalize(section.title)
                if _matches_all(tokens, searchable_section):
                    results.append(
                        (
                            70 - section.level,
                            DocumentationSearchResult(
                                filename=document.filename,
                                title=section.title,
                                subtitle=document.title,
                                excerpt=self._section_excerpt(document, section),
                            ),
                        )
                    )

            matching_line = self._matching_content_line(document.content, tokens)
            if matching_line:
                results.append(
                    (
                        40,
                        DocumentationSearchResult(
                            filename=document.filename,
                            title=document.title,
                            subtitle="Trecho encontrado",
                            excerpt=matching_line,
                        ),
                    )
                )

        ordered_results = sorted(results, key=lambda item: (-item[0], _normalize(item[1].title)))
        unique_results: list[DocumentationSearchResult] = []
        seen: set[tuple[str, str]] = set()

        for _, result in ordered_results:
            result_key = (result.filename, result.title)
            if result_key in seen:
                continue
            seen.add(result_key)
            unique_results.append(result)
            if len(unique_results) >= limit:
                break

        return unique_results

    def _load_document(self, path: Path) -> DocumentationDocument:
        content = path.read_text(encoding="utf-8")
        sections = _extract_sections(content)
        title = sections[0].title if sections and sections[0].level == 1 else _title_from_filename(path.name)
        return DocumentationDocument(
            filename=path.name,
            title=title,
            content=content,
            sections=tuple(sections),
        )

    def _document_sort_key(self, document: DocumentationDocument) -> tuple[int, str]:
        is_initial = document.filename == INITIAL_DOCUMENT
        return (0 if is_initial else 1, _normalize(document.title))

    def _section_excerpt(self, document: DocumentationDocument, section: DocumentationSection) -> str:
        lines = document.content.splitlines()
        for line in lines[section.line_index + 1 :]:
            cleaned_line = line.strip()
            if not cleaned_line or cleaned_line.startswith("#"):
                continue
            return _trim_markdown_line(cleaned_line)
        return "Seção do documento."

    def _matching_content_line(self, content: str, tokens: list[str]) -> str:
        for line in content.splitlines():
            cleaned_line = line.strip()
            if not cleaned_line or cleaned_line.startswith("#"):
                continue
            if _matches_all(tokens, _normalize(cleaned_line)):
                return _trim_markdown_line(cleaned_line)
        return ""


def resolve_document_link(current_filename: str, link_target: str) -> str | None:
    link = (link_target or "").split("#", 1)[0].strip()
    if not link:
        return current_filename

    if "://" in link or link.startswith("mailto:"):
        return None

    linked_name = Path(link).name
    if linked_name.endswith(".md"):
        return linked_name
    return None


def _extract_sections(content: str) -> list[DocumentationSection]:
    sections: list[DocumentationSection] = []
    for index, line in enumerate(content.splitlines()):
        match = HEADING_PATTERN.match(line)
        if match:
            sections.append(
                DocumentationSection(
                    title=match.group(2).strip(),
                    level=len(match.group(1)),
                    line_index=index,
                )
            )
    return sections


def _title_from_filename(filename: str) -> str:
    return Path(filename).stem.replace("-", " ").replace("_", " ").title()


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def _matches_all(tokens: list[str], searchable: str) -> bool:
    return all(token in searchable for token in tokens)


def _first_meaningful_line(content: str) -> str:
    for line in content.splitlines():
        cleaned_line = line.strip()
        if cleaned_line and not cleaned_line.startswith("#"):
            return _trim_markdown_line(cleaned_line)
    return "Documento Markdown."


def _trim_markdown_line(value: str, limit: int = 150) -> str:
    cleaned_value = re.sub(r"`([^`]+)`", r"\1", value)
    cleaned_value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned_value)
    cleaned_value = cleaned_value.strip("-* ")
    if len(cleaned_value) <= limit:
        return cleaned_value
    return f"{cleaned_value[: limit - 3].rstrip()}..."
