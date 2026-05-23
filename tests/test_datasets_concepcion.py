"""Tests for the Concepción 2010 fragility dataset (grupo F)."""
from __future__ import annotations

import numpy as np
import pytest

from bridgejm.datasets import (
    BridgePier,
    CONCEPCION_2010_PIERS,
    fragility_curve,
    pier_by_name,
)
from bridgejm.fragility import FragilityCurve


def test_dataset_has_five_piers():
    assert len(CONCEPCION_2010_PIERS) == 5
    for p in CONCEPCION_2010_PIERS:
        assert isinstance(p, BridgePier)
        assert p.M_u_kNm > p.M_y_kNm > 0
        assert 0.01 < p.theta_u_rad < 0.10
        assert p.observed_ds in {"slight", "moderate", "extensive", "complete"}


def test_pier_by_name_lookup():
    p = pier_by_name("BioBio_P3")
    assert p is not None
    assert p.bridge.startswith("Puente B")
    assert pier_by_name("__missing__") is None


def test_fragility_curve_is_lognormal_with_correct_shape():
    fc = fragility_curve("moderate")
    assert isinstance(fc, FragilityCurve)
    # Probability at median should be 0.5 by construction
    p_at_median = fc.probability(fc.median)
    assert float(p_at_median) == pytest.approx(0.5, abs=1e-6)


def test_fragility_monotonic_in_im():
    fc = fragility_curve("extensive")
    ims = np.linspace(0.05, 1.5, 30)
    probs = np.asarray([float(fc.probability(im)) for im in ims])
    diffs = np.diff(probs)
    assert np.all(diffs >= -1e-12), "fragility must be non-decreasing in IM"


def test_fragility_ordering_across_damage_states():
    # At a fixed IM, P(slight) >= P(moderate) >= P(extensive) >= P(complete)
    im = 0.40
    ps = [float(fragility_curve(ds).probability(im))
          for ds in ("slight", "moderate", "extensive", "complete")]
    assert ps[0] >= ps[1] >= ps[2] >= ps[3]


def test_fragility_invalid_damage_state_raises():
    with pytest.raises(ValueError):
        fragility_curve("destroyed")  # type: ignore[arg-type]
