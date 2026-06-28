# FinAgent — инструменты (MCP)

MCP-сервер `ru-finance` (локальный, stdio). 22 ручки поверх двух библиотек:
- **moex** (aioboy, v2.0.0) — весь ISS Московской биржи;
- **cbrapi** (v0.1.7) — данные ЦБ РФ;
плюс свой доменный слой (облигационная математика и отчёты по портфелю).

Принцип: ручки **generic** — конкретные бумаги агент подставляет из
[`assets.md`](assets.md) / [`context.md`](context.md). Цены — задержка ~15 мин
(бесплатный ISS), в выходные отдаётся цена последней сессии.

Запуск вручную: `.venv/bin/python -m ru_finance.mcp_server`
Регистрация в Claude Code: `claude mcp add ru-finance -- <венв-python> -m ru_finance.mcp_server`

Легенда: 🟢 факт-данные · 🧮 расчёт · 📁 читает assets.md

---

## MOEX — Московская биржа

### 🟢 `moex_resolve(query)`
Определить, как ISS адресует бумагу (акция/облигация/фонд/индекс).
- **Принимает:** `query` — тикер/ISIN/номер ОФЗ/название (`"SBER"`, `"26253"`, `"RU000A10C6F7"`).
- **Возвращает:** `{secid, engine, market, board, type, shortname, isin, group, is_traded}`.
- **Пример:** `moex_resolve("26253")` → `{"secid":"SU26253RMFS3","market":"bonds","board":"TQOB","type":"ofz_bond",...}`

### 🟢 `moex_quote(query)`
Текущая котировка акции/фонда (нормализованная, с фоллбэком цены).
- **Принимает:** `query` — тикер/название.
- **Возвращает:** `{secid, price, change_pct, bid, ask, open, low, high, value_today, vol_today, updatetime, price_field}`. `price_field` = какое поле дало цену (в выходные `MARKETPRICE`/`LCLOSEPRICE` вместо `LAST`).
- **Пример:** `moex_quote("SBER")` → `{"price":299.69,"change_pct":0.03,"price_field":"LAST",...}`

### 🟢 `moex_bond(query)`
Облигация со всеми метриками для анализа под ставку.
- **Принимает:** `query` — номер ОФЗ или ISIN.
- **Возвращает:** `{price_pct, change_pct, ytm, duration_years, mod_duration_years, coupon_pct, coupon_value, annual_coupon_per_bond, next_coupon, coupon_period_days, maturity, accrued_int, face_value}`.
- **Пример:** `moex_bond("26253")` → `{"price_pct":87.18,"ytm":15.93,"duration_years":5.9,"mod_duration_years":5.46,"annual_coupon_per_bond":130.0,"next_coupon":"2026-10-21","maturity":"2038-10-06",...}`

### 🟢 `moex_candles(query, frm, till, interval="24")`
Свечи OHLCV за период.
- **Принимает:** `query`; `frm`/`till` (`"YYYY-MM-DD"`); `interval` — `1,10,60`(час)`,24`(день)`,7`(нед)`,31`(мес)`,4`(кв).
- **Возвращает:** список `{begin, open, high, low, close, value, volume}`.
- **Пример:** `moex_candles("SBER","2026-06-22","2026-06-26","24")`

### 🟢 `moex_history(query, frm, till)`
Дневная история торгов (для доходностей/волатильности/просадок).
- **Принимает:** `query`; `frm`/`till` (`"YYYY-MM-DD"`).
- **Возвращает:** список строк истории (TRADEDATE, CLOSE, VOLUME, VALUE...).
- **Пример:** `moex_history("26253","2025-12-01","2026-06-27")`

### 🟢 `moex_dividends(query)`
История дивидендов по бумаге.
- **Принимает:** `query` — тикер.
- **Возвращает:** список `{registryclosedate, value, currencyid, ...}`.
- **Пример:** `moex_dividends("SBER")`

### 🟢 `moex_search_endpoints(pattern)`
Найти ISS-эндпоинт (шаблон) по подстроке пути — для доступа к данным без готовой ручки.
- **Принимает:** `pattern` — `"/candles"`, `"turnovers"`, `"/dividends"`.
- **Возвращает:** `[{id, path, variables}]`. `id` → в `moex_query`.
- **Пример:** `moex_search_endpoints("turnovers")`

