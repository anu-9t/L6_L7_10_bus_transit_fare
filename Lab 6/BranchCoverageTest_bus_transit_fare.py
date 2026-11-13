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


def test_blacklisted_card_on_express_route_clears_manifest_fare():
    commuters = [commuter(1), commuter(1, blacklisted=True), commuter(1)]
    result = process_commute_manifest([manifest("express", commuters)], 0.0)
    assert result == {"total_fare": 0.0, "status": "ZERO_RIDERSHIP"}


def test_blacklisted_express_card_still_charges_booking_fee():
    commuters = [commuter(1), commuter(1, blacklisted=True)]
    result = process_commute_manifest(
        [manifest("express", commuters, priority=True)], 3.0)
    assert result == {"total_fare": 3.0, "status": "COMPLETED"}


def test_exactly_four_rejections_does_not_fail_audit():
    commuters = [commuter(0) for _ in range(4)] + [commuter(2)]
    result = process_commute_manifest([manifest("local", commuters)], 0.0)
    assert result == {"total_fare": 4.5, "status": "COMPLETED"}


def test_rejections_across_manifests_are_added_up():
    manifests = [manifest("ferry", [commuter(1)]) for _ in range(5)]
    result = process_commute_manifest(manifests, 0.0)
    assert result["status"] == "AUDIT_REJECTED"


def test_audit_rejected_still_reports_total_fare():
    manifests = [manifest("local", [commuter(1)])]
    manifests += [manifest("ferry", [commuter(1)]) for _ in range(5)]
    result = process_commute_manifest(manifests, 0.0)
    assert result == {"total_fare": 3.5, "status": "AUDIT_REJECTED"}


def test_missing_keys_use_defaults():
    # no route_type -> local, commuter with no keys -> 1 zone, regular
    result = process_commute_manifest(
        [{"route_active": True, "commuters": [{}]}], 0.0)
    assert result == {"total_fare": 3.5, "status": "COMPLETED"}


def test_manifest_without_route_active_is_skipped():
    assert process_commute_manifest([{}], 0.0)["status"] == "ZERO_RIDERSHIP"


def test_active_route_with_no_commuters_is_zero_ridership():
    result = process_commute_manifest([manifest("shuttle", [])], 0.0)
    assert result["status"] == "ZERO_RIDERSHIP"


def test_empty_manifest_list_is_zero_ridership():
    assert process_commute_manifest([], 0.0) == {
        "total_fare": 0.0, "status": "ZERO_RIDERSHIP"}


def test_zero_booking_fee_is_allowed():
    result = process_commute_manifest([manifest(commuters=[commuter(1)])], 0.0)
    assert result["status"] == "COMPLETED"


def test_negative_zones_is_rejected():
    result = process_commute_manifest(
        [manifest("local", [commuter(-2), commuter(1)])], 0.0)
    assert result == {"total_fare": 3.5, "status": "COMPLETED"}


def test_senior_and_student_on_express_route():
    commuters = [commuter(2, "student"), commuter(2, "senior")]
    result = process_commute_manifest([manifest("express", commuters)], 0.0)
    assert result["total_fare"] == pytest.approx(3.5 + 4.9)


def test_fares_from_several_manifests_are_added():
    manifests = [manifest("local", [commuter(1)]),
                 manifest("shuttle", [commuter(1)])]
    result = process_commute_manifest(manifests, 0.0)
    assert result == {"total_fare": 8.5, "status": "COMPLETED"}


# inspect_smartcard_turnstiles

def test_turnstiles_jam_on_two_failures_in_a_row():
    assert inspect_smartcard_turnstiles([[4, 5]]) == "TURNSTILE_JAM"


def test_turnstiles_single_failure_is_not_a_jam():
    assert inspect_smartcard_turnstiles([[4]]) == "OPERATIONAL"


def test_turnstiles_streak_resets_after_a_good_reading():
    assert inspect_smartcard_turnstiles([[4, 0, 4]]) == "OPERATIONAL"


def test_turnstiles_three_failures_is_not_counted():
    assert inspect_smartcard_turnstiles([[3, 3, 3]]) == "OPERATIONAL"


def test_turnstiles_streak_does_not_carry_between_devices():
    assert inspect_smartcard_turnstiles([[4], [4]]) == "OPERATIONAL"


def test_turnstiles_jam_on_second_device():
    assert inspect_smartcard_turnstiles([[0, 1], [2, 4, 9]]) == "TURNSTILE_JAM"


def test_turnstiles_device_with_no_readings():
    assert inspect_smartcard_turnstiles([[]]) == "OPERATIONAL"
