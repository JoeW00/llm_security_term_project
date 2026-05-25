import json
from pathlib import Path

import pytest

from soc_agent.state import Alert

ALERT_DIR = Path(__file__).parents[1] / "data" / "sample_alerts"
FIXTURES = sorted(ALERT_DIR.glob("*.json"))


def test_fixtures_present():
    assert FIXTURES, "expected sample alert JSON files under data/sample_alerts/"


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_sample_alert_validates(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    alert = Alert.model_validate(data)
    assert alert.source
    assert alert.message
