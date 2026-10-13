"""Checks the flow-through simulator: Table 1 split, mass balance, and MAA rules."""
import pytest

from basin_simulator import PROVINCES, simulate_basin


def test_no_withdrawal_passes_everything_with_2_1_1_split():
    reaches = simulate_basin(40, 0, 0, maa_enabled=False)["reaches"]
    for province, outflow in zip(PROVINCES, (40, 60, 80)):
        assert reaches[province]["outflow"] == pytest.approx(outflow)


def test_alberta_taking_everything_passes_nothing():
    reaches = simulate_basin(40, 100, 0, maa_enabled=False)["reaches"]
    assert reaches["Alberta"]["outflow"] == pytest.approx(0)
    assert reaches["Saskatchewan"]["inflow_from_upstream"] == pytest.approx(0)
    assert reaches["Manitoba"]["inflow_from_upstream"] == pytest.approx(20)


@pytest.mark.parametrize("generated, ab, sk, maa",
                         [(40, 30, 50, False), (20, 100, 100, True), (60, 75, 10, True)])
def test_mass_balance_closes_in_every_province(generated, ab, sk, maa):
    for reach in simulate_basin(generated, ab, sk, maa)["reaches"].values():
        assert reach["inflow_from_upstream"] + reach["water_generated"] == pytest.approx(
            reach["withdrawal"] + reach["outflow"])


def test_maa_alberta_passes_half_of_what_it_generates():
    reaches = simulate_basin(40, 100, 0, maa_enabled=True)["reaches"]
    assert reaches["Alberta"]["withdrawal"] == pytest.approx(20)
    assert reaches["Alberta"]["outflow"] == pytest.approx(20)


def test_maa_saskatchewan_passes_half_of_natural_flow_at_its_border():
    reaches = simulate_basin(40, 100, 100, maa_enabled=True)["reaches"]
    # natural flow at SK/MB border = 40 + 20 = 60, so at least 30 must pass
    assert reaches["Saskatchewan"]["outflow"] == pytest.approx(30)
    assert reaches["Saskatchewan"]["withdrawal"] == pytest.approx(10)


def test_alberta_overuse_shrinks_saskatchewan_allowance():
    sk_room_when_alberta_takes_nothing = simulate_basin(40, 0, 100, True)["maa_limits"]["Saskatchewan"]
    sk_room_when_alberta_takes_half = simulate_basin(40, 50, 100, True)["maa_limits"]["Saskatchewan"]
    assert sk_room_when_alberta_takes_nothing == pytest.approx(30)
    assert sk_room_when_alberta_takes_half == pytest.approx(10)