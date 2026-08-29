from __future__ import annotations

from datetime import date
from unittest.mock import Mock, patch

from expense_report.fx import FxCache, FxError, get_rates


def _mock_response(rates: dict) -> Mock:
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.json.return_value = {"rates": rates}
    return resp


def test_get_rates_happy_path(tmp_path):
    cache = FxCache(tmp_path / "cache.json")
    with patch("expense_report.fx.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"CHF": 0.95, "USD": 1.08})
        rates, used_date = get_rates(date(2026, 5, 20), "EUR", ["CHF", "USD"], cache)

    assert rates == {"CHF": 0.95, "USD": 1.08, "EUR": 1.0}
    assert used_date == date(2026, 5, 20)
    mock_get.assert_called_once()


def test_get_rates_supports_arbitrary_target_currencies(tmp_path):
    cache = FxCache(tmp_path / "cache.json")
    with patch("expense_report.fx.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"KRW": 1450.0, "CHF": 0.95, "USD": 1.08})
        rates, used_date = get_rates(date(2026, 5, 20), "EUR", ["KRW", "CHF", "USD"], cache)

    assert rates == {"KRW": 1450.0, "CHF": 0.95, "USD": 1.08, "EUR": 1.0}
    assert used_date == date(2026, 5, 20)


def test_get_rates_uses_cache_on_second_call(tmp_path):
    cache = FxCache(tmp_path / "cache.json")
    with patch("expense_report.fx.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"CHF": 0.95, "USD": 1.08})
        get_rates(date(2026, 5, 20), "EUR", ["CHF", "USD"], cache)
        get_rates(date(2026, 5, 20), "EUR", ["CHF", "USD"], cache)

    assert mock_get.call_count == 1


def test_different_target_sets_do_not_share_a_cache_entry(tmp_path):
    cache = FxCache(tmp_path / "cache.json")
    with patch("expense_report.fx.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"USD": 1.08})
        get_rates(date(2026, 5, 20), "EUR", ["USD"], cache)

    with patch("expense_report.fx.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"JPY": 165.0, "USD": 1.08})
        rates, _ = get_rates(date(2026, 5, 20), "EUR", ["JPY", "USD"], cache)

    mock_get.assert_called_once()
    assert rates["JPY"] == 165.0


def test_cache_persists_across_instances(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache1 = FxCache(cache_path)
    with patch("expense_report.fx.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"CHF": 0.95, "USD": 1.08})
        get_rates(date(2026, 5, 20), "EUR", ["CHF", "USD"], cache1)

    cache2 = FxCache(cache_path)
    with patch("expense_report.fx.requests.get") as mock_get:
        rates, used_date = get_rates(date(2026, 5, 20), "EUR", ["CHF", "USD"], cache2)

    mock_get.assert_not_called()
    assert rates == {"CHF": 0.95, "USD": 1.08, "EUR": 1.0}


def test_get_rates_falls_back_over_weekend(tmp_path):
    cache = FxCache(tmp_path / "cache.json")
    responses = [
        _mock_response({}),  # Saturday: no ECB rate published
        _mock_response({"CHF": 0.95, "USD": 1.08}),  # Friday
    ]
    with patch("expense_report.fx.requests.get", side_effect=responses):
        rates, used_date = get_rates(date(2026, 5, 23), "EUR", ["CHF", "USD"], cache)  # a Saturday

    assert used_date == date(2026, 5, 22)
    assert rates["CHF"] == 0.95


def test_base_equal_to_one_target_currency_only_fetches_the_other(tmp_path):
    cache = FxCache(tmp_path / "cache.json")
    with patch("expense_report.fx.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"USD": 1.08})
        rates, used_date = get_rates(date(2026, 5, 20), "CHF", ["CHF", "USD"], cache)

    mock_get.assert_called_once()
    assert rates == {"CHF": 1.0, "USD": 1.08}


def test_single_target_currency_equal_to_base_needs_no_request(tmp_path):
    cache = FxCache(tmp_path / "cache.json")
    with patch("expense_report.fx.requests.get") as mock_get:
        rates, used_date = get_rates(date(2026, 5, 20), "USD", ["USD"], cache)

    mock_get.assert_not_called()
    assert rates == {"USD": 1.0}
    assert used_date == date(2026, 5, 20)


def test_raises_after_exhausting_fallback_window(tmp_path):
    cache = FxCache(tmp_path / "cache.json")
    with patch("expense_report.fx.requests.get") as mock_get:
        mock_get.return_value = _mock_response({})
        try:
            get_rates(date(2026, 5, 20), "EUR", ["CHF", "USD"], cache)
        except FxError:
            pass
        else:
            raise AssertionError("expected FxError")
