from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "plot_priority_regions_world.py"
    spec = importlib.util.spec_from_file_location("plot_priority_regions_world", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_priority_regions_sorts_by_priority() -> None:
    module = _load_script_module()

    regions = module.load_priority_regions(Path("config/priority_regions.yaml"))

    assert regions
    assert regions[0].priority == min(region.priority for region in regions)
    assert regions[-1].priority == max(region.priority for region in regions)
    assert [region.priority for region in regions] == sorted(region.priority for region in regions)


def test_callout_position_uses_bbox_top_right_corner() -> None:
    module = _load_script_module()
    region = module.PriorityRegion(
        region_id="amazon_basin",
        label="Amazon Basin",
        continent="South America",
        priority=1,
        bbox=(-79.5, -19.5, -44.0, 6.5),
    )

    position = module.callout_position(region)

    assert position == (-44.0, 6.5)


def test_callout_offset_points_stacks_nearby_labels_upward() -> None:
    module = _load_script_module()
    region = module.PriorityRegion(
        region_id="demo_region",
        label="Demo Region",
        continent="Demo Continent",
        priority=99,
        bbox=(10.0, -4.0, 14.0, 2.0),
    )

    offset = module.callout_offset_points(
        region,
        occupied_anchors=[(13.0, 1.5, 0), (12.5, 1.0, 1)],
    )

    assert offset == (
        module.CALLOUT_DX_POINTS,
        module.CALLOUT_DY_POINTS + 2 * module.CALLOUT_STACK_DY_POINTS,
    )


def test_format_callout_text_includes_priority_label_and_continent() -> None:
    module = _load_script_module()
    region = module.PriorityRegion(
        region_id="sudd",
        label="Sudd Wetland",
        continent="Africa",
        priority=5,
        bbox=(28.5, 5.5, 33.5, 10.5),
    )

    text = module.format_callout_text(region)

    assert text == "5. Sudd Wetland\nAfrica"
