from __future__ import annotations

from WA.utils.mgrs_tiling import GWD30TilingSystem


def test_point_to_tile_matches_reference_cases() -> None:
    tiling = GWD30TilingSystem()

    assert tiling.point_to_tile(0.0, 3.0) == "31NEA"
    assert tiling.point_to_tile(45.0, 7.0) == "32TLQ"
    assert tiling.point_to_tile(-10.0, -60.0) == "21LSJ"
    assert tiling.point_to_tile(-4.5, -60.5) == "20MQA"
    assert tiling.point_to_tile(23.4, 113.2) == "49QGF"


def test_tile_to_extent_matches_reference_case() -> None:
    tiling = GWD30TilingSystem()

    assert tiling.tile_to_extent("31NEA") == (
        2.999865198786888,
        -0.00013570970543935252,
        3.9869779189416295,
        0.993381386003582,
    )


def test_bbox_to_tiles_matches_reference_case() -> None:
    tiling = GWD30TilingSystem()

    assert tiling.bbox_to_tiles(-5.0, -61.0, -4.0, -60.0) == [
        "20MQA",
        "20MQV",
        "20MRA",
        "20MRV",
        "21MSQ",
        "21MSR",
    ]


def test_bbox_to_tiles_keeps_eastward_overlap_tiles() -> None:
    tiling = GWD30TilingSystem()

    assert tiling.bbox_to_tiles(0.499, 3.949, 0.501, 3.951) == [
        "31NEA",
        "31NFA",
    ]
