import pytest
from bus_transit_fare import process_commute_manifest, inspect_smartcard_turnstiles


def manifest(route_type="local", commuters=None, priority=False, active=True):
    return {
        "route_active": active,
        "route_type": route_type,
        "priority_boarding": priority,
        "commuters": commuters if commuters is not None else [],
    }


def commuter(zones=1, kind="regular", blacklisted=False):
    return {"zones": zones, "type": kind, "blacklisted": blacklisted}


# process_commute_manifest

def test_single_regular_local_ride():
    result = process_commute_manifest([manifest(commuters=[commuter(2)])], 2.0)
    assert result["total_fare"] == 4.5
    assert result["status"] == "COMPLETED"


def test_manifests_not_a_list_raises():
    with pytest.raises(ValueError):
        process_commute_manifest("not a list", 1.0)


def test_negative_booking_fee_raises():
    with pytest.raises(ValueError):
        process_commute_manifest([], -1.0)


def test_inactive_route_is_skipped():
    result = process_commute_manifest(
        [manifest(commuters=[commuter(2)], active=False)], 1.0)
    assert result == {"total_fare": 0.0, "status": "ZERO_RIDERSHIP"}


def test_express_regular_fare():
    result = process_commute_manifest(
        [manifest("express", [commuter(1)])], 0.0)
    assert result == {"total_fare": 7.0, "status": "COMPLETED"}


def test_shuttle_student_fare():
    result = process_commute_manifest(
        [manifest("shuttle", [commuter(2, "student")])], 0.0)
    assert result == {"total_fare": 2.5, "status": "COMPLETED"}


def test_local_senior_fare():
    result = process_commute_manifest(
        [manifest("local", [commuter(2, "senior")])], 0.0)
    assert result["total_fare"] == pytest.approx(2.45)
    assert result["status"] == "COMPLETED"


def test_unknown_route_type_is_rejected():
    result = process_commute_manifest(
        [manifest("ferry", [commuter(1)])], 0.0)
    assert result == {"total_fare": 0.0, "status": "ZERO_RIDERSHIP"}


def test_zero_zones_is_rejected():
    result = process_commute_manifest(
        [manifest("local", [commuter(0)])], 0.0)
    assert result == {"total_fare": 0.0, "status": "ZERO_RIDERSHIP"}


def test_blacklisted_card_on_local_route_is_skipped():
    result = process_commute_manifest(
        [manifest("local", [commuter(1, blacklisted=True), commuter(2)])], 0.0)
    assert result == {"total_fare": 4.5, "status": "COMPLETED"}


def test_priority_boarding_adds_booking_fee():
    result = process_commute_manifest(
        [manifest("local", [commuter(1)], priority=True)], 2.0)
    assert result == {"total_fare": 5.5, "status": "COMPLETED"}


def test_more_than_four_rejections_fails_audit():
    commuters = [commuter(0) for _ in range(5)]
    result = process_commute_manifest([manifest("local", commuters)], 0.0)
    assert result == {"total_fare": 0.0, "status": "AUDIT_REJECTED"}


# inspect_smartcard_turnstiles

def test_turnstiles_no_data():
    assert inspect_smartcard_turnstiles([]) == "NO_DATA"


def test_turnstiles_operational():
    assert inspect_smartcard_turnstiles([[0, 1, 2]]) == "OPERATIONAL"
