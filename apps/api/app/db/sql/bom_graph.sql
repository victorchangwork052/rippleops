-- BigQuery Graph definition for the multi-level BOM.
-- {dataset} is replaced with `project.dataset` by scripts/seed_bigquery.py.

CREATE OR REPLACE PROPERTY GRAPH `{dataset}.bom_graph`
  NODE TABLES (
    `{dataset}.item_master` AS Item
      KEY (item_id)
      LABEL Item PROPERTIES (item_id, item_name, item_type, product_family, status)
  )
  EDGE TABLES (
    `{dataset}.bom_edges` AS BomEdge
      KEY (parent_item_id, child_item_id)
      SOURCE KEY (parent_item_id) REFERENCES Item (item_id)
      DESTINATION KEY (child_item_id) REFERENCES Item (item_id)
      LABEL HAS_CHILD PROPERTIES (parent_item_id, child_item_id, qty_per_parent, effective_from, effective_to)
  );
