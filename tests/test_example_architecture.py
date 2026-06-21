from pathlib import Path

from graphify.schema import ENTITY_TYPES, RELATIONSHIP_TYPES


EXAMPLE = Path("examples/architecture/complex-commerce-platform.md")


def test_complex_architecture_example_exercises_the_full_extraction_schema() -> None:
    text = EXAMPLE.read_text(encoding="utf-8")

    assert "# Atlas Commerce Platform" in text
    assert {f"`{entity_type}`" for entity_type in ENTITY_TYPES} <= set(text.split())
    assert {f"`{relationship_type}`" for relationship_type in RELATIONSHIP_TYPES} <= set(
        text.split()
    )
    assert text.count("```mermaid") >= 3
    assert "## Extraction test questions" in text
