from __future__ import annotations

import logging

from WA.utils import progress as progress_module


def test_log_progress_iterable_fallback(monkeypatch, caplog) -> None:
    monkeypatch.setattr(progress_module, "_tqdm_enabled", lambda: False)

    with caplog.at_level(logging.INFO, logger="WA.progress"):
        items = list(
            progress_module.tqdm(
                ["a", "b", "c"],
                desc="GWD30 2013 TIFF",
                unit="tile",
                mininterval=0.0,
            )
        )

    assert items == ["a", "b", "c"]
    assert any("GWD30 2013 TIFF" in message for message in caplog.messages)
    assert any("3/3 tile" in message for message in caplog.messages)


def test_log_progress_manual_update_fallback(monkeypatch, caplog) -> None:
    monkeypatch.setattr(progress_module, "_tqdm_enabled", lambda: False)

    with caplog.at_level(logging.INFO, logger="WA.progress"):
        progress = progress_module.tqdm(
            total=4,
            desc="GWD30 parallel",
            unit="tile",
            mininterval=0.0,
        )
        progress.set_postfix_str("47RQS_wetland_2013.tif")
        progress.update(2)
        progress.update(2)
        progress.close()

    assert any("47RQS_wetland_2013.tif" in message for message in caplog.messages)
    assert any("4/4 tile" in message for message in caplog.messages)
