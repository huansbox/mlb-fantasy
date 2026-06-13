"""Unit tests for issue 047 / #326 — swap_batter."""

from swap_batter import format_swap_line, should_emit_swap, swap_vector_batter


def test_should_emit_only_4star_plus():
    assert should_emit_swap(5) and should_emit_swap(4)
    assert not should_emit_swap(3)
    assert not should_emit_swap(None)


def test_swap_vector_counting_and_ratio():
    cand = {"HR": 1.4, "R": 4.2, "OPS": 0.860}
    inc = {"HR": 1.0, "R": 5.0, "OPS": 0.849}
    vec = swap_vector_batter(cand, 28, inc, 25)
    assert vec["HR"] == 0.4
    assert vec["R"] == -0.8
    assert vec["OPS"] == 0.011    # ratio diff, 3dp
    assert vec["PA"] == 3.0


def test_swap_vector_missing_category_treated_zero():
    vec = swap_vector_batter({"HR": 1.0}, 20, {}, 18)
    assert vec["HR"] == 1.0 and vec["PA"] == 2.0


def test_pederson_retro_replay_pa_and_avg_negative():
    # add Pederson (strong-side, low PA, lower AVG) ⇄ drop Arraez (everyday,
    # high PA, high AVG). The swap must surface the volume + AVG loss.
    arraez = {"R": 4.5, "HR": 0.3, "AVG": 0.330, "OPS": 0.780}
    pederson = {"R": 3.0, "HR": 1.2, "AVG": 0.240, "OPS": 0.820}
    vec = swap_vector_batter(pederson, cand_pa=17, inc_cats=arraez, inc_pa=24)
    assert vec["PA"] == -7.0      # the −28%-PA blind spot, now explicit
    assert vec["AVG"] < 0          # Arraez's AVG edge lost
    assert vec["HR"] > 0           # Pederson's power gained (the trade-off)


def test_format_swap_line_order_and_signs():
    vec = {"BB": 2.1, "HR": 0.4, "R": -0.8, "AVG": -0.006, "OPS": 0.011, "PA": -7}
    line = format_swap_line("Arraez", "Pederson", vec)
    assert line.startswith("swap Arraez→Pederson/week: ")
    assert "PA -7" in line and "HR +0.4" in line and "AVG -0.006" in line
    # PA appears last in the fixed order
    assert line.rindex("PA") > line.rindex("OPS")


def test_format_swap_line_includes_extra_category():
    line = format_swap_line("X", "Y", {"HR": 1.0, "SVH": 0.5})
    assert "HR +1" in line and "SVH +0.5" in line
