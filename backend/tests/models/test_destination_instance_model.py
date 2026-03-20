from __future__ import annotations

from app.models.destination_instance import DestinationInstance


def test_destination_instance_model_exposes_expected_columns() -> None:
    table = DestinationInstance.__table__

    assert "id" in table.c
    assert "user_id" in table.c
    assert "type" in table.c
    assert "name" in table.c
    assert "enabled" in table.c
    assert "config" in table.c
    assert "created_at" in table.c
    assert "updated_at" in table.c
    assert table.c.type.nullable is False
    assert table.c.name.nullable is False
    assert table.c.enabled.nullable is False
    assert table.c.config.nullable is False
