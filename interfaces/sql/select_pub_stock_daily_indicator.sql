SELECT
  trade_date,
  stock_code,
  indicator_name,
  indicator_value,
  data_version
FROM pub_stock_daily_indicator
WHERE trade_date = :data_date
  AND stock_code = :stock_code
ORDER BY indicator_name;