### 🟢 `moex_query(template_id, vars=None, params=None)`
Запасной доступ к ЛЮБОМУ из ~252 эндпоинтов ISS.
- **Принимает:** `template_id` (из `moex_search_endpoints`); `vars` — переменные пути (`{engine, market, board, security}`); `params` — query-параметры (`{from, till, ...}`).
- **Возвращает:** `{block: [строки]}`.
- **Пример:** `moex_query(322, {"engine":"stock"}, {})`

---

## ЦБ РФ (cbrapi)

Все возвращают `{latest, latest_date, series[]}` (ряд) или `{latest, latest_date, rows[]}` (таблица). Даты опциональны (`"YYYY-MM-DD"`), `tail` — сколько последних точек.

### 🟢 `cbr_key_rate(first_date=None, last_date=None, tail=30)`
Ключевая ставка ЦБ — главный драйвер облигаций и рубля.
- **Пример:** `cbr_key_rate(tail=1)` → `{"latest":14.25,"latest_date":"2026-06-26"}`

### 🟢 `cbr_ruonia(...)`
RUONIA overnight (% годовых) — рыночный ориентир ставки денежного рынка. (Приведено к процентам.)

### 🟢 `cbr_ruonia_index(...)`
RUONIA-индекс + срочные средние `RUONIA_AVG_1M/3M/6M` (% годовых) — короткая кривая ставок денежного рынка. Живая замена прекращённому ROISfix. Таблица.

### 🟢 `cbr_ibor(...)`
MIACR — фактические средневзвешенные ставки межбанка по срокам (D1/D7/...). MosPrime/MIBOR прекращены — пустые колонки отфильтрованы. Таблица.

### 🟢 `cbr_currency(symbol, first_date, last_date, tail=30)`
Курс валюты ЦБ к рублю. `symbol`: `"USD"`, `"EUR"`, `"CNY"`. Даты обязательны.
- **Пример:** `cbr_currency("USD","2026-01-01","2026-06-27")`

### 🟢 `cbr_metals(...)`
Учётные цены ЦБ на драгметаллы (золото/серебро/платина/палладий). Таблица.

### 🟢 `cbr_reserves(...)`
Международные (золотовалютные) резервы РФ. Таблица.

---

## Облигационная математика

### 🧮 `bond_report(query)`
Глубокий разбор облигации: метрики + сценарии по ставке + реальная доходность.
- **Принимает:** `query` — номер ОФЗ/ISIN.
- **Возвращает:**
  - `bond` — как `moex_bond`;
  - `scenarios` — `{macaulay_years, breakeven_yield_rise_pp, scenarios:[{delta_pp, total_return_pct}]}` (полный доход за год при сдвиге доходности на ±п.п. + точка безубытка);
  - `real_return` — `[{inflation_pct, real_return_pct}]` (доходность к погашению за вычетом инфляции).
- **Пример:** `bond_report("26253")` → `scenarios.scenarios` показывает, что при −2 п.п. годовой доход ≈ +27%, безубыток при росте доходности до ~+3.4 п.п.

---

## Ожидания по ставке (G-кривая ОФЗ) 🧮

### 🧮 `rate_expectations(key_rate=None)`
Рыночные ожидания по ключевой ставке из кривой бескупонной доходности ОФЗ (КБД/zcyc). Только числа — интерпретация на стороне агента (см. `news.md`).
- **Принимает:** `key_rate` опц. (иначе из `cbr_key_rate`).
- **Возвращает:** `{as_of, key_rate, ruonia, curve[], signals, note}`.
  - `signals`: `slope_10y_1y`, `slope_2y_3m`; **брутто**-спреды `short_vs_key_1y/05y`, `priced_cut_1y_pp_gross` (⚠️ включают срочную премию, не чистое ожидание); якорь `short_vs_ruonia_1y`; форварды `fwd_1y_in_1y`, `fwd_1y_in_2y`, `fwd_3m_in_1y`; `inverted`; машинная метка `read` (`cuts_priced`|`hikes_priced`|`flat`, деадбенд ±0.25 пп).
