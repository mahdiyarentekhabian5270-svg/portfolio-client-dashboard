from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape as html_escape
from typing import Any

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from calculations import crypto_value_irr, fund_value_irr, usd_value_irr
from market_data import (
    MarketDataError,
    fetch_coinpaprika_quote,
    fetch_coinpaprika_ticker_map,
    fetch_nerkhara_local_rate,
    fetch_tsetmc_quote,
    fetch_usd_free_rate,
)
from storage import (
    get_last_quote,
    init_storage,
    load_assets,
    load_snapshots,
    save_last_quote,
    save_snapshot,
)


st.set_page_config(
    page_title="پایشگر پرتفو | Portfolio Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;800&display=swap');
    :root { --pm-ink:#17233b; --pm-muted:#718096; --pm-line:#e7edf5; --pm-blue:#315cde; --pm-bg:#f4f7fb; }
    html, body, .stApp { font-family:'Vazirmatn',Tahoma,sans-serif !important; }
    .stApp { background:var(--pm-bg); color:var(--pm-ink); direction:ltr; }
    [data-testid="stAppViewContainer"] { direction:rtl; }
    header[data-testid="stHeader"] { background:rgba(244,247,251,.88); }
    [data-testid="stMainBlockContainer"] { max-width:1500px; padding:2rem 2.4rem 3rem; direction:rtl; }
    [data-testid="stMain"] { direction:rtl; }
    [data-testid="stMarkdownContainer"] { direction:rtl; text-align:right; }
    [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { text-align:right; line-height:1.85; }
    .stHorizontalBlock { direction:rtl; gap:1rem; }
    [data-testid="stSidebar"] { direction:rtl; min-width:340px !important; width:340px !important; background:#fff; border-left:1px solid var(--pm-line); }
    [data-testid="stSidebarContent"] { direction:rtl; padding:1.25rem 1rem 2rem; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"], [data-testid="stSidebar"] label { text-align:right !important; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color:var(--pm-ink); letter-spacing:-.3px; }
    [data-testid="stSidebar"] button { border-radius:11px !important; min-height:42px; font-weight:600; }
    [data-testid="stSidebar"] input, [data-testid="stSidebar"] [data-baseweb="select"] { border-radius:10px !important; }
    [data-testid="stDataFrame"] { direction:rtl; border:1px solid var(--pm-line); border-radius:12px; overflow:hidden; }
    [data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--pm-line) !important; border-radius:18px !important; background:#fff; }
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"] { text-align:right; }
    .pm-hero { display:flex; align-items:center; justify-content:space-between; gap:24px; padding:30px 34px; margin:0 0 22px; border-radius:24px; color:#fff; background:linear-gradient(120deg,#132443 0%,#1e3b69 55%,#315c9c 100%); box-shadow:0 14px 35px rgba(24,51,91,.14); direction:rtl; }
    .pm-eyebrow { font-size:11px; font-weight:700; letter-spacing:1.5px; opacity:.72; margin-bottom:8px; }
    .pm-hero h1 { color:#fff; font-size:clamp(25px,3vw,35px); line-height:1.45; margin:0 0 5px; font-weight:800; }
    .pm-hero p { color:rgba(255,255,255,.76); margin:0; font-size:13px; }
    .pm-hero-side { min-width:190px; display:flex; flex-direction:column; align-items:flex-start; gap:10px; }
    .pm-live { display:inline-flex; align-items:center; gap:8px; padding:8px 13px; border:1px solid rgba(255,255,255,.22); background:rgba(255,255,255,.1); border-radius:999px; font-size:12px; white-space:nowrap; }
    .pm-live-dot { width:8px; height:8px; border-radius:50%; background:#4be0a2; box-shadow:0 0 0 4px rgba(75,224,162,.15); }
    .pm-refresh-note { color:rgba(255,255,255,.7); font-size:11px; }
    .pm-metric { height:100%; min-height:138px; padding:18px 20px; border:1px solid var(--pm-line); border-radius:18px; background:#fff; box-shadow:0 5px 18px rgba(26,48,81,.035); direction:rtl; }
    .pm-metric-head { display:flex; align-items:center; justify-content:space-between; color:var(--pm-muted); font-size:12px; font-weight:600; }
    .pm-metric-icon { width:34px; height:34px; display:grid; place-items:center; border-radius:11px; background:#edf2ff; color:var(--pm-blue); font-size:18px; font-weight:800; }
    .pm-metric-value { margin:13px 0 5px; color:var(--pm-ink); font-size:clamp(17px,1.7vw,24px); font-weight:800; line-height:1.5; letter-spacing:-.5px; font-variant-numeric:tabular-nums; }
    .pm-metric-detail { color:#8a96a8; font-size:11px; line-height:1.7; }
    .pm-metric.green .pm-metric-icon { background:#e8f8f1; color:#159568; }
    .pm-metric.gold .pm-metric-icon { background:#fff6e5; color:#b7791f; }
    .pm-metric.purple .pm-metric-icon { background:#f2edff; color:#7652c8; }
    .pm-section-title { display:flex; align-items:center; justify-content:space-between; gap:12px; margin:4px 0 14px; color:var(--pm-ink); font-size:17px; font-weight:800; }
    .pm-section-sub { color:#8a96a8; font-size:11px; font-weight:400; }
    .pm-panel-title { margin:0 0 5px; font-size:16px; font-weight:800; color:var(--pm-ink); }
    .pm-panel-sub { margin:0 0 17px; font-size:11px; color:#8a96a8; }
    .pm-alert { padding:12px 16px; margin:10px 0; border-radius:12px; font-size:12px; line-height:1.9; direction:rtl; }
    .pm-alert.warn { color:#875b12; background:#fff7e6; border:1px solid #f7e7bf; }
    .pm-alert.info { color:#285a9b; background:#edf5ff; border:1px solid #d9e9ff; }
    .pm-alert.danger { color:#a13d3d; background:#fff0f0; border:1px solid #f5d6d6; }
    .pm-empty { text-align:center; padding:42px 24px; border:1px dashed #cbd6e5; border-radius:22px; background:#fff; margin:18px 0; }
    .pm-empty-icon { width:62px; height:62px; display:grid; place-items:center; margin:0 auto 15px; border-radius:20px; background:#edf2ff; color:#315cde; font-size:29px; }
    .pm-empty h3 { margin:0 0 8px; color:var(--pm-ink); font-size:19px; }
    .pm-empty p { margin:0 auto; max-width:560px; color:#78869a; font-size:12px; line-height:2; }
    .pm-chip-row { display:flex; justify-content:center; flex-wrap:wrap; gap:8px; margin-top:18px; }
    .pm-chip { color:#52627a; background:#f2f5fa; border:1px solid #e7edf5; border-radius:99px; padding:7px 12px; font-size:11px; }
    .pm-alloc-item { margin:0 0 18px; }
    .pm-alloc-head { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:7px; font-size:12px; }
    .pm-alloc-name { color:#44536b; font-weight:600; }
    .pm-alloc-pct { color:var(--pm-ink); font-weight:800; font-variant-numeric:tabular-nums; }
    .pm-alloc-track { width:100%; height:9px; background:#edf1f7; border-radius:999px; overflow:hidden; }
    .pm-alloc-fill { height:100%; border-radius:999px; background:linear-gradient(90deg,#315cde,#6f8ff0); }
    .pm-alloc-value { margin-top:5px; color:#8995a7; font-size:10px; }
    .pm-footnote { color:#8b97a8; font-size:11px; line-height:1.9; }
    .pm-number { direction:ltr; unicode-bidi:plaintext; font-variant-numeric:tabular-nums; }
    @media (max-width: 1050px) { [data-testid="stMainBlockContainer"]{padding:1.2rem 1rem 2rem;} [data-testid="stSidebar"]{min-width:300px !important;width:300px !important;} .pm-hero{padding:24px;} }
    @media (max-width: 720px) { .pm-hero{display:block;} .pm-hero-side{align-items:flex-start;margin-top:18px;} .pm-metric{min-height:120px;} }
    </style>
    """,
    unsafe_allow_html=True,
)


# Cached source calls. UI reruns each minute, while provider requests are throttled
# to roughly the actual publication cadence of each free data source.
@st.cache_data(ttl=60, show_spinner=False)
def cached_tsetmc_quote(ins_code: str) -> dict[str, Any]:
    return fetch_tsetmc_quote(ins_code)


@st.cache_data(ttl=300, show_spinner=False)
def cached_crypto_ticker_map() -> dict[str, dict[str, Any]]:
    return fetch_coinpaprika_ticker_map()


@st.cache_data(ttl=300, show_spinner=False)
def cached_crypto_quote(coin_id: str) -> dict[str, Any]:
    return fetch_coinpaprika_quote(coin_id)


@st.cache_data(ttl=600, show_spinner=False)
def cached_usd_rate() -> dict[str, Any]:
    return fetch_usd_free_rate()


@st.cache_data(ttl=600, show_spinner=False)
def cached_usdt_local_rate() -> dict[str, Any]:
    return fetch_nerkhara_local_rate("usdt", "تتر")


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def age_minutes(value: str | None) -> float | None:
    parsed = parse_time(value)
    if parsed is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 60)


def rial(value: float | int | None, compact: bool = False) -> str:
    if value is None:
        return "—"
    value = float(value)
    if compact and abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:,.2f} میلیارد ریال"
    if compact and abs(value) >= 1_000_000:
        return f"{value / 1_000_000:,.2f} میلیون ریال"
    return f"{value:,.0f} ریال"


def number(value: float | int | None, digits: int = 8) -> str:
    if value is None:
        return "—"
    value = float(value)
    if abs(value) >= 1000:
        return f"{value:,.2f}"
    return f"{value:,.{digits}f}".rstrip("0").rstrip(".")


def get_quote(
    asset: dict[str, Any],
    crypto_ticker_map: dict[str, dict[str, Any]] | None = None,
    crypto_map_error: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    key = f"asset:{asset['id']}"
    try:
        if asset["type"] == "fund":
            quote_data = cached_tsetmc_quote(asset["instrument_code"])
        elif asset["type"] == "crypto":
            coin_id = asset["coin_id"]
            if coin_id.casefold() == "usdt-tether":
                # Tether can trade at a premium/discount to USD in Iran, so
                # use its local free-market quote instead of assuming $1.
                quote_data = cached_usdt_local_rate()
            elif crypto_ticker_map and coin_id in crypto_ticker_map:
                quote_data = crypto_ticker_map[coin_id]
            else:
                # The free bulk endpoint covers the top 2,000 coins. For an
                # asset outside that list, try the single-coin endpoint.
                quote_data = cached_crypto_quote(coin_id)
        else:
            return None, "نوع دارایی ناشناخته است."
        save_last_quote(key, quote_data)
        return quote_data, None
    except Exception as exc:
        old = get_last_quote(key)
        return old, str(exc)


def get_usd_quote() -> tuple[dict[str, Any] | None, str | None]:
    try:
        quote_data = cached_usd_rate()
        save_last_quote("fx:usd_irr", quote_data)
        return quote_data, None
    except Exception as exc:
        return get_last_quote("fx:usd_irr"), str(exc)


def mark_quote_age(quote_data: dict[str, Any], asset_type: str) -> tuple[bool, str]:
    """Return stale flag and readable age label using the provider timestamp."""
    source_time = quote_data.get("source_updated_at")
    age = age_minutes(source_time)
    source_stale = bool(quote_data.get("stale"))
    if asset_type == "crypto":
        stale = source_stale or (age is not None and age > 20)
    elif asset_type == "fx":
        stale = source_stale or (age is not None and age > 30)
    else:
        stale = source_stale or (age is not None and age > 72 * 60)
    if age is None:
        age_text = "زمان منبع اعلام نشده"
    elif age < 1:
        age_text = "کمتر از ۱ دقیقه"
    else:
        age_text = f"حدود {age:.0f} دقیقه قبل"
    if quote_data.get("fallback_from_cache"):
        stale = True
        age_text += "؛ آخرین داده ذخیره‌شده"
    return stale, age_text


def get_market_snapshot(assets: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any] | None, str | None]:
    usd_quote, fx_error = get_usd_quote()
    usd_irr = float(usd_quote["price"]) if usd_quote else None
    fx_stale, fx_age_label = mark_quote_age(usd_quote, "fx") if usd_quote else (True, "نرخ دلار در دسترس نیست")

    crypto_ticker_map: dict[str, dict[str, Any]] | None = None
    crypto_map_error: str | None = None
    needs_coinpaprika = any(
        asset.get("type") == "crypto" and str(asset.get("coin_id", "")).casefold() != "usdt-tether"
        for asset in assets
    )
    if needs_coinpaprika:
        try:
            crypto_ticker_map = cached_crypto_ticker_map()
        except Exception as exc:
            crypto_map_error = str(exc)

    rows: list[dict[str, Any]] = []
    for asset in assets:
        quote_data, error = get_quote(asset, crypto_ticker_map, crypto_map_error)
        row: dict[str, Any] = {
            "id": asset["id"],
            "asset": asset.get("name") or asset.get("symbol") or "دارایی",
            "symbol": asset.get("symbol", ""),
            "type": asset["type"],
            "type_fa": {"fund": "صندوق بورسی", "crypto": "رمزارز", "usd": "دلار نقدی"}.get(asset["type"], "سایر"),
            "quantity": float(asset.get("quantity", 0)),
            "quote": quote_data,
            "quote_error": error,
            "price": None,
            "price_currency": None,
            "value_irr": None,
            "stale": True,
            "age_label": "قیمت دریافت نشده",
            "source": "—",
            "status": "بدون قیمت",
        }
        if asset["type"] == "usd":
            row["price"] = usd_irr
            row["price_currency"] = "ریال / دلار"
            row["source"] = "NerkhAra / USD آزاد"
            row["stale"] = fx_stale
            row["age_label"] = fx_age_label
            if usd_irr is not None:
                row["value_irr"] = usd_value_irr(row["quantity"], usd_irr)
                row["status"] = "قدیمی" if fx_stale else "به‌روز"
            elif fx_error:
                row["quote_error"] = fx_error
        elif quote_data:
            row["price"] = float(quote_data["price"])
            row["price_currency"] = quote_data.get("currency", "")
            row["source"] = quote_data.get("source", "—")
            quote_age_type = "fx" if quote_data.get("currency", "").startswith("IRR per") else asset["type"]
            row["stale"], row["age_label"] = mark_quote_age(quote_data, quote_age_type)
            if asset["type"] == "fund":
                row["value_irr"] = fund_value_irr(row["quantity"], row["price"])
            elif asset["type"] == "crypto" and quote_data.get("currency", "").startswith("IRR per"):
                row["value_irr"] = fund_value_irr(row["quantity"], row["price"])
            elif asset["type"] == "crypto" and usd_irr is not None:
                row["value_irr"] = crypto_value_irr(row["quantity"], row["price"], usd_irr)
                row["stale"] = row["stale"] or fx_stale
                row["age_label"] += f" | دلار: {fx_age_label}"
            if row["value_irr"] is not None:
                row["status"] = "قدیمی" if row["stale"] else "به‌روز"
            elif asset["type"] == "crypto" and usd_irr is None:
                row["status"] = "منتظر نرخ دلار"
        elif error:
            row["quote_error"] = error
        rows.append(row)
    return rows, usd_quote, fx_error


def metric_card(label: str, value: str, detail: str, icon: str, accent: str = "blue") -> None:
    st.markdown(
        f"""<div class="pm-metric {accent}">
        <div class="pm-metric-head"><span>{label}</span><span class="pm-metric-icon">{icon}</span></div>
        <div class="pm-metric-value">{value}</div>
        <div class="pm-metric-detail">{detail}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def section_title(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""<div class="pm-section-title"><span>{title}</span><span class="pm-section-sub">{subtitle}</span></div>""",
        unsafe_allow_html=True,
    )


init_storage()
st_autorefresh(interval=60_000, key="portfolio_auto_refresh")
# Client build: all write controls are intentionally disabled.
# Portfolio holdings are edited by the owner in assets.json in the GitHub repository.

now_label = datetime.now().strftime("%H:%M:%S")
st.markdown(
    f"""<div class="pm-hero">
      <div>
        <div class="pm-eyebrow">PORTFOLIO MONITOR · LIVE TRACKING</div>
        <h1>داشبورد پایش پرتفو</h1>
        <p>گزارش مشاهده مشتری · ارزش روز و ترکیب سرمایه‌گذاری · واحد محاسبات: ریال</p>
      </div>
      <div class="pm-hero-side">
        <span class="pm-live"><span class="pm-live-dot"></span> نسخه فقط‌خواندنی · پایش خودکار فعال</span>
        <span class="pm-refresh-note">آخرین بارگذاری صفحه: {now_label} · تازه‌سازی هر ۶۰ ثانیه</span>
      </div>
    </div>""",
    unsafe_allow_html=True,
)

assets = load_assets()
if not assets:
    st.markdown(
        """<div class="pm-empty">
          <div class="pm-empty-icon">◈</div>
          <h3>پرتفوی شما هنوز خالی است</h3>
          <p>برای شروع، از پنل مدیریت سمت راست یک صندوق بورسی، رمزارز یا دلار نقدی اضافه کنید. پس از ثبت مقدار دارایی، داشبورد قیمت آنلاین و ارزش ریالی آن را نمایش می‌دهد.</p>
          <div class="pm-chip-row"><span class="pm-chip">صندوق‌های بورسی</span><span class="pm-chip">رمزارزها</span><span class="pm-chip">دلار نقدی</span><span class="pm-chip">محاسبات به ریال</span></div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.stop()

with st.spinner("در حال دریافت آخرین قیمت‌های قابل دسترس..."):
    rows, usd_quote, fx_error = get_market_snapshot(assets)

priced_rows = [row for row in rows if row["value_irr"] is not None]
unpriced_rows = [row for row in rows if row["value_irr"] is None]
all_priced = len(priced_rows) == len(rows)
all_fresh = all(not row["stale"] for row in priced_rows) and not unpriced_rows
priced_total = sum(row["value_irr"] for row in priced_rows)
complete_total = priced_total if all_priced else None
usd_irr = float(usd_quote["price"]) if usd_quote else None

if all_priced and all_fresh:
    save_snapshot(priced_total, len(rows), usd_irr)

# KPI cards use a narrow HTML layer so typography and RTL stay consistent in Safari.
kpi_cols = st.columns([1.45, 1, 1, 1], gap="medium")
with kpi_cols[0]:
    if complete_total is not None:
        metric_card("ارزش کل پرتفو", rial(complete_total, compact=True), "مجموع کامل تمام دارایی‌های ثبت‌شده", "◈", "blue")
    else:
        metric_card("ارزش دارایی‌های قیمت‌گذاری‌شده", rial(priced_total, compact=True), f"از {len(rows)} دارایی · {len(unpriced_rows)} مورد بدون قیمت معتبر", "◈", "blue")
with kpi_cols[1]:
    metric_card("تعداد دارایی‌ها", f"{len(assets):,} مورد", f"قیمت‌گذاری‌شده: {len(priced_rows)} مورد", "▦", "purple")
with kpi_cols[2]:
    metric_card("دلار آزاد", rial(usd_irr, compact=True) if usd_irr else "در دسترس نیست", "نرخ هر دلار به ریال", "$", "gold")
with kpi_cols[3]:
    status_label = "همه داده‌ها تازه‌اند" if all_fresh else "برخی داده‌ها قدیمی یا ناقص‌اند"
    metric_card("سلامت داده‌ها", "مناسب" if all_fresh else "نیازمند بررسی", status_label, "✓" if all_fresh else "!", "green" if all_fresh else "gold")

if not all_priced:
    st.markdown(
        f"<div class='pm-alert warn'>ارزش کل پرتفو هنوز کامل نیست؛ قیمت معتبر {len(unpriced_rows)} دارایی دریافت نشده است. عدد بالا فقط جمع دارایی‌های قیمت‌گذاری‌شده را نشان می‌دهد.</div>",
        unsafe_allow_html=True,
    )
if any(row["stale"] for row in priced_rows):
    st.markdown(
        "<div class='pm-alert info'>حداقل یک قیمت از داده قدیمی یا آخرین قیمت ذخیره‌شده استفاده می‌کند. زمان منبع و وضعیت هر دارایی را در بخش جزئیات بررسی کنید.</div>",
        unsafe_allow_html=True,
    )
if fx_error and not usd_quote:
    st.markdown(f"<div class='pm-alert danger'>نرخ دلار آزاد دریافت نشد: {html_escape(str(fx_error))}</div>", unsafe_allow_html=True)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
main_col, side_col = st.columns([1.55, 1], gap="large")

with main_col:
    section_title("دارایی‌های پرتفو", f"{len(rows)} دارایی ثبت‌شده")
    table_rows = []
    for row in rows:
        weight_label = (f"{row['value_irr'] / complete_total * 100:,.2f}%" if complete_total and row["value_irr"] is not None else "—")
        table_rows.append({
            "دارایی": row["asset"],
            "نماد": row["symbol"],
            "نوع": row["type_fa"],
            "مقدار": number(row["quantity"], 10),
            "قیمت واحد": (number(row["price"], 6) + (f" {row['price_currency']}" if row["price_currency"] else "")) if row["price"] is not None else "—",
            "ارزش روز (ریال)": rial(row["value_irr"], compact=True) if row["value_irr"] is not None else "قیمت ناموجود",
            "وزن": weight_label,
            "وضعیت": row["status"],
        })
    st.dataframe(
        pd.DataFrame(table_rows),
        use_container_width=True,
        hide_index=True,
        height=min(440, 76 + 42 * len(table_rows)),
        column_config={
            "دارایی": st.column_config.TextColumn("دارایی", width="medium"),
            "نماد": st.column_config.TextColumn("نماد", width="small"),
            "نوع": st.column_config.TextColumn("نوع", width="small"),
            "مقدار": st.column_config.TextColumn("مقدار", width="small"),
            "قیمت واحد": st.column_config.TextColumn("قیمت واحد", width="medium"),
            "ارزش روز (ریال)": st.column_config.TextColumn("ارزش روز (ریال)", width="medium"),
            "وزن": st.column_config.TextColumn("وزن", width="small"),
            "وضعیت": st.column_config.TextColumn("وضعیت", width="small"),
        },
    )
    st.markdown(
        "<div class='pm-footnote'>وزن هر دارایی فقط زمانی نمایش داده می‌شود که قیمت تمام دارایی‌ها معتبر باشد. قیمت صندوق بر مبنای آخرین معامله و در نبود آن بر مبنای قیمت پایانی است.</div>",
        unsafe_allow_html=True,
    )

with side_col:
    section_title("ترکیب سرمایه‌گذاری", "بر اساس ارزش روز")
    if priced_rows and priced_total > 0:
        by_type: dict[str, float] = {}
        for row in priced_rows:
            by_type[row["type_fa"]] = by_type.get(row["type_fa"], 0.0) + float(row["value_irr"])
        for name, value in sorted(by_type.items(), key=lambda item: item[1], reverse=True):
            pct = value / priced_total * 100
            safe_name = html_escape(str(name))
            st.markdown(
                f"""<div class="pm-alloc-item">
                  <div class="pm-alloc-head"><span class="pm-alloc-name">{safe_name}</span><span class="pm-alloc-pct">{pct:,.1f}%</span></div>
                  <div class="pm-alloc-track"><div class="pm-alloc-fill" style="width:{max(0,min(100,pct)):.2f}%"></div></div>
                  <div class="pm-alloc-value">{rial(value, compact=True)}</div>
                </div>""",
                unsafe_allow_html=True,
            )
        if not all_priced:
            st.markdown("<div class='pm-footnote'>درصدها بر اساس دارایی‌هایی محاسبه شده‌اند که قیمت معتبر دارند؛ ممکن است با وزن نهایی پرتفو متفاوت باشند.</div>", unsafe_allow_html=True)
    else:
        st.info("برای نمایش ترکیب، حداقل یک دارایی باید قیمت معتبر داشته باشد.")

    section_title("ارزش هر دارایی", "مقایسه ریالی")
    if priced_rows:
        for row in sorted(priced_rows, key=lambda item: item["value_irr"], reverse=True):
            pct = (row["value_irr"] / priced_total * 100) if priced_total else 0
            safe_asset = html_escape(str(row["asset"]))
            safe_symbol = html_escape(str(row["symbol"]))
            st.markdown(
                f"""<div class="pm-alloc-item" style="margin-bottom:13px">
                  <div class="pm-alloc-head"><span class="pm-alloc-name">{safe_asset} <span style="color:#98a2b3;font-weight:400">({safe_symbol})</span></span><span class="pm-alloc-pct">{pct:,.1f}%</span></div>
                  <div class="pm-alloc-track"><div class="pm-alloc-fill" style="width:{max(0,min(100,pct)):.2f}%"></div></div>
                  <div class="pm-alloc-value">{rial(row['value_irr'], compact=True)}</div>
                </div>""",
                unsafe_allow_html=True,
            )
    else:
        st.caption("هنوز داده کافی برای نمایش وجود ندارد.")

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
with st.expander("جزئیات قیمت، منابع داده و خطاها", expanded=bool(unpriced_rows)):
    for row in rows:
        with st.container(border=True):
            st.markdown(f"**{html_escape(str(row['asset']))} ({html_escape(str(row['symbol']))}) — {html_escape(str(row['status']))}**")
            c1, c2, c3 = st.columns(3)
            c1.write(f"منبع: {row['source']}")
            c2.write(f"زمان داده: {row['age_label']}")
            c3.write(f"ارزش: {rial(row['value_irr'], compact=True)}")
            if row.get("quote_error"):
                st.error(f"خطای دریافت قیمت: {html_escape(str(row['quote_error']))}")

# History and export tools.
history_col, export_col = st.columns([1.6, 1], gap="large")
with history_col:
    section_title("تاریخچه ارزش پرتفو", "روند تغییرات ارزش")
    snapshots = load_snapshots()
    if len(snapshots) >= 2:
        history_df = pd.DataFrame(snapshots)
        history_df["زمان"] = pd.to_datetime(history_df["captured_at"], utc=True).dt.tz_convert(None)
        history_df = history_df.set_index("زمان")[["total_value_irr"]].rename(columns={"total_value_irr": "ارزش پرتفو (ریال)"})
        st.line_chart(history_df, use_container_width=True)
    else:
        st.markdown(
            "<div class='pm-alert info'>نمودار تاریخچه در طول اجرای برنامه شکل می‌گیرد. در میزبانی ابری رایگان، تاریخچه محلی ممکن است پس از راه‌اندازی مجدد برنامه پاک شود؛ برای نگهداری دائمی تاریخچه باید پایگاه داده خارجی اضافه شود.</div>",
            unsafe_allow_html=True,
        )
with export_col:
    section_title("گزارش و پشتیبان‌گیری", "خروجی داده‌ها")
    st.markdown(
        "<div class='pm-footnote'>می‌توانید وضعیت فعلی دارایی‌ها و قیمت‌هایی را که در این نوبت دریافت شده‌اند به‌صورت CSV ذخیره کنید.</div>",
        unsafe_allow_html=True,
    )
    export_rows = []
    for row in rows:
        export_rows.append({
            "asset_id": row["id"],
            "asset": row["asset"],
            "symbol": row["symbol"],
            "asset_type": row["type"],
            "quantity": row["quantity"],
            "unit_price": row["price"],
            "price_currency": row["price_currency"],
            "value_irr": row["value_irr"],
            "source": row["source"],
            "stale": row["stale"],
            "source_timestamp": (row["quote"] or {}).get("source_updated_at") if row["quote"] else None,
        })
    csv_bytes = pd.DataFrame(export_rows).to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "دانلود گزارش فعلی پرتفو (CSV)",
        data=csv_bytes,
        file_name="portfolio_snapshot.csv",
        mime="text/csv",
        use_container_width=True,
        type="primary",
    )

st.divider()
st.markdown(
    "<div class='pm-footnote'>منابع قیمت: <a href='https://www.tsetmc.com/' target='_blank'>TSETMC</a> · "
    "<a href='https://coinpaprika.com/' target='_blank'>CoinPaprika</a> · "
    "<a href='https://nerkhara.com/en/api/' target='_blank'>NerkhAra</a>. "
    "قیمت‌ها برای پایش و برآورد ارزش هستند و لزوماً قیمت تضمین‌شده اجرای معامله نیستند. "
    "نرخ دلار NerkhAra در واحد تومان دریافت و پیش از محاسبه در ۱۰ ضرب می‌شود. "
    "چون ورود اطلاعات بر اساس تعداد واحد است، سود و زیان نسبت به قیمت خرید محاسبه نمی‌شود.</div>",
    unsafe_allow_html=True,
)
