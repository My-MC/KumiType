from concurrent.futures import Future

import pytest

from kumitype.builder import build_all


class InlinePool:
    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def submit(self, function, *args):
        future = Future()
        try:
            future.set_result(function(*args))
        except Exception as exc:
            future.set_exception(exc)
        return future


def test_fail_fast_stops_scheduling_and_reports_unstarted(monkeypatch):
    import kumitype.builder as builder

    calls = []
    captured = {}
    def failing(config, target, *args):
        calls.append(target)
        raise ValueError('source missing')
    def capture(outputs, errors, **kwargs):
        captured.update(outputs=outputs, errors=errors)
    monkeypatch.setattr(builder, 'ProcessPoolExecutor', InlinePool)
    monkeypatch.setattr(builder, 'build_one', failing)
    monkeypatch.setattr(builder, 'write_build_report', capture)
    config = {'variants': ['mono'], 'japanese_fonts': ['biz'], 'weights': [200, 300, 400],
              'styles': ['normal'], 'build': {'fail_on_error': True}}
    with pytest.raises(ValueError, match='build errors.*source missing'):
        build_all(config, jobs=1)
    assert len(calls) == 1
    assert len(captured['errors']) == 3
    assert captured['outputs'] == []
