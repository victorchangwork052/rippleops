-- Fallback traversal (handoff section 44) when BigQuery Graph is unavailable.

WITH RECURSIVE up AS (
  SELECT
    parent_item_id AS top_id,
    [CONCAT(parent_item_id, '|', child_item_id, '|', CAST(qty_per_parent AS STRING))] AS edges,
    1 AS depth
  FROM `{dataset}.bom_edges`
  WHERE child_item_id = @part_id
    AND effective_from <= @as_of
    AND (effective_to IS NULL OR effective_to >= @as_of)
  UNION ALL
  SELECT
    b.parent_item_id,
    ARRAY_CONCAT([CONCAT(b.parent_item_id, '|', b.child_item_id, '|', CAST(b.qty_per_parent AS STRING))], up.edges),
    up.depth + 1
  FROM up
  JOIN `{dataset}.bom_edges` AS b ON b.child_item_id = up.top_id
  WHERE up.depth < 8
    AND b.effective_from <= @as_of
    AND (b.effective_to IS NULL OR b.effective_to >= @as_of)
)
SELECT up.top_id AS product_id, up.edges
FROM up
JOIN `{dataset}.item_master` AS i ON i.item_id = up.top_id
WHERE i.item_type = 'FINISHED_GOOD'
