from __future__ import annotations

from WA.test_selection import categories_for_paths, category_keys_for_path, infer_related_tests


def test_infer_related_tests_for_phase4_paths() -> None:
    inferred = infer_related_tests(["src/WA/comparison/phase4_regional.py"])

    assert "tests/test_comparison/test_phase4_regional.py" in inferred
    assert "tests/test_comparison/test_trends.py" in inferred
    assert "tests/test_visualization/test_phase4.py" in inferred
    assert "tests/test_standardize.py" not in inferred


def test_infer_related_tests_keeps_direct_test_path() -> None:
    inferred = infer_related_tests(
        [
            "tests/test_comparison/test_phase4_regional.py",
            "src/WA/comparison/phase4_regional.py",
        ]
    )

    assert inferred[0] == "tests/test_comparison/test_phase4_regional.py"
    assert inferred.count("tests/test_comparison/test_phase4_regional.py") == 1


def test_categories_for_paths_include_standardization_and_loaders() -> None:
    categories = categories_for_paths(
        [
            "src/WA/standardize.py",
            "src/WA/loaders/gwd30.py",
        ]
    )
    keys = [category.key for category in categories]

    assert "standardization_and_gwd30_io" in keys
    assert "loaders" in keys


def test_infer_related_tests_for_scaleout_readiness_paths() -> None:
    inferred = infer_related_tests(["src/WA/comparison/scaleout_readiness.py"])

    assert "tests/test_comparison/test_scaleout_readiness.py" in inferred
    assert "tests/test_comparison/test_hotspot_ledger.py" in inferred
    assert "tests/test_visualization/test_phase4.py" in inferred


def test_category_keys_for_path_matches_phase3_7_script() -> None:
    keys = category_keys_for_path("scripts/plot_phase3_7_hotspot_panels.py")

    assert keys == ["phase3_7"]
