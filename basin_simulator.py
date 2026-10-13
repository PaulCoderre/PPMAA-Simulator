import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium", app_title="Prairie River Basin Simulator")

with app.setup:
    import marimo as mo
    import matplotlib.pyplot as plt

    # Three provinces in series, upstream to downstream
    # (Saskatchewan–Nelson River basin; Stadnyk 2025, Fig. 1).
    PROVINCES = ("Alberta", "Saskatchewan", "Manitoba")

    # Saskatchewan and Manitoba each generate half of what Alberta generates,
    # following the 2:1:1 split of Stadnyk (2025) Table 1 (P_net = 40 / 20 / 20).
    DOWNSTREAM_GENERATION_RATIO = 0.5

    # Master Agreement on Apportionment (PPWB 1969): at least 50% of the
    # natural flow must cross each provincial border.
    MAA_MINIMUM_FRACTION_OF_NATURAL_FLOW = 0.5


@app.function
def water_generated_by_province(alberta_water_generated):
    """Water generated within each province in one year, keeping the 2:1:1 split."""
    downstream_water_generated = alberta_water_generated * DOWNSTREAM_GENERATION_RATIO
    return {
        "Alberta": alberta_water_generated,
        "Saskatchewan": downstream_water_generated,
        "Manitoba": downstream_water_generated,
    }


@app.function
def flow_through_reach(inflow_from_upstream, water_generated, requested_withdrawal):
    """One-year flow-through balance for a province (no storage):

        Q_out = Q_in + G - A

    The withdrawal A cannot exceed the water available (Q_in + G).
    """
    water_available = inflow_from_upstream + water_generated
    actual_withdrawal = min(max(requested_withdrawal, 0.0), water_available)
    return {
        "inflow_from_upstream": inflow_from_upstream,
        "water_generated": water_generated,
        "water_available": water_available,
        "withdrawal": actual_withdrawal,
        "outflow": water_available - actual_withdrawal,
    }


@app.function
def maa_withdrawal_limit(water_available, natural_outflow):
    """Largest withdrawal that still passes 50% of the natural flow downstream.

    The MAA requires  Q_out >= 0.5 x natural Q_out, and Q_out = available - A, so
        A <= available - 0.5 x natural Q_out   (never below zero).

    For Alberta, natural Q_out is the water generated in Alberta.
    For Saskatchewan, natural Q_out is Alberta's natural flow plus the water
    generated in Saskatchewan, so any extra Alberta use reduces Saskatchewan's room.
    """
    return max(0.0, water_available - MAA_MINIMUM_FRACTION_OF_NATURAL_FLOW * natural_outflow)


@app.function
def simulate_basin(alberta_water_generated, alberta_withdrawal_percent,
                   saskatchewan_withdrawal_percent, maa_enabled):
    """Run one year through Alberta -> Saskatchewan -> Manitoba.

    Withdrawals are given as percentages:
      - Alberta: % of the water generated in Alberta
      - Saskatchewan: % of the water available in Saskatchewan (inflow + generated)
    Manitoba does not withdraw.
    """
    water_generated = water_generated_by_province(alberta_water_generated)
    results = {}
    requested_withdrawals = {}
    maa_limits = {}

    inflow_from_upstream = 0.0
    natural_outflow = 0.0  # flow that would leave the province with no withdrawals
    for province in PROVINCES:
        water_available = inflow_from_upstream + water_generated[province]
        natural_outflow += water_generated[province]

        if province == "Alberta":
            requested = alberta_withdrawal_percent / 100 * water_generated[province]
        elif province == "Saskatchewan":
            requested = saskatchewan_withdrawal_percent / 100 * water_available
        else:
            requested = 0.0
        requested_withdrawals[province] = requested

        permitted = requested
        if maa_enabled and province != "Manitoba":
            maa_limits[province] = maa_withdrawal_limit(water_available, natural_outflow)
            permitted = min(requested, maa_limits[province])

        reach = flow_through_reach(inflow_from_upstream, water_generated[province], permitted)
        reach["natural_outflow"] = natural_outflow
        results[province] = reach
        inflow_from_upstream = reach["outflow"]

    return {"reaches": results, "requested_withdrawals": requested_withdrawals,
            "maa_limits": maa_limits}


@app.cell
def _():
    mo.md(r"""
    # Prairie River Basin Simulator

    A one-year water balance for three provinces in series on the
    Saskatchewan–Nelson River system, simplified from the River Basin Game
    (Hoekstra 2012; Stadnyk 2025). Each province passes on whatever it receives
    plus what it generates, minus what it withdraws. Alberta is upstream, so
    every unit Alberta takes is a unit Saskatchewan and Manitoba never see.

    **Try it:** set Alberta's withdrawal to 100% and see what crosses the border.
    Then lower the water generated to simulate a drought year, and turn on the
    Master Agreement on Apportionment.
    """)
    return


