SELECT
  data_product,
  data_date,
  market,
  asset_type,
  status,
  quality_level,
  record_count,
  expected_min_records,
  source_tables,
  source_end_date,
  published_at,
  data_version,
  error_message
FROM pub_data_quality_status
WHERE data_date = :data_date
ORDER BY data_product;
