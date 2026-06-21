import pytest

from grach.schema import validate_extraction


def test_validation_accepts_canonical_equivalent_relationship_entity_names() -> None:
    extraction = {
        "entities": [
            {"name": "Order Service", "type": "Service", "aliases": []},
            {"name": "Orders Database", "type": "Database", "aliases": []},
        ],
        "relationships": [
            {
                "source": "order-service",
                "source_type": "Service",
                "type": "USES_DATABASE",
                "target": "orders database",
                "target_type": "Database",
                "confidence": 1.0,
            }
        ],
    }

    validate_extraction(extraction)


def test_validation_rejects_reversed_owned_by_relationship() -> None:
    extraction = {
        "entities": [
            {"name": "Order Service", "type": "Service", "aliases": []},
            {"name": "Commerce Team", "type": "Team", "aliases": []},
        ],
        "relationships": [
            {
                "source": "Commerce Team",
                "source_type": "Team",
                "type": "OWNED_BY",
                "target": "Order Service",
                "target_type": "Service",
                "confidence": 1.0,
            }
        ],
    }

    with pytest.raises(ValueError, match="OWNED_BY requires .* -> Team"):
        validate_extraction(extraction)


def test_validation_rejects_exposes_between_unsupported_endpoint_types() -> None:
    extraction = {
        "entities": [
            {"name": "Order Service", "type": "Service", "aliases": []},
            {"name": "Submit Order", "type": "Endpoint", "aliases": []},
        ],
        "relationships": [
            {
                "source": "Order Service",
                "source_type": "Service",
                "type": "EXPOSES",
                "target": "Submit Order",
                "target_type": "Endpoint",
                "confidence": 1.0,
            }
        ],
    }

    with pytest.raises(ValueError, match="EXPOSES requires API -> Endpoint or Service -> API"):
        validate_extraction(extraction)
