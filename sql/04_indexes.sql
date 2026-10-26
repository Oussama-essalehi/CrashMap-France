-- Indexes created after the bulk load (faster COPY).
SET search_path TO crashmap;

CREATE INDEX ix_fact_accident_date       ON fact_accident (date_key);
CREATE INDEX ix_fact_accident_dep_year   ON fact_accident (dep_code, year);
CREATE INDEX ix_fact_accident_location   ON fact_accident (location_key);
CREATE INDEX ix_fact_accident_conditions ON fact_accident (conditions_key);
CREATE INDEX ix_fact_accident_road       ON fact_accident (road_key);
CREATE INDEX ix_fact_vehicle_accident    ON fact_vehicle (accident_id);
CREATE INDEX ix_fact_victim_accident     ON fact_victim (accident_id);
CREATE INDEX ix_fact_victim_user_type    ON fact_victim (user_type_key);

ANALYZE;
