"""Market-data adapters for the portfolio monitor.

All internal portfolio values are expressed in Iranian rials (IRR).
TSETMC fund prices are already in rials. NerkhAra's USD rate is in toman
(IRT), so it is multiplied by 10 before it is used. CoinPaprika quotes
crypto in USD and those prices are converted with the free-market USD rate.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests

TIMEOUT = 12
USER_AGENT = "Mozilla/5.0 (compatible; PortfolioMonitor/1.0; +local-dashboard)"


class MarketDataError(RuntimeError):
    pass


def _get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    try:
        response = requests.get(
            url,
            params=params,
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        response.raise_for_status()
        return response.json()
    except requests.Timeout as exc:
        raise MarketDataError("پاسخ منبع قیمت در زمان مقرر دریافت نشد.") from exc
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        raise MarketDataError(f"خطای HTTP از منبع قیمت: {status}") from exc
    except requests.RequestException as exc:
        raise MarketDataError(f"خطای ارتباط با منبع قیمت: {exc}") from exc
    except ValueError as exc:
        raise MarketDataError("پاسخ منبع قیمت JSON معتبر نیست.") from exc


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_tsetmc_event_time(payload: dict[str, Any]) -> str | None:
    """Best-effort parse of TSETMC date/time fields; do not invent a timestamp."""
    date_value = payload.get("dEven") or payload.get("dEvenLast") or payload.get("date")
    time_value = payload.get("hEven") or payload.get("hEvenLast") or payload.get("time")
    if date_value is None:
        return None
    date_text = str(date_value).strip()
    if len(date_text) != 8 or not date_text.isdigit():
        return None
    try:
        day = datetime.strptime(date_text, "%Y%m%d").date()
        time_text = str(time_value or "000000").zfill(6)
        if len(time_text) == 6 and time_text.isdigit():
            return datetime.strptime(f"{day.isoformat()} {time_text}", "%Y-%m-%d %H%M%S").replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
        return datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc).isoformat(timespec="seconds")
    except ValueError:
        return None


def search_tsetmc_instruments(query: str) -> list[dict[str, str]]:
    """Search TSETMC by Persian or Latin ticker/name."""
    if not query.strip():
        return []
    url = f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch/{quote(query.strip(), safe='')}"
    data = _get_json(url)
    rows = data.get("instrumentSearch", []) if isinstance(data, dict) else []
    results: list[dict[str, str]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        ins_code = str(row.get("insCode") or "").strip()
        symbol = str(row.get("lVal18AFC") or "").strip()
        name = str(row.get("lVal30") or "").strip()
        if ins_code and (symbol or name):
            results.append({
                "ins_code": ins_code,
                "symbol": symbol or query.strip(),
                "name": name or symbol or query.strip(),
                "market": str(row.get("flowTitle") or ""),
            })
    # Keep exact ticker matches first, then the rest.
    q = query.strip().casefold()
    results.sort(key=lambda item: (item["symbol"].casefold() != q, item["symbol"].casefold(), item["name"].casefold()))
    return results[:30]


def fetch_tsetmc_quote(ins_code: str) -> dict[str, Any]:
    """Return last traded / closing price in rials for one TSETMC instrument."""
    url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{quote(str(ins_code).strip(), safe='')}"
    data = _get_json(url)
    row: Any = data.get("closingPriceInfo", data) if isinstance(data, dict) else data
    if isinstance(row, list):
        row = row[0] if row else {}
    if not isinstance(row, dict):
        raise MarketDataError("ساختار پاسخ قیمت صندوق از TSETMC قابل تشخیص نیست.")

    # pDrCotVal is the last traded price; pClosing is the official closing price.
    raw_price = row.get("pDrCotVal")
    price_type = "آخرین معامله"
    if raw_price in (None, "", 0, "0"):
        raw_price = row.get("pClosing")
        price_type = "قیمت پایانی (جایگزین آخرین معامله)"
    if raw_price in (None, ""):
        raw_price = row.get("pl") or row.get("pc")
    try:
        price = float(raw_price)
    except (TypeError, ValueError) as exc:
        raise MarketDataError("قیمت صندوق در پاسخ TSETMC وجود ندارد یا معتبر نیست.") from exc
    if price <= 0:
        raise MarketDataError("قیمت صندوق صفر یا منفی گزارش شده است.")

    return {
        "price": price,
        "currency": "IRR",
        "source": "TSETMC",
        "source_updated_at": _parse_tsetmc_event_time(row),
        "fetched_at": utc_now_iso(),
        "price_type": price_type,
        "stale": False,
    }


def search_coinpaprika(query: str) -> list[dict[str, str]]:
    """Search CoinPaprika for coin IDs from a symbol or name."""
    if not query.strip():
        return []
    data = _get_json(
        "https://api.coinpaprika.com/v1/search/",
        params={"q": query.strip(), "c": "currencies", "limit": 20},
    )
    rows = data.get("currencies", []) if isinstance(data, dict) else []
    results: list[dict[str, str]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        if row.get("is_active") is False:
            continue
        results.append({
            "coin_id": str(row["id"]),
            "symbol": str(row.get("symbol") or ""),
            "name": str(row.get("name") or row["id"]),
            "rank": str(row.get("rank") or ""),
        })
    q = query.strip().casefold()
    results.sort(key=lambda item: (item["symbol"].casefold() != q, item["name"].casefold() != q, int(item["rank"]) if item["rank"].isdigit() else 999999))
    return results[:20]



def fetch_coinpaprika_ticker_map() -> dict[str, dict[str, Any]]:
    """Fetch the free top-2,000 ticker list once for an entire portfolio.

    This is more quota-efficient than requesting one coin endpoint per asset.
    Coins outside the free list can still be fetched individually as fallback.
    """
    data = _get_json("https://api.coinpaprika.com/v1/tickers", params={"quotes": "USD"})
    if not isinstance(data, list):
        raise MarketDataError("ساختار فهرست قیمت CoinPaprika قابل تشخیص نیست.")
    mapped: dict[str, dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        try:
            price = float(item["quotes"]["USD"]["price"])
        except (KeyError, TypeError, ValueError):
            continue
        if price <= 0:
            continue
        mapped[str(item["id"])] = {
            "price": price,
            "currency": "USD",
            "source": "CoinPaprika",
            "source_updated_at": item.get("last_updated"),
            "fetched_at": utc_now_iso(),
            "stale": False,
        }
    return mapped

def fetch_coinpaprika_quote(coin_id: str) -> dict[str, Any]:
    """Return a coin's USD ticker price and source timestamp."""
    safe_id = quote(str(coin_id).strip(), safe="-")
    data = _get_json(f"https://api.coinpaprika.com/v1/tickers/{safe_id}", params={"quotes": "USD"})
    try:
        price = float(data["quotes"]["USD"]["price"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MarketDataError("قیمت دلاری رمزارز در پاسخ CoinPaprika پیدا نشد.") from exc
    if price <= 0:
        raise MarketDataError("قیمت رمزارز صفر یا منفی گزارش شده است.")
    return {
        "price": price,
        "currency": "USD",
        "source": "CoinPaprika",
        "source_updated_at": data.get("last_updated"),
        "fetched_at": utc_now_iso(),
        "stale": False,
    }


def fetch_usd_free_rate() -> dict[str, Any]:
    """Return Tehran free-market USD rate in rials from NerkhAra."""
    data = _get_json("https://nerkhara.com/api/v1/latest/usd.json")
    item = data.get("item", {}) if isinstance(data, dict) else {}
    try:
        price = float(item["price"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MarketDataError("نرخ دلار در پاسخ NerkhAra پیدا نشد.") from exc
    if price <= 0:
        raise MarketDataError("نرخ دلار صفر یا منفی گزارش شده است.")

    unit = str(item.get("unit") or "").upper()
    if unit == "IRT":  # NerkhAra documents IRT as toman.
        price_irr = price * 10
    elif unit == "IRR":
        price_irr = price
    else:
        raise MarketDataError(f"واحد غیرمنتظره نرخ دلار از NerkhAra: {unit or 'نامشخص'}")

    return {
        "price": price_irr,
        "source_price": price,
        "source_unit": unit,
        "currency": "IRR per USD",
        "source": "NerkhAra / USD آزاد",
        "source_updated_at": item.get("updated_utc") or data.get("generated_utc"),
        "fetched_at": utc_now_iso(),
        "stale": bool(item.get("stale", False)),
        "sources_count": item.get("sources"),
        "spread_pct": item.get("spread_pct"),
    }


def fetch_nerkhara_local_rate(rate_id: str, display_name: str) -> dict[str, Any]:
    """Fetch a local Tehran-market rate (e.g. USDT) and normalize it to rials."""
    safe_id = quote(rate_id.strip(), safe="-")
    data = _get_json(f"https://nerkhara.com/api/v1/latest/{safe_id}.json")
    item = data.get("item", {}) if isinstance(data, dict) else {}
    try:
        price = float(item["price"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MarketDataError(f"قیمت {display_name} در پاسخ NerkhAra پیدا نشد.") from exc
    if price <= 0:
        raise MarketDataError(f"قیمت {display_name} صفر یا منفی گزارش شده است.")
    unit = str(item.get("unit") or "").upper()
    if unit == "IRT":
        price_irr = price * 10
    elif unit == "IRR":
        price_irr = price
    else:
        raise MarketDataError(f"واحد غیرمنتظره قیمت {display_name}: {unit or 'نامشخص'}")
    return {
        "price": price_irr,
        "source_price": price,
        "source_unit": unit,
        "currency": f"IRR per {rate_id.upper()}",
        "source": f"NerkhAra / {display_name} بازار آزاد",
        "source_updated_at": item.get("updated_utc") or data.get("generated_utc"),
        "fetched_at": utc_now_iso(),
        "stale": bool(item.get("stale", False)),
        "sources_count": item.get("sources"),
        "spread_pct": item.get("spread_pct"),
    }
