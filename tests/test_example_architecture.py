from pathlib import Path

from grach.schema import ENTITY_TYPES, RELATIONSHIP_TYPES


EXAMPLE = Path("examples/architecture/complex-commerce-platform.md")
SIMPLE_EXAMPLE = Path("examples/architecture-simple/order-system.md")


def test_complex_architecture_example_exercises_the_full_extraction_schema() -> None:
    text = EXAMPLE.read_text(encoding="utf-8")

    assert "# Atlas Commerce Platform" in text
    assert {f"`{entity_type}`" for entity_type in ENTITY_TYPES} <= set(text.split())
    assert {f"`{relationship_type}`" for relationship_type in RELATIONSHIP_TYPES} <= set(
        text.split()
    )
    assert text.count("```mermaid") >= 3
    assert "## Extraction test questions" in text


def test_simple_architecture_example_has_a_small_explicit_graph() -> None:
    text = SIMPLE_EXAMPLE.read_text(encoding="utf-8")

    assert "# Simple Order System" in text
    assert "## Entities" in text
    assert "## Relationships" in text
    assert text.count("```mermaid") == 1
    assert text.count("| `Service` |") == 2
    assert text.count("| `Database` |") == 1
    assert text.count("| `Team` |") == 1
    assert text.count("| `USES_DATABASE` |") == 1
    assert text.count("| `CALLS` |") == 1
    assert text.count("| `OWNED_BY` |") == 2
