"""Checks the simulator against Stadnyk (2025) Table 1 and basic mass balance."""
import pytest

from basin_simulator import PROVINCES, simulate_basin


def test_baseline_reproduces_table_1_steady_state():
    reaches = simulate_basin(40, 0, maa_enabled=False)["reaches"]
    for province, outflow, storage in zip(PROVINCES, (40, 60, 80), (50, 75, 100)):
        assert reaches[province]["outflow"] == pytest.approx(outflow)
        assert reaches[province]["end_storage"] == pytest.approx(storage)


@pytest.mark.parametrize("net_input, withdrawal, maa", [(40, 30, False), (20, 80, True), (60, 200, False)])
def test_mass_balance_closes_in_every_reach(net_input, withdrawal, maa):
    for reach in simulate_basin(net_input, withdrawal, maa)["reaches"].values():
        inputs = reach["initial_storage"] + reach["net_input"] + reach["inflow_from_upstream"]
        outputs = reach["withdrawal"] + reach["outflow"] + reach["end_storage"]
        assert inputs == pytest.approx(outputs)


def test_maa_keeps_border_flow_at_half_of_natural():
    natural = simulate_basin(40, 0, False)["reaches"]["Alberta"]["outflow"]
    with_maa = simulate_basin(40, 90, True)
    assert with_maa["alberta_permitted_withdrawal"] == pytest.approx(45)
    assert with_maa["reaches"]["Alberta"]["outflow"] == pytest.approx(0.5 * natural)


def test_withdrawal_cannot_exceed_water_on_hand():
    result = simulate_basin(40, 500, False)
    assert result["alberta_permitted_withdrawal"] == pytest.approx(90)
    assert result["reaches"]["Saskatchewan"]["inflow_from_upstream"] == pytest.approx(0)
