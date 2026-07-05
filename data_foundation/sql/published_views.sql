CREATE OR REPLACE VIEW pub_stock_daily_kline AS
SELECT
  ts_code AS asset_id,
  'CN_A' AS market,
  'stock' AS asset_type,
  trade_date,
  open,
  high,
  low,
  close,
  vol,
  amount,
  'token_daily_details' AS source,
  trade_date AS source_end_date,
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s') AS published_at,
  'v1' AS data_version,
  CASE WHEN close IS NULL THEN 'warning' ELSE 'pass' END AS quality_status
FROM token_daily_details;

CREATE OR REPLACE VIEW pub_stock_weekly_kline AS
SELECT
  ts_code AS asset_id,
  'CN_A' AS market,
  'stock' AS asset_type,
  trade_date AS period_end_date,
  open,
  high,
  low,
  close,
  vol,
  amount,
  'token_weekly_details' AS source,
  trade_date AS source_end_date,
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s') AS published_at,
  'v1' AS data_version,
  CASE WHEN close IS NULL THEN 'warning' ELSE 'pass' END AS quality_status
FROM token_weekly_details;

CREATE OR REPLACE VIEW pub_stock_monthly_kline AS
SELECT
  ts_code AS asset_id,
  'CN_A' AS market,
  'stock' AS asset_type,
  trade_date AS period_end_date,
  open,
  high,
  low,
  close,
  vol,
  amount,
  'token_monthly_details' AS source,
  trade_date AS source_end_date,
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s') AS published_at,
  'v1' AS data_version,
  CASE WHEN close IS NULL THEN 'warning' ELSE 'pass' END AS quality_status
FROM token_monthly_details;

CREATE OR REPLACE VIEW pub_stock_daily_basic AS
SELECT
  ts_code AS asset_id,
  'CN_A' AS market,
  'stock' AS asset_type,
  trade_date,
  close,
  turnover_rate,
  pe_ttm,
  pb,
  total_mv,
  circ_mv,
  trade_date AS source_end_date,
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s') AS published_at,
  'v1' AS data_version,
  CASE WHEN close IS NULL THEN 'warning' ELSE 'pass' END AS quality_status
FROM token_daily_basic;

CREATE OR REPLACE VIEW pub_stock_asset_basic AS
SELECT
  basic.ts_code AS asset_id,
  basic.symbol,
  basic.name,
  COALESCE(type_info.market, basic.market, 'CN_A') AS market,
  'stock' AS asset_type,
  COALESCE(type_info.exchange, basic.exchange) AS exchange,
  COALESCE(type_info.list_status, basic.list_status) AS list_status,
  basic.update_date AS snapshot_date,
  basic.update_date AS source_end_date,
  STR_TO_DATE(CONCAT(basic.update_date, ' 23:59:59'), '%Y%m%d %H:%i:%s') AS published_at,
  'v1' AS data_version,
  CASE WHEN basic.name IS NULL THEN 'warning' ELSE 'pass' END AS quality_status
FROM token_stock_basic basic
LEFT JOIN token_type type_info
  ON basic.ts_code = type_info.ts_code;

CREATE OR REPLACE VIEW pub_stock_daily_indicator AS
SELECT
  ts_code AS asset_id,
  'CN_A' AS market,
  'stock' AS asset_type,
  trade_date,
  'ma20' AS indicator_name,
  'v1' AS indicator_version,
  'window_20' AS params_hash,
  ma20 AS indicator_value,
  'ma_price_daily_statistic' AS source_table,
  'ma20' AS source_column,
  trade_date AS source_start_date,
  trade_date AS source_end_date,
  trade_date AS calculation_date,
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s') AS available_time,
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s') AS published_at,
  'v1' AS data_version,
  CASE WHEN ma20 IS NULL THEN 'warning' ELSE 'pass' END AS quality_status
FROM ma_price_daily_statistic
UNION ALL
SELECT
  ts_code, 'CN_A', 'stock', trade_date,
  'close_above_ma20_flag', 'v1', 'window_20', ma20_above,
  'ma_price_daily_statistic', 'ma20_above', trade_date, trade_date, trade_date,
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s'),
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s'),
  'v1',
  CASE WHEN ma20_above IS NULL THEN 'warning' ELSE 'pass' END
FROM ma_price_daily_statistic
UNION ALL
SELECT
  ts_code, 'CN_A', 'stock', trade_date,
  'amount_ratio_20d', 'v1', 'window_20', ratio_20d,
  'amount_daily_statistic', 'ratio_20d', trade_date, trade_date, trade_date,
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s'),
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s'),
  'v1',
  CASE WHEN ratio_20d IS NULL THEN 'warning' ELSE 'pass' END
FROM amount_daily_statistic
UNION ALL
SELECT
  ts_code, 'CN_A', 'stock', trade_date,
  'volatility_60d', 'v1', 'window_60', volatility_60d,
  'volatility_daily_statistic', 'volatility_60d', trade_date, trade_date, trade_date,
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s'),
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s'),
  'v1',
  CASE WHEN volatility_60d IS NULL THEN 'warning' ELSE 'pass' END