@app.cell
def _():
    water_generated_slider = mo.ui.slider(
        start=0, stop=80, step=1, value=40, show_value=True, full_width=True,
        label="Water generated in Alberta (Saskatchewan and Manitoba each generate half)",
    )
    alberta_withdrawal_slider = mo.ui.slider(
        start=0, stop=100, step=1, value=0, show_value=True, full_width=True,
        label="Alberta withdrawal (% of water generated in Alberta)",
    )
    saskatchewan_withdrawal_slider = mo.ui.slider(
        start=0, stop=100, step=1, value=0, show_value=True, full_width=True,
        label="Saskatchewan withdrawal (% of water available in Saskatchewan)",
    )
    maa_switch = mo.ui.switch(label="Master Agreement on Apportionment (MAA)")
    mo.vstack([water_generated_slider, alberta_withdrawal_slider,
               saskatchewan_withdrawal_slider, maa_switch], gap=1.25)
    return (alberta_withdrawal_slider, maa_switch, saskatchewan_withdrawal_slider,
            water_generated_slider)


@app.cell
def _(alberta_withdrawal_slider, maa_switch, saskatchewan_withdrawal_slider,
      water_generated_slider):
    scenario = simulate_basin(water_generated_slider.value,
                              alberta_withdrawal_slider.value,
                              saskatchewan_withdrawal_slider.value,
                              maa_switch.value)
    return (scenario,)


@app.cell
def _(maa_switch, scenario):
    def _withdrawal_note(province):
        requested = scenario["requested_withdrawals"][province]
        permitted = scenario["reaches"][province]["withdrawal"]
        if maa_switch.value and permitted < requested - 1e-9:
            return mo.callout(mo.md(
                f"**{province}: MAA in effect.** Requested **{requested:.1f}** units, "
                f"permitted **{permitted:.1f}** so that half the natural flow "
                f"({scenario['reaches'][province]['natural_outflow']:.1f}) crosses the border."
            ), kind="warn")
        if maa_switch.value:
            return mo.callout(mo.md(
                f"**{province}** withdraws {permitted:.1f} units, within its MAA limit "
                f"of {scenario['maa_limits'][province]:.1f}."
            ), kind="info")
        return mo.callout(mo.md(
            f"**{province}** withdraws **{permitted:.1f}** units. No apportionment agreement."
        ), kind="neutral")

    mo.vstack([_withdrawal_note("Alberta"), _withdrawal_note("Saskatchewan")], gap=0.5)
    return


@app.cell
def _(scenario):
    def _stat(province):
        reach = scenario["reaches"][province]
        natural_inflow = reach["natural_outflow"] - reach["water_generated"]
        received = reach["inflow_from_upstream"]
        percent = 100 * received / natural_inflow if natural_inflow else 0
        return mo.stat(
            value=f"{received:.1f}",
            label=f"{province}: water received from upstream",
            caption=(f"{percent:.0f}% of the natural {natural_inflow:.1f} units; "
                     f"plus {reach['water_generated']:.1f} generated locally"),
            direction="decrease" if percent < 99.5 else None,
            bordered=True,
        )

    mo.hstack([_stat("Saskatchewan"), _stat("Manitoba")], widths="equal", gap=1)
    return


@app.cell
def _(maa_switch, scenario):
    _labels = ["Alberta → Sask.", "Sask. → Manitoba", "Manitoba → Hudson Bay"]
    _natural_flows = [scenario["reaches"][p]["natural_outflow"] for p in PROVINCES]
    _scenario_flows = [scenario["reaches"][p]["outflow"] for p in PROVINCES]

    _fig, _ax = plt.subplots(figsize=(7.5, 3.6))
    _x = range(len(_labels))
    _width = 0.38
    _ax.bar([i - _width / 2 for i in _x], _natural_flows, _width,
            label="Natural (no withdrawals)", color="#9db8d3")
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
            f"| {_province} | {_r['inflow_from_upstream']:.1f} | {_r['water_generated']:.1f} | "
            f"{_r['withdrawal']:.1f} | {_r['outflow']:.1f} | {_r['natural_outflow']:.1f} |"
        )
    mo.accordion({"Full water balance (Q_out = Q_in + G − A)": mo.md(
        "| Province | Q_in | G (generated) | A (withdrawn) | Q_out | Natural Q_out |\n"
        "|---|---:|---:|---:|---:|---:|\n" + "\n".join(_rows)
    )})
    return


if __name__ == "__main__":
    app.run()