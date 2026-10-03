"""Unit tests for EBU R128 loudnorm filter construction."""

from clipforge.render.loudnorm import build_loudnorm_af


def test_build_loudnorm_fallback():
    af = build_loudnorm_af(None, target_i=-14.0, target_tp=-1.5)
    assert af == "loudnorm=I=-14.0:TP=-1.5:LRA=11.0"


def test_build_loudnorm_two_pass():
    measured = {
        "input_i": "-22.5",
        "input_tp": "-1.2",
        "input_lra": "9.4",
        "input_thresh": "-32.1",
        "target_offset": "+0.5",
    }
    af = build_loudnorm_af(measured, target_i=-14.0, target_tp=-1.5)
    assert "measured_I=-22.5" in af
    assert "measured_TP=-1.2" in af
    assert "measured_LRA=9.4" in af
    assert "measured_thresh=-32.1" in af
    assert "offset=+0.5" in af
    assert "linear=true" in af
