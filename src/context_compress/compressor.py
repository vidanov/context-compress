"""Core compression engine with semantic-aware rules."""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ContentType(Enum):
    SAFETY = "safety"
    PREFERENCE = "preference"
    REFERENCE = "reference"
    PERSONALITY = "personality"
    CODE = "code"
    PROCEDURE = "procedure"
    PROSE = "prose"


@dataclass
class CompressionConfig:
    strip_markdown: bool = True
    remove_blanks: bool = True
    collapse_lists: bool = True
    deduplicate: bool = True
    preserve_code_blocks: bool = True
    preserve_safety_rules: bool = True
    compression_level: str = "medium"  # light, medium, heavy


@dataclass
class CompressionResult:
    original: str
    compressed: str
    original_bytes: int = 0
    compressed_bytes: int = 0
    sections_classified: dict = field(default_factory=dict)

    @property
    def reduction_pct(self) -> float:
        if self.original_bytes == 0:
            return 0.0
        return (1 - self.compressed_bytes / self.original_bytes) * 100


# Patterns that indicate safety-critical content
SAFETY_PATTERNS = [
    r"(?i)\bnever\b.*\b(execute|delete|push|commit|overwrite|modify|remove)\b",
    r"(?i)\b(always|must)\b.*\b(ask|confirm|approval|permission)\b",
    r"(?i)\bdo not\b.*\b(without|unless)\b",
    r"(?i)\b(destructive|irreversible)\b",
    r"(?i)\bbefore\b.*\b(proceed|execute|act)\b.*\b(ask|confirm)\b",
]

# Patterns that indicate preferences
PREFERENCE_PATTERNS = [
    r"(?i)\b(always use|prefer|default to)\b",
    r"(?i)\bfor (python|javascript|typescript)\b.*\buse\b",
    r"(?i)\b(style|convention|format)\b.*\b(use|follow|apply)\b",
]

# Patterns that indicate reference/path content
REFERENCE_PATTERNS = [
    r"(?i)^(path|location|directory|folder):",
    r"/[A-Za-z][\w/.-]+",  # file paths
    r"(?i)\b(consult|reference|see|check)\b.*\.(md|yaml|json)\b",
]


def classify_section(text: str) -> ContentType:
    """Classify a section by its content type."""
    # Code blocks are never compressed
    if text.strip().startswith("```") or re.match(r"^\s{4}\S", text, re.MULTILINE):
        return ContentType.CODE

    # Safety needs multiple signals or very strong single signal
    safety_score = 0
    for pattern in SAFETY_PATTERNS:
        if re.search(pattern, text):
            safety_score += 1
    if safety_score >= 2 or (safety_score == 1 and len(text) < 200):
        return ContentType.SAFETY

    for pattern in PREFERENCE_PATTERNS:
        if re.search(pattern, text):
            return ContentType.PREFERENCE

    for pattern in REFERENCE_PATTERNS:
        if re.search(pattern, text):
            return ContentType.REFERENCE

    if re.search(r"(?i)\b(personality|tone|style|voice)\b", text):
        return ContentType.PERSONALITY

    if re.search(r"(?i)^\d+\.\s", text, re.MULTILINE):
        return ContentType.PROCEDURE

    return ContentType.PROSE


def compress_section(text: str, content_type: ContentType, config: CompressionConfig) -> str:
    """Compress a section based on its content type."""
    if content_type == ContentType.CODE:
        return text  # never touch code

    if content_type == ContentType.SAFETY and config.preserve_safety_rules:
        # Light compression only: strip formatting, keep full sentences
        return _strip_formatting(text)

    if content_type == ContentType.PREFERENCE:
        # Light-medium: strip formatting, keep explicit statements
        text = _strip_formatting(text)
        text = _remove_blanks(text)
        return text

    if content_type == ContentType.REFERENCE:
        # Heavy: strip everything, collapse to minimal
        text = _strip_formatting(text)
        text = _remove_blanks(text)
        text = _collapse_lists(text)
        text = _use_shorthand(text)
        return text

    if content_type in (ContentType.PERSONALITY, ContentType.PROSE):
        # Heavy compression
        text = _strip_formatting(text)
        text = _remove_blanks(text)
        text = _collapse_lists(text)
        text = _use_shorthand(text)
        text = _remove_filler(text)
        return text

    if content_type == ContentType.PROCEDURE:
        # Medium: keep structure, compress prose
        text = _strip_formatting(text)
        text = _remove_blanks(text)
        text = _remove_filler(text)
        return text

    return text


def _strip_formatting(text: str) -> str:
    """Remove markdown formatting markers."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # bold
    text = re.sub(r"\*(.+?)\*", r"\1", text)  # italic
    text = re.sub(r"(?<!`)`([^`]+)`(?!`)", r"\1", text)  # inline code (not code blocks)
    text = re.sub(r"^---+\s*$", "", text, flags=re.MULTILINE)  # horizontal rules
    text = re.sub(r"^\|[-:| ]+\|$", "", text, flags=re.MULTILINE)  # table separator rows
    return text


def _remove_blanks(text: str) -> str:
    """Remove excessive blank lines."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^(#+.*)\n\n", r"\1\n", text, flags=re.MULTILINE)  # blank after heading
    # Remove blank lines between list items
    text = re.sub(r"(^[-*] .+)\n\n([-*] )", r"\1\n\2", text, flags=re.MULTILINE)
    return text