FROM volatility_daily_statistic;

CREATE OR REPLACE VIEW pub_stock_weekly_indicator AS
SELECT
  ts_code AS asset_id,
  'CN_A' AS market,
  'stock' AS asset_type,
  trade_date AS period_end_date,
  'weekly_ma5' AS indicator_name,
  'candidate_v1' AS indicator_version,
  'window_5' AS params_hash,
  ma5 AS indicator_value,
  'ma_price_weekly_statistic' AS source_table,
  'ma5' AS source_column,
  trade_date AS source_start_date,
  trade_date AS source_end_date,
  trade_date AS calculation_date,
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s') AS available_time,
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s') AS published_at,
  'v1' AS data_version,
  CASE WHEN ma5 IS NULL THEN 'warning' ELSE 'pass' END AS quality_status
FROM ma_price_weekly_statistic
UNION ALL
SELECT
  ts_code, 'CN_A', 'stock', trade_date,
  'weekly_ma10', 'candidate_v1', 'window_10', ma10,
  'ma_price_weekly_statistic', 'ma10', trade_date, trade_date, trade_date,
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s'),
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s'),
  'v1',
  CASE WHEN ma10 IS NULL THEN 'warning' ELSE 'pass' END
FROM ma_price_weekly_statistic
UNION ALL
SELECT
  ts_code, 'CN_A', 'stock', trade_date,
  'weekly_ma20', 'candidate_v1', 'window_20', ma20,
  'ma_price_weekly_statistic', 'ma20', trade_date, trade_date, trade_date,
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s'),
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s'),
  'v1',
  CASE WHEN ma20 IS NULL THEN 'warning' ELSE 'pass' END
FROM ma_price_weekly_statistic
UNION ALL
SELECT
  ts_code, 'CN_A', 'stock', trade_date,
  'weekly_amount_ratio', 'candidate_v1', 'window_default', amount_ratio,
  'amount_weekly_statistic', 'amount_ratio', trade_date, trade_date, trade_date,
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s'),
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s'),
  'v1',
  CASE WHEN amount_ratio IS NULL THEN 'warning' ELSE 'pass' END
FROM amount_weekly_statistic
UNION ALL
SELECT
  ts_code, 'CN_A', 'stock', trade_date,
  'weekly_volatility_20w', 'candidate_v1', 'window_20', volatility_20w,
  'volatility_weekly_statistic', 'volatility_20w', trade_date, trade_date, trade_date,
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s'),
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s'),
  'v1',
  CASE WHEN volatility_20w IS NULL THEN 'warning' ELSE 'pass' END
FROM volatility_weekly_statistic
UNION ALL
SELECT
  ts_code, 'CN_A', 'stock', trade_date,
  'weekly_volatility_30w', 'candidate_v1', 'window_30', volatility_30w,
  'volatility_weekly_statistic', 'volatility_30w', trade_date, trade_date, trade_date,
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s'),
  STR_TO_DATE(CONCAT(trade_date, ' 23:59:59'), '%Y%m%d %H:%i:%s'),
  'v1',
  CASE WHEN volatility_30w IS NULL THEN 'warning' ELSE 'pass' END
FROM volatility_weekly_statistic;

CREATE OR REPLACE VIEW pub_data_quality_status AS
SELECT
  data_product,
  data_date,
  'CN_A' AS market,
  'stock' AS asset_type,
  CASE WHEN record_count > 0 THEN 'ready' ELSE 'blocked' END AS status,
  CASE WHEN record_count > 0 THEN 'pass' ELSE 'failed' END AS quality_level,
  record_count,
  1 AS expected_min_records,
  source_tables,
  data_date AS source_end_date,
  STR_TO_DATE(CONCAT(data_date, ' 23:59:59'), '%Y%m%d %H:%i:%s') AS published_at,
  'v1' AS data_version,
  NULL AS error_message
FROM (
  SELECT 'pub_stock_daily_kline' AS data_product, trade_date AS data_date, COUNT(*) AS record_count, 'token_daily_details' AS source_tables
  FROM pub_stock_daily_kline GROUP BY trade_date
  UNION ALL
  SELECT 'pub_stock_daily_basic', trade_date, COUNT(*), 'token_daily_basic'
  FROM pub_stock_daily_basic GROUP BY trade_date
  UNION ALL
  SELECT 'pub_stock_daily_indicator', trade_date, COUNT(*), 'ma_price_daily_statistic,amount_daily_statistic,volatility_daily_statistic'
  FROM pub_stock_daily_indicator GROUP BY trade_date
  UNION ALL
  SELECT 'pub_stock_weekly_indicator', period_end_date, COUNT(*), 'ma_price_weekly_statistic,amount_weekly_statistic,volatility_weekly_statistic'
  FROM pub_stock_weekly_indicator GROUP BY period_end_date
  UNION ALL
  SELECT 'pub_stock_asset_basic', snapshot_date, COUNT(*), 'token_stock_basic,token_type'
  FROM pub_stock_asset_basic GROUP BY snapshot_date
) product_quality;
