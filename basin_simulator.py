import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium", app_title="Prairie River Basin Simulator")

with app.setup:
    import marimo as mo
    import matplotlib.pyplot as plt

    # Three control volumes in series, upstream to downstream
    # (Saskatchewan–Nelson River basin; Stadnyk 2025, Fig. 1).
    PROVINCES = ("Alberta", "Saskatchewan", "Manitoba")

    # Initial storage S_i by reach, in water units (Stadnyk 2025, Table 1).
    INITIAL_STORAGE = {"Alberta": 50.0, "Saskatchewan": 75.0, "Manitoba": 100.0}

    # Saskatchewan and Manitoba each receive half of Alberta's net input,
    # preserving the 2:1:1 split of Table 1 (P_net = 40 / 20 / 20).
    DOWNSTREAM_INPUT_RATIO = 0.5

    # Storage constant k (years). Each year a reach releases 1/k of the water
    # it holds after withdrawals. k = 2.25 reproduces Table 1 exactly when
    # nothing is withdrawn: every reach passes on 40 / 60 / 80 units and
    # its storage stays at 50 / 75 / 100 (a steady-state baseline).
    STORAGE_CONSTANT_K = 2.25

    # Master Agreement on Apportionment (PPWB 1969): flow crossing a
    # provincial border must be at least 50% of the natural flow.
    MAA_MINIMUM_FRACTION_OF_NATURAL_FLOW = 0.5


@app.function
def provincial_net_inputs(alberta_net_input):
    """Net precipitation P_net for each province, keeping the 2:1:1 split."""
    downstream_net_input = alberta_net_input * DOWNSTREAM_INPUT_RATIO
    return {
        "Alberta": alberta_net_input,
        "Saskatchewan": downstream_net_input,
        "Manitoba": downstream_net_input,
    }


@app.function
def step_reach(initial_storage, net_input, inflow_from_upstream, requested_withdrawal,
               storage_constant_k=STORAGE_CONSTANT_K):
    """One annual water balance for a single reach (Stadnyk 2025, Eq. 1):

        S_end = S_start + P_net + Q_in - A - Q_out

    Withdrawal A is taken first and cannot exceed the water on hand.
    Outflow is then 1/k of what remains, so a withdrawal upstream reduces
    the flow passed downstream in the same year.
    """
    water_available = initial_storage + net_input + inflow_from_upstream
    actual_withdrawal = min(max(requested_withdrawal, 0.0), water_available)
    water_after_withdrawal = water_available - actual_withdrawal
    outflow = water_after_withdrawal / storage_constant_k
    end_storage = water_after_withdrawal - outflow
    return {
        "initial_storage": initial_storage,
        "net_input": net_input,
        "inflow_from_upstream": inflow_from_upstream,
        "water_available": water_available,
        "withdrawal": actual_withdrawal,
        "outflow": outflow,
        "end_storage": end_storage,
    }


@app.function
def maa_withdrawal_limit(water_available):
    """Largest withdrawal that still meets the MAA (option b).

    Natural outflow (no withdrawal) is water_available / k. The MAA requires
    actual outflow >= 0.5 x natural outflow, i.e.
        (water_available - A) / k >= 0.5 x water_available / k
    which gives  A <= 0.5 x water_available.
    """
    return (1.0 - MAA_MINIMUM_FRACTION_OF_NATURAL_FLOW) * water_available


@app.function
def simulate_basin(alberta_net_input, alberta_requested_withdrawal, maa_enabled):
    """Run one year through Alberta -> Saskatchewan -> Manitoba.

    Only Alberta withdraws water, so any change downstream is caused by
    Alberta's withdrawal or by the net input setting.
    """
    net_inputs = provincial_net_inputs(alberta_net_input)
    requested_withdrawals = {"Alberta": alberta_requested_withdrawal,
                             "Saskatchewan": 0.0, "Manitoba": 0.0}
    results = {}
    inflow_from_upstream = 0.0
    alberta_maa_limit = None
    for province in PROVINCES:
        requested = requested_withdrawals[province]
        if maa_enabled:
            water_available = (INITIAL_STORAGE[province] + net_inputs[province]
                               + inflow_from_upstream)
            limit = maa_withdrawal_limit(water_available)
            if province == "Alberta":
                alberta_maa_limit = limit
            requested = min(requested, limit)
        reach = step_reach(INITIAL_STORAGE[province], net_inputs[province],
                           inflow_from_upstream, requested)
        results[province] = reach
        inflow_from_upstream = reach["outflow"]
    return {
        "reaches": results,
        "alberta_requested_withdrawal": alberta_requested_withdrawal,
        "alberta_permitted_withdrawal": results["Alberta"]["withdrawal"],
        "alberta_maa_limit": alberta_maa_limit,
    }


@app.cell
def _():
    mo.md(r"""
    # Prairie River Basin Simulator

    A one-year water balance for three provinces in series on the
    Saskatchewan–Nelson River system, simplified from the River Basin Game
    (Hoekstra 2012; Stadnyk 2025). Alberta is upstream, so whatever Alberta
    withdraws is water Saskatchewan and Manitoba never receive.

    **Try it:** raise Alberta's withdrawal and watch the downstream provinces.
    Then lower the net input to simulate a drought year, and turn on the
    Master Agreement on Apportionment.
    """)
    return


