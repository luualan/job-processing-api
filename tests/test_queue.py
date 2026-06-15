import time

from tests.test_api import client, _get_type_field


def test_priority_ordering():
    # create three jobs with different priorities
    client.post("/jobs", json={"type": "low", "payload": {}, "priority": 0})
    client.post("/jobs", json={"type": "high", "payload": {}, "priority": 10})
    client.post("/jobs", json={"type": "mid", "payload": {}, "priority": 5})

    # claim order should be high, mid, low
    c1 = client.post("/jobs/claim")
    assert c1.status_code == 200
    assert _get_type_field(c1.json()) == "high"

    c2 = client.post("/jobs/claim")
    assert c2.status_code == 200
    assert _get_type_field(c2.json()) == "mid"

    c3 = client.post("/jobs/claim")
    assert c3.status_code == 200
    assert _get_type_field(c3.json()) == "low"


def test_fifo_tiebreaker():
    # create two jobs with same priority; ensure older is claimed first
    client.post("/jobs", json={"type": "first", "payload": {}, "priority": 1})
    # small sleep to ensure created_at ordering
    time.sleep(0.01)
    client.post("/jobs", json={"type": "second", "payload": {}, "priority": 1})

    c1 = client.post("/jobs/claim")
    assert c1.status_code == 200
    assert _get_type_field(c1.json()) == "first"

    c2 = client.post("/jobs/claim")
    assert c2.status_code == 200
    assert _get_type_field(c2.json()) == "second"
