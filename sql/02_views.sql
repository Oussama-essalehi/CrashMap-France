-- CrashMap France - helper function and analysis views
SET search_path TO crashmap;

-- Rate rule used everywhere: no rate below the minimum number of accidents (analysis_params).
-- safe_rate(numerator, denominator, n_accidents, scale) = numerator / denominator * scale,
-- or NULL when n_accidents < min_accidents or the denominator is 0 / NULL.
CREATE OR REPLACE FUNCTION safe_rate(numerator numeric, denominator numeric,
                                     n_accidents numeric, scale numeric DEFAULT 100)
RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT CASE
        WHEN n_accidents < (SELECT param_value FROM crashmap.analysis_params
                            WHERE param_name = 'min_accidents') THEN NULL
        WHEN denominator IS NULL OR denominator = 0 THEN NULL
        ELSE ROUND(numerator * scale / denominator, 2)
    END
$$;

-- One row per accident with every dimension attribute (safe to COUNT(*): accident grain).
CREATE OR REPLACE VIEW v_accident AS
SELECT
    f.*,
    d.date, d.month, d.month_name, d.year_month, d.day_of_week, d.weekday_name, d.is_weekend,
    d.is_covid_year,
    t.time_band, t.time_band_order,
    p.dep_name, p.region_name, p.zone, p.population AS dep_population,
    l.com_code, l.com_name, l.in_town_label,
    c.lum_label, c.atm_label, c.surf_label, c.night,
    r.catr_label, r.vma_band, r.vma_band_order, r.plan_label, r.intersection_label
FROM fact_accident f
JOIN dim_date        d USING (date_key)
LEFT JOIN dim_time_band t USING (hour)
JOIN dim_population  p USING (dep_code)
JOIN dim_location    l USING (location_key)
JOIN dim_conditions  c USING (conditions_key)
JOIN dim_road        r USING (road_key);

-- One row per person involved, with user / vehicle type and the accident context.
-- COUNT(*) here counts people; count accidents with COUNT(DISTINCT accident_id) only.
CREATE OR REPLACE VIEW v_victim AS
SELECT
    v.*,
    u.catu, u.catu_label, u.user_mode,
    vt.catv_label, vt.vehicle_group,
    a.year, a.dep_code, a.in_town, a.date_key, a.hour
FROM fact_victim v
JOIN dim_user_type u USING (user_type_key)
LEFT JOIN dim_vehicle_type vt USING (catv)
JOIN fact_accident a USING (accident_id);

-- Department x year indicators with population-based rates.
CREATE OR REPLACE VIEW v_department_year AS
SELECT
    p.dep_code, p.dep_name, p.region_name, p.zone, p.population, f.year,
    COUNT(*)                                       AS n_accidents,
    SUM(f.n_killed)                                AS n_killed,
    COUNT(*) FILTER (WHERE f.fatal)                AS n_fatal_accidents,
    safe_rate(SUM(f.n_killed), COUNT(*), COUNT(*))                 AS killed_per_100_accidents,
    safe_rate(COUNT(*), p.population, COUNT(*), 100000)            AS accidents_per_100k,
    safe_rate(SUM(f.n_killed), p.population, COUNT(*), 100000)     AS killed_per_100k
FROM fact_accident f
JOIN dim_population p USING (dep_code)
GROUP BY p.dep_code, p.dep_name, p.region_name, p.zone, p.population, f.year;

-- National KPIs per year.
CREATE OR REPLACE VIEW v_kpi_year AS
SELECT
    year,
    COUNT(*)                          AS n_accidents,
    COUNT(*) FILTER (WHERE fatal)     AS n_fatal_accidents,
    SUM(n_killed)                     AS n_killed,
    SUM(n_hospitalized)               AS n_hospitalized,
    SUM(n_lightly_injured)            AS n_lightly_injured,
    SUM(n_victims)                    AS n_victims,
    safe_rate(SUM(n_killed), COUNT(*), COUNT(*)) AS killed_per_100_accidents,
    bool_or(year = 2020)              AS covid_year
FROM fact_accident
GROUP BY year;