@app.cell
def _():
    net_input_slider = mo.ui.slider(
        start=0, stop=80, step=1, value=40, show_value=True, full_width=True,
        label="Alberta net input (Saskatchewan and Manitoba each get half)",
    )
    withdrawal_slider = mo.ui.slider(
        start=0, stop=120, step=1, value=0, show_value=True, full_width=True,
        label="Alberta withdrawal requested",
    )
    maa_switch = mo.ui.switch(label="Master Agreement on Apportionment (MAA)")
    mo.vstack([net_input_slider, withdrawal_slider, maa_switch], gap=1.25)
    return maa_switch, net_input_slider, withdrawal_slider


@app.cell
def _(maa_switch, net_input_slider, withdrawal_slider):
    scenario = simulate_basin(net_input_slider.value, withdrawal_slider.value,
                              maa_switch.value)
    natural = simulate_basin(net_input_slider.value, 0.0, False)
    return natural, scenario


@app.cell
def _(maa_switch, scenario):
    _requested = scenario["alberta_requested_withdrawal"]
    _permitted = scenario["alberta_permitted_withdrawal"]
    _available = scenario["reaches"]["Alberta"]["water_available"]
    if maa_switch.value and _permitted < _requested:
        _note = mo.callout(mo.md(
            f"**MAA in effect.** Alberta requested **{_requested:.0f}** units but may "
            f"withdraw only **{_permitted:.0f}** (half of the {_available:.0f} units "
            f"on hand), so at least half the natural flow crosses into Saskatchewan."
        ), kind="warn")
    elif _permitted < _requested:
        _note = mo.callout(mo.md(
            f"Alberta requested **{_requested:.0f}** units but only "
            f"**{_available:.0f}** were on hand, so Alberta takes everything available."
        ), kind="danger")
    elif maa_switch.value:
        _note = mo.callout(mo.md(
            f"**MAA in effect.** Alberta's withdrawal of {_permitted:.0f} is within its "
            f"limit of {scenario['alberta_maa_limit']:.0f} units."
        ), kind="info")
    else:
        _note = mo.callout(mo.md(
            f"No apportionment agreement: Alberta withdraws the **{_permitted:.0f}** "
            f"units it asked for."
        ), kind="neutral")
    _note
    return


@app.cell
def _(natural, scenario):
    def _stat(province):
        reach = scenario["reaches"][province]
        natural_reach = natural["reaches"][province]
        received = reach["inflow_from_upstream"]
        natural_received = natural_reach["inflow_from_upstream"]
        percent = 100 * received / natural_received if natural_received else 0
        storage_change = reach["end_storage"] - reach["initial_storage"]
        return mo.stat(
            value=f"{reach['end_storage']:.0f}",
            label=f"{province}: water remaining",
            caption=(f"Received {received:.0f} of {natural_received:.0f} units "
                     f"from upstream ({percent:.0f}% of natural); "
                     f"storage change {storage_change:+.0f}"),
            direction="decrease" if storage_change < -0.5 else None,
            bordered=True,
        )

    mo.hstack([_stat("Saskatchewan"), _stat("Manitoba")], widths="equal", gap=1)
    return


@app.cell
def _(maa_switch, natural, scenario):
    _labels = ["Alberta → Sask.", "Sask. → Manitoba", "Manitoba → Hudson Bay"]
    _natural_flows = [natural["reaches"][p]["outflow"] for p in PROVINCES]
    _scenario_flows = [scenario["reaches"][p]["outflow"] for p in PROVINCES]

    _fig, _ax = plt.subplots(figsize=(7.5, 3.6))
    _x = range(len(_labels))
    _width = 0.38
    _ax.bar([i - _width / 2 for i in _x], _natural_flows, _width,
            label="Natural (no withdrawal)", color="#9db8d3")
    _ax.bar([i + _width / 2 for i in _x], _scenario_flows, _width,
            label="This scenario", color="#1f5f8b")
    if maa_switch.value:
        for i, natural_flow in enumerate(_natural_flows[:2]):
            _ax.hlines(MAA_MINIMUM_FRACTION_OF_NATURAL_FLOW * natural_flow,
                       i - 0.45, i + 0.45, colors="#c0392b", linestyles="--",
                       label="MAA minimum (50% of natural)" if i == 0 else None)
    _ax.set_xticks(list(_x))
    _ax.set_xticklabels(_labels)
    _ax.set_ylabel("Flow (water units / year)")
    _ax.set_title("Water passed across each border")
    _ax.spines[["top", "right"]].set_visible(False)
    _ax.legend(frameon=False, fontsize=9)
    _fig.tight_layout()
    _fig
    return


@app.cell
def _(scenario):
    _rows = []
    for _province in PROVINCES:
        _r = scenario["reaches"][_province]
        _rows.append(
            f"| {_province} | {_r['initial_storage']:.1f} | {_r['net_input']:.1f} | "
            f"{_r['inflow_from_upstream']:.1f} | {_r['withdrawal']:.1f} | "
            f"{_r['outflow']:.1f} | {_r['end_storage']:.1f} |"
        )
    mo.accordion({"Full water balance (S_end = S_start + P_net + Q_in − A − Q_out)": mo.md(
        "| Province | S_start | P_net | Q_in | A | Q_out | S_end |\n"
        "|---|---:|---:|---:|---:|---:|---:|\n" + "\n".join(_rows)
        + f"\n\nQ_out = (S_start + P_net + Q_in − A) / k, with k = {STORAGE_CONSTANT_K}."
    )})
    return


if __name__ == "__main__":
    app.run()