def _collapse_lists(text: str) -> str:
    """Collapse short bullet lists into inline text."""
    lines = text.split("\n")
    result = []
    list_items = []

    for line in lines:
        if re.match(r"^[-*]\s+(.+)$", line):
            item = re.sub(r"^[-*]\s+", "", line).strip()
            if len(item) < 60:  # only collapse short items
                list_items.append(item)
                continue
        if list_items:
            if len(list_items) <= 5:
                result.append(". ".join(list_items))
            else:
                # keep as list if too many items
                for item in list_items:
                    result.append(f"- {item}")
            list_items = []
        result.append(line)

    if list_items:
        result.append(". ".join(list_items))

    return "\n".join(result)


def _use_shorthand(text: str) -> str:
    """Replace verbose phrases with shorthand."""
    replacements = [
        (r"(?i)\bis equivalent to\b", "="),
        (r"(?i)\bfor example\b", "e.g."),
        (r"(?i)\bthat is to say\b", "i.e."),
        (r"(?i)\bin order to\b", "to"),
        (r"(?i)\bmake sure to\b", ""),
        (r"(?i)\bplease note that\b", ""),
        (r"(?i)\bit is important to\b", ""),
        (r"(?i)\bwhen you are\b", "when"),
        (r"(?i)\byou should\b", ""),
        (r"(?i)\bensure that\b", ""),
        (r"(?i)\bthis is\b", "="),
        (r"(?i)\bwhich means\b", "→"),
        (r"(?i)\bif it exists\b", "(if exists)"),
        (r"(?i)\bdo not\b", "don't"),
        (r"(?i)\bDo NOT\b", "don't"),
        (r"(?i)\bshould be\b", "→"),
        (r"(?i)\bwill be\b", "→"),
        (r"(?i)\bcontains?\b", "has"),
        (r"(?i)\bincluding\b", "incl."),
        (r"(?i)\bwithout\b", "w/o"),
        (r"(?i)\bthrough\b", "via"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    # Clean up double spaces
    text = re.sub(r"  +", " ", text)
    return text


def _remove_filler(text: str) -> str:
    """Remove filler words and phrases."""
    fillers = [
        r"(?i)\bbasically\b,?\s*",
        r"(?i)\bessentially\b,?\s*",
        r"(?i)\bsimply\b\s*",
        r"(?i)\bjust\b\s*",
        r"(?i)\bactually\b,?\s*",
        r"(?i)\bof course\b,?\s*",
        r"(?i)\bthe following\b\s*",
        r"(?i)\bas needed\b",
        r"(?i)\bif needed\b",
        r"(?i)\bwhen appropriate\b",
        r"(?i)\bas appropriate\b",
        r"(?i)\bproperly\b\s*",
        r"(?i)\bcorrectly\b\s*",
    ]
    for filler in fillers:
        text = re.sub(filler, "", text)
    text = re.sub(r"  +", " ", text)
    return text


def compress_file(content: str, config: CompressionConfig | None = None) -> CompressionResult:
    """Compress a full file with semantic-aware rules."""
    if config is None:
        config = CompressionConfig()

    # First, protect code blocks by replacing them with placeholders
    code_blocks = []
    def save_code_block(match):
        code_blocks.append(match.group(0))
        return f"__CODE_BLOCK_{len(code_blocks) - 1}__"

    protected = re.sub(r"```[\s\S]*?```", save_code_block, content)

    sections = _split_into_sections(protected)
    compressed_parts = []
    classifications = {}

    for heading, body in sections:
        content_type = classify_section(body)
        classifications[heading or "(top)"] = content_type.value

        compressed_body = compress_section(body, content_type, config)

        if heading:
            compressed_parts.append(f"{heading}\n{compressed_body}")
        else:
            compressed_parts.append(compressed_body)

    compressed = "\n\n".join(compressed_parts)

    # Restore code blocks
    for i, block in enumerate(code_blocks):
        compressed = compressed.replace(f"__CODE_BLOCK_{i}__", block)

    # Final cleanup
    compressed = re.sub(r"\n{3,}", "\n\n", compressed)

    return CompressionResult(
        original=content,
        compressed=compressed,
        original_bytes=len(content.encode()),
        compressed_bytes=len(compressed.encode()),
        sections_classified=classifications,
    )


def _split_into_sections(content: str) -> list[tuple[str | None, str]]:
    """Split markdown into (heading, body) pairs."""
    lines = content.split("\n")
    sections = []
    current_heading = None
    current_body = []

    for line in lines:
        if re.match(r"^#{1,3}\s", line):
            if current_heading is not None or current_body:
                sections.append((current_heading, "\n".join(current_body)))
            current_heading = line
            current_body = []
        else:
            current_body.append(line)

    if current_heading is not None or current_body:
        sections.append((current_heading, "\n".join(current_body)))

    return sections


def find_duplicates(files: dict[str, str]) -> dict[str, list[str]]:
    """Find duplicate/overlapping content across files."""
    # Extract key phrases from each file
    phrase_locations: dict[str, list[str]] = {}

    for filename, content in files.items():
        # Extract sentences/rules
        sentences = re.split(r"[.\n]", content)
        for sentence in sentences:
            cleaned = sentence.strip().lower()
            if len(cleaned) > 30:  # only meaningful phrases
                if cleaned not in phrase_locations:
                    phrase_locations[cleaned] = []
                phrase_locations[cleaned].append(filename)

    # Return only duplicates
    return {phrase: locs for phrase, locs in phrase_locations.items() if len(locs) > 1}
