"""Regression tests for the user's literal, fail-closed registry stop thresholds."""

from scripts.check_registry import stop_reasons


def test_directed_proximity_stops_even_when_dense_and_reciprocal_is_low():
    prior = {
        "kind": "dense",
        "spearman_dots": 0.01,
        "spearman_surface": 0.02,
        "containment": 0.71,
        "rev_containment": 0.16,
        "jaccard_3px": 0.03,
    }
    assert stop_reasons(prior) == ["directed_near3px>0.70"]


def test_directed_proximity_threshold_is_strictly_greater_than_point_seven():
    prior = {
        "kind": "dense",
        "spearman_dots": 0.0,
        "spearman_surface": 0.0,
        "containment": 0.70,
        "rev_containment": 0.0,
        "jaccard_3px": 0.0,
    }
    assert stop_reasons(prior) == []


def test_unrounded_directed_proximity_crossing_stops_even_if_display_rounds_to_point_seven():
    prior = {
        "spearman_dots": 0.0,
        "spearman_surface": 0.0,
        "containment": 0.70,
        "_containment_raw": 0.70001,
    }
    assert stop_reasons(prior) == ["directed_near3px>0.70"]


def test_surface_correlation_stops_before_emission_even_if_display_rounds_to_point_nine():
    prior = {
        "spearman_dots": 0.01,
        "spearman_surface": 0.9000,
        "_spearman_surface_raw": 0.90001,
        "containment": 0.0,
    }
    assert stop_reasons(prior) == ["spearman_surface>0.90"]


def test_correlation_equal_to_point_nine_does_not_trigger():
    prior = {
        "spearman_dots": 0.90,
        "_spearman_dots_raw": 0.90,
        "spearman_surface": 0.0,
        "containment": 0.0,
    }
    assert stop_reasons(prior) == []


def test_final_dot_correlation_stops():
    prior = {
        "spearman_dots": 0.91,
        "spearman_surface": 0.02,
        "containment": 0.0,
    }
    assert stop_reasons(prior) == ["spearman_dots>0.90"]