- **Пример (27.06.2026):** `slope_10y_1y` 2.72; `short_vs_key_1y` −0.69; `fwd_1y_in_1y` 14.48; `read` `cuts_priced` (короткий конец ниже ставки, но форварды растут → near-term cut + «выше дольше»).

### 🧮 `curve_yield(years)`
Доходность G-кривой ОФЗ на произвольном сроке (% годовых) — привязка кривой к дюрации бумаги. **Точная NSS-модель MOEX** (Нельсон-Сигель + 9 гауссовых поправок из блока `params`), сверена с узлами `yearyields` до **0.0000 пп**; гладкая на изгибах и **экстраполирует за 20 лет**.
- **Пример:** `curve_yield(5.9)` → ~15.69% (под дюрацию ОФЗ 26253); `curve_yield(30)` → ~16.79% (экстраполяция).

---

## Портфель (доменные отчёты) 📁

**Сервер generic:** портфель ВСЕГДА передаётся параметром `assets` (markdown,
формат как [`assets.md`](assets.md)) — в коде сервера нет ничьих конкретных данных,
его можно хостить и делиться. Цены — живые.
**P&L приблизительный** (средняя цена покупки, без полученных купонов/дивидендов и налогов) — точный учёт появится с транзакциями.

Формат `assets` (строки): `- Название (ТИКЕР/ISIN): N шт. (цена_покупки ... [-> текущая])`; `'%'` в скобках = облигация (цена в % номинала), иначе акция/фонд (₽); `# Заголовок` = счёт, `## Заголовок` = класс.

### 🧮📁 `portfolio_snapshot(assets)`
Главная ручка — полный снимок портфеля.
- **Принимает:** `assets` — портфель в markdown.
- **Возвращает:** `{as_of, key_rate, total_value, total_cost, pnl, pnl_pct, positions[], allocation[], rate_risk, income}`.
  - `positions[]` — `{name, secid, account, bucket, qty, price, value, weight_pct, pnl_pct, change_pct, ytm, duration_years}`;
  - `allocation[]` — по корзинам (Длинные ОФЗ / Фонды акций / Акции / Корп. облигации / Денежный рынок);
  - `rate_risk` — `{portfolio_mod_duration_years, per_plus_1pp_pct/rub, per_minus_1pp_pct/rub}`;
  - `income` — `{annual_coupons, annual_money_market, annual_total_est, running_yield_pct}`.
- **Пример (факт на 27.06.2026):** total 467 065 ₽, P&L −7.6%, дюрация 3.59 г, +1 п.п. → −16 750 ₽, поток 51 051 ₽/год (10.9%), длинные ОФЗ 68.8%.

### 🧮📁 `portfolio_rate_whatif(delta_pp, assets)`
Что станет с портфелем при сдвиге доходностей облигаций на `delta_pp` п.п.
- **Принимает:** `delta_pp` (например `-2`, `1.5`); `assets` — портфель в markdown.
- **Возвращает:** `{delta_pp, portfolio_value_change_rub, portfolio_value_change_pct, new_total_value, bond_detail[]}`.
- **Пример:** `portfolio_rate_whatif(-2, <assets>)` → +33 501 ₽ (+7.2%), новый итог 500 566 ₽.

### 🧮📁 `portfolio_income_calendar(assets)`
Ближайшие поступления: следующий купон по каждой облигации + последний объявленный дивиденд.
- **Принимает:** `assets` — портфель в markdown.
- **Возвращает:** `{events:[{date, type, name, amount_rub}]}` (отсортировано по дате).

### 🧮📁 `portfolio_movers(assets)`
Кто вырос/просел.
- **Принимает:** `assets` — портфель в markdown.
- **Возвращает:** `{day_losers, day_gainers, worst_vs_cost, best_vs_cost}` (топ-3 в каждую сторону, по дневному изменению и по P&L против цены покупки).

---

## Заметки

- **Сеть:** `iss.moex.com` капризен (случайные таймауты) — в `session.py` зашиты ретраи. `cbr.ru` стабилен.
- **Шаблоны ISS** грузятся один раз при старте сервера (кэш на уровне класса aioboy).
- **Дивиденды** — эндпоинт вне шаблонов aioboy, берутся прямым GET.
- **Соответствие ToS:** личное использование, задержанные данные, без перераспространения.
