from __future__ import annotations

from WA.utils import progress


def test_noop_tqdm_supports_iteration_and_progress_methods(monkeypatch) -> None:
    monkeypatch.setattr(progress, "_real_tqdm", None)

    bar = progress.tqdm([1, 2, 3], desc="demo")

    assert list(bar) == [1, 2, 3]
    bar.set_postfix_str("ok", refresh=False)
    bar.update()
    bar.close()
