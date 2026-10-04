-- Statistical demand forecast with BigQuery ML AI.FORECAST (Google's TimesFM
-- foundation model). No model training: the pre-trained model forecasts each
-- product's monthly shipment history directly.
SELECT
  product_id,
  forecast_timestamp,
  forecast_value,
  prediction_interval_lower_bound,
  prediction_interval_upper_bound
FROM AI.FORECAST(
  (
    SELECT product_id, TIMESTAMP(month) AS month_ts, CAST(shipped_qty AS FLOAT64) AS shipped_qty
    FROM `{dataset}.demand_history`
    WHERE product_id IN UNNEST(@product_ids)
  ),
  data_col => 'shipped_qty',
  timestamp_col => 'month_ts',
  id_cols => ['product_id'],
  horizon => {horizon},
  confidence_level => {confidence}
)
ORDER BY product_id, forecast_timestamp
