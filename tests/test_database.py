from types import SimpleNamespace

import pytest
from sqlalchemy.exc import StatementError

from backend.database import Database


def test_later_insert_failure_rolls_back_entire_prediction_transaction(fake_service):
    from backend.schemas import FlowInput
    database = Database("sqlite://")
    database.initialize()
    valid = FlowInput(features={"duration": 100, "packet_rate": 1})
    output = fake_service.predict([valid])[0]
    invalid_json = SimpleNamespace(features={"unsupported": object()})
    try:
        with pytest.raises(StatementError):
            database.save_predictions([output, output], [valid, invalid_json])
        assert database.stats()["total_flows"] == 0
        assert database.alerts(20, 0) == []
    finally:
        database.close()
