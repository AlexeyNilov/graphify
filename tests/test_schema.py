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
