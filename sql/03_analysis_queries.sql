-- CrashMap France - analysis queries (one block per business question)
-- Every rate goes through safe_rate(): NULL when the group has fewer accidents than
-- analysis_params.min_accidents (default 100).
-- Accidents are always counted at the accident grain (fact_accident / v_accident), never on a
-- joined accident x vehicle x victim table.
SET search_path TO crashmap;

-- =============================================================================================
-- Q1. WHEN - accidents, deaths and severity by hour, weekday and month. Are night accidents deadlier?
-- =============================================================================================

-- Q1.a By hour of day: accidents, deaths, deaths per 100 accidents, share of all deaths.
SELECT
    hour,
    COUNT(*)                                          AS n_accidents,
    SUM(n_killed)                                     AS n_killed,
    safe_rate(SUM(n_killed), COUNT(*), COUNT(*))      AS killed_per_100_accidents,
    ROUND(100.0 * SUM(n_killed) / SUM(SUM(n_killed)) OVER (), 2) AS pct_of_all_deaths
FROM fact_accident
WHERE hour IS NOT NULL
GROUP BY hour
ORDER BY hour;

-- Q1.b By weekday: accidents and deaths, with the weekday's rank on death rate.
WITH by_day AS (
    SELECT d.day_of_week, d.weekday_name,
           COUNT(*) AS n_accidents, SUM(f.n_killed) AS n_killed
    FROM fact_accident f
    JOIN dim_date d USING (date_key)
    GROUP BY d.day_of_week, d.weekday_name
)
SELECT
    weekday_name, n_accidents, n_killed,
    safe_rate(n_killed, n_accidents, n_accidents) AS killed_per_100_accidents,
    RANK() OVER (ORDER BY n_killed::numeric / n_accidents DESC) AS rank_death_rate
FROM by_day
ORDER BY day_of_week;

-- Q1.c By month, with yearly subtotals and a grand total (ROLLUP), COVID year flagged.
SELECT
    d.year,
    d.month,
    COUNT(*)                                     AS n_accidents,
    SUM(f.n_killed)                              AS n_killed,
    safe_rate(SUM(f.n_killed), COUNT(*), COUNT(*)) AS killed_per_100_accidents,
    CASE WHEN GROUPING(d.year) = 1 THEN 'Total'
         WHEN GROUPING(d.month) = 1 THEN 'Sous-total année'
         ELSE 'Mois' END                         AS level,
    bool_or(d.is_covid_year)                     AS covid_year
FROM fact_accident f
JOIN dim_date d USING (date_key)
GROUP BY ROLLUP (d.year, d.month)
ORDER BY d.year NULLS LAST, d.month NULLS LAST;

-- Q1.d Night vs day: time band x lighting (night = light codes 3-5). Are night accidents deadlier?
SELECT
    t.time_band,
    CASE WHEN c.night THEN 'Nuit (éclairage)' WHEN NOT c.night THEN 'Jour / crépuscule' END AS lighting,
    COUNT(*)                                          AS n_accidents,
    SUM(f.n_killed)                                   AS n_killed,
    COUNT(*) FILTER (WHERE f.fatal)                   AS n_fatal_accidents,
    safe_rate(SUM(f.n_killed), COUNT(*), COUNT(*))    AS killed_per_100_accidents,
    safe_rate(COUNT(*) FILTER (WHERE f.fatal), COUNT(*), COUNT(*)) AS pct_fatal_accidents
FROM fact_accident f
JOIN dim_time_band t USING (hour)
JOIN dim_conditions c USING (conditions_key)
WHERE c.night IS NOT NULL
GROUP BY GROUPING SETS ((t.time_band_order, t.time_band), (c.night), (t.time_band_order, t.time_band, c.night))
ORDER BY t.time_band_order NULLS LAST, c.night NULLS FIRST;

-- =============================================================================================
-- Q2. WHERE - rates per 100,000 inhabitants by department, death rate per accident, in-town vs
--     out-of-town, focus city.
-- =============================================================================================

-- Q2.a Departments ranked by deaths per 100,000 inhabitants (yearly average 2019-latest year).
--      Departments below the accident threshold get no rate and therefore no rank.
WITH dep AS (
    SELECT p.dep_code, p.dep_name, p.region_name, p.population,
           COUNT(*) AS n_accidents, SUM(f.n_killed) AS n_killed,
           COUNT(DISTINCT f.year) AS n_years
    FROM fact_accident f
    JOIN dim_population p USING (dep_code)
    GROUP BY p.dep_code, p.dep_name, p.region_name, p.population
),
rates AS (
    SELECT dep.*,
           safe_rate(n_killed::numeric / n_years, population, n_accidents, 100000)    AS killed_per_100k_per_year,
           safe_rate(n_accidents::numeric / n_years, population, n_accidents, 100000) AS accidents_per_100k_per_year,
           safe_rate(n_killed, n_accidents, n_accidents)                              AS killed_per_100_accidents
    FROM dep
)
SELECT
    dep_code, dep_name, region_name, population, n_accidents, n_killed,
    killed_per_100k_per_year, accidents_per_100k_per_year, killed_per_100_accidents,
    CASE WHEN killed_per_100k_per_year IS NOT NULL
         THEN RANK() OVER (ORDER BY killed_per_100k_per_year DESC NULLS LAST) END AS rank_killed_per_100k,
    CASE WHEN killed_per_100_accidents IS NOT NULL
         THEN RANK() OVER (ORDER BY killed_per_100_accidents DESC NULLS LAST) END AS rank_death_rate
FROM rates
ORDER BY rank_killed_per_100k NULLS LAST, dep_code;

-- Q2.b In-town vs out-of-town, by road category, with subtotals (GROUPING SETS).
SELECT
    COALESCE(l.in_town_label, 'Total')            AS localisation,
    COALESCE(r.catr_label, 'Toutes routes')       AS road_category,
    COUNT(*)                                      AS n_accidents,
    SUM(f.n_killed)                               AS n_killed,
    safe_rate(SUM(f.n_killed), COUNT(*), COUNT(*)) AS killed_per_100_accidents,
    ROUND(100.0 * SUM(f.n_killed) / SUM(SUM(f.n_killed)) OVER (PARTITION BY GROUPING(l.in_town_label), GROUPING(r.catr_label)), 2) AS pct_of_deaths
FROM fact_accident f
JOIN dim_location l USING (location_key)
JOIN dim_road r USING (road_key)
WHERE l.in_town IS NOT NULL
GROUP BY GROUPING SETS ((l.in_town_label), (l.in_town_label, r.catr_label), ())
ORDER BY GROUPING(l.in_town_label), l.in_town_label, killed_per_100_accidents DESC NULLS LAST;

-- Q2.c Regions with a regional subtotal of their departments (ROLLUP), departments with a population.
WITH dep AS (
    SELECT p.region_name, p.dep_name, p.population,
           COUNT(*) AS n_accidents, SUM(f.n_killed) AS n_killed, COUNT(DISTINCT f.year) AS n_years
    FROM fact_accident f
    JOIN dim_population p USING (dep_code)
    WHERE p.population IS NOT NULL
    GROUP BY p.region_name, p.dep_name, p.population
)
SELECT
    COALESCE(region_name, 'France (départements avec population)') AS region,
    COALESCE(dep_name, 'Sous-total')                               AS department,
    SUM(n_accidents)                                AS n_accidents,
    SUM(n_killed)                                   AS n_killed,
    SUM(population)                                 AS population,
    safe_rate(SUM(n_killed) / MAX(n_years), SUM(population), SUM(n_accidents), 100000) AS killed_per_100k_per_year,
    safe_rate(SUM(n_killed), SUM(n_accidents), SUM(n_accidents))                       AS killed_per_100_accidents
FROM dep
GROUP BY ROLLUP (region_name, dep_name)
ORDER BY region_name NULLS LAST, dep_name NULLS LAST;

-- Q2.d Focus city (Toulouse, INSEE 31555): accidents and deaths per year, share precisely located.
SELECT
    f.year,
    COUNT(*)                                        AS n_accidents,
    SUM(f.n_killed)                                 AS n_killed,
    COUNT(*) FILTER (WHERE f.pedestrian_involved)   AS n_with_pedestrian,
    COUNT(*) FILTER (WHERE f.two_wheeler_involved)  AS n_with_two_wheeler,
    ROUND(100.0 * COUNT(*) FILTER (WHERE f.coord_precise) / COUNT(*), 1) AS pct_precise_coordinates
FROM fact_accident f
JOIN dim_location l USING (location_key)
WHERE l.com_code = '31555'
GROUP BY f.year
ORDER BY f.year;

-- =============================================================================================
-- Q3. CONDITIONS - severity by light, weather, surface, road category, speed limit, layout.
-- =============================================================================================

-- Q3.a One long table: factor / modality / accidents / deaths / death rate, ranked within factor.
WITH long AS (
    SELECT 'Luminosité' AS factor, c.lum_label AS modality, f.n_killed, f.fatal
    FROM fact_accident f JOIN dim_conditions c USING (conditions_key) WHERE c.lum_label IS NOT NULL
    UNION ALL
    SELECT 'Météo', c.atm_label, f.n_killed, f.fatal
    FROM fact_accident f JOIN dim_conditions c USING (conditions_key) WHERE c.atm_label IS NOT NULL
    UNION ALL
    SELECT 'Surface', c.surf_label, f.n_killed, f.fatal
    FROM fact_accident f JOIN dim_conditions c USING (conditions_key) WHERE c.surf_label IS NOT NULL
    UNION ALL
    SELECT 'Catégorie de route', r.catr_label, f.n_killed, f.fatal
    FROM fact_accident f JOIN dim_road r USING (road_key) WHERE r.catr_label IS NOT NULL
    UNION ALL
    SELECT 'Vitesse maximale autorisée', r.vma_band, f.n_killed, f.fatal
    FROM fact_accident f JOIN dim_road r USING (road_key) WHERE r.vma_band IS NOT NULL
    UNION ALL
    SELECT 'Tracé', r.plan_label, f.n_killed, f.fatal
    FROM fact_accident f JOIN dim_road r USING (road_key) WHERE r.plan_label IS NOT NULL
    UNION ALL
    SELECT 'Intersection', r.intersection_label, f.n_killed, f.fatal
    FROM fact_accident f JOIN dim_road r USING (road_key) WHERE r.intersection_label IS NOT NULL
)
SELECT
    factor, modality,
    COUNT(*)                                         AS n_accidents,
    SUM(n_killed)                                    AS n_killed,
    safe_rate(SUM(n_killed), COUNT(*), COUNT(*))     AS killed_per_100_accidents,
    safe_rate(COUNT(*) FILTER (WHERE fatal), COUNT(*), COUNT(*)) AS pct_fatal_accidents,
    RANK() OVER (PARTITION BY factor ORDER BY SUM(n_killed)::numeric / COUNT(*) DESC) AS rank_in_factor
FROM long
GROUP BY factor, modality
ORDER BY factor, rank_in_factor;

-- Q3.b Speed limit x in-town: death rate matrix (conditional aggregation with FILTER).
SELECT
    r.vma_band,
    COUNT(*) FILTER (WHERE f.in_town)          AS n_acc_in_town,
    COUNT(*) FILTER (WHERE NOT f.in_town)      AS n_acc_out_of_town,
    safe_rate(SUM(f.n_killed) FILTER (WHERE f.in_town), COUNT(*) FILTER (WHERE f.in_town),
              COUNT(*) FILTER (WHERE f.in_town))         AS killed_per_100_in_town,
    safe_rate(SUM(f.n_killed) FILTER (WHERE NOT f.in_town), COUNT(*) FILTER (WHERE NOT f.in_town),
              COUNT(*) FILTER (WHERE NOT f.in_town))     AS killed_per_100_out_of_town
FROM fact_accident f
JOIN dim_road r USING (road_key)
WHERE r.vma_band IS NOT NULL
GROUP BY r.vma_band_order, r.vma_band
ORDER BY r.vma_band_order;

-- =============================================================================================
-- Q4. WHO - victims by user type, travel mode, age band and sex; effect of safety equipment.
-- =============================================================================================

-- Q4.a Persons involved and killed by travel mode; share killed among persons involved.
SELECT
    u.user_mode,
    COUNT(*)                                        AS n_persons,
    SUM(v.killed)                                   AS n_killed,
    SUM(v.hospitalized)                             AS n_hospitalized,
    COUNT(DISTINCT v.accident_id)                   AS n_accidents,
    safe_rate(SUM(v.killed), COUNT(*), COUNT(DISTINCT v.accident_id)) AS pct_killed,
    ROUND(100.0 * SUM(v.killed) / SUM(SUM(v.killed)) OVER (), 2)      AS pct_of_all_deaths
FROM fact_victim v
JOIN dim_user_type u USING (user_type_key)
WHERE u.user_mode IS NOT NULL
GROUP BY u.user_mode
ORDER BY n_killed DESC;

-- Q4.b Killed by age band and sex (persons with known age and sex).
SELECT
    v.age_band, v.sex,
    COUNT(*)            AS n_persons,
    SUM(v.killed)       AS n_killed,
    safe_rate(SUM(v.killed), COUNT(*), COUNT(DISTINCT v.accident_id)) AS pct_killed
FROM fact_victim v
WHERE v.age_band IS NOT NULL AND v.sex IS NOT NULL
GROUP BY v.age_band_order, v.age_band, v.sex
ORDER BY v.age_band_order, v.sex;

-- Q4.c Safety equipment among comparable users: share killed or hospitalized.
--      Car occupants (seatbelt) and motorcycle / moped riders (helmet), equipment known.
SELECT
    CASE WHEN u.user_mode = 'Voiture (VL)' THEN 'Occupants de voiture'
         ELSE 'Conducteurs / passagers de 2RM' END AS population,
    CASE WHEN u.user_mode = 'Voiture (VL)' THEN 'Ceinture' ELSE 'Casque' END AS equipment,
    CASE WHEN (u.user_mode = 'Voiture (VL)' AND v.seatbelt_worn)
           OR (u.user_mode <> 'Voiture (VL)' AND v.helmet_worn) THEN 'Porté' ELSE 'Non porté' END AS worn,
    COUNT(*)                                                     AS n_persons,
    SUM(v.killed)                                                AS n_killed,
    safe_rate(SUM(v.killed), COUNT(*), COUNT(DISTINCT v.accident_id))                  AS pct_killed,
    safe_rate(SUM(v.killed + v.hospitalized), COUNT(*), COUNT(DISTINCT v.accident_id)) AS pct_killed_or_hospitalized
FROM fact_victim v
JOIN dim_user_type u USING (user_type_key)
WHERE v.equipment_known
  AND v.grav IS NOT NULL
  AND u.catu IN (1, 2)
  AND u.user_mode IN ('Voiture (VL)', 'Moto > 125 cm3', 'Moto 50-125 cm3', 'Cyclomoteur <= 50 cm3')
GROUP BY 1, 2, 3
ORDER BY 1, 3;

-- =============================================================================================
-- Q5. SEVERITY FACTORS - combinations of conditions with the highest share of fatal accidents
--     (descriptive; the multivariate model is in src/crashmap/model.py).
-- =============================================================================================
WITH combos AS (
    SELECT
        CASE WHEN f.in_town THEN 'En agglo' ELSE 'Hors agglo' END            AS localisation,
        CASE WHEN c.night THEN 'Nuit' ELSE 'Jour' END                        AS lighting,
        CASE WHEN f.pedestrian_involved THEN 'Piéton'
             WHEN f.motorised_two_wheeler_involved THEN '2RM'
             WHEN f.bicycle_involved OR f.personal_mobility_involved THEN 'Vélo / EDP'
             ELSE 'Véhicules seuls' END                                      AS users,
        CASE WHEN f.n_vehicles = 1 THEN '1 véhicule' ELSE '2 véhicules et +' END AS vehicles,
        f.fatal, f.n_killed
    FROM fact_accident f
    JOIN dim_conditions c USING (conditions_key)
    WHERE f.in_town IS NOT NULL AND c.night IS NOT NULL
)
SELECT
    localisation, lighting, users, vehicles,
    COUNT(*)                                       AS n_accidents,
    SUM(n_killed)                                  AS n_killed,
    safe_rate(COUNT(*) FILTER (WHERE fatal), COUNT(*), COUNT(*)) AS pct_fatal_accidents,
    DENSE_RANK() OVER (ORDER BY COUNT(*) FILTER (WHERE fatal)::numeric / COUNT(*) DESC) AS rank_fatal_share
FROM combos
GROUP BY localisation, lighting, users, vehicles
HAVING COUNT(*) >= (SELECT param_value FROM analysis_params WHERE param_name = 'min_accidents')
ORDER BY rank_fatal_share
LIMIT 15;

-- =============================================================================================
-- Q6. TREND - 2019 to latest year, year-over-year change (LAG), change vs 2019, COVID flagged.
-- =============================================================================================

-- Q6.a Yearly KPIs with LAG and change vs the 2019 baseline.
SELECT
    year,
    n_accidents,
    n_killed,
    killed_per_100_accidents,
    LAG(n_killed) OVER (ORDER BY year)                                   AS n_killed_prev_year,
    ROUND(100.0 * (n_killed - LAG(n_killed) OVER (ORDER BY year))
          / LAG(n_killed) OVER (ORDER BY year), 1)                       AS pct_change_killed_yoy,
    ROUND(100.0 * (n_accidents - LAG(n_accidents) OVER (ORDER BY year))
          / LAG(n_accidents) OVER (ORDER BY year), 1)                    AS pct_change_accidents_yoy,
    ROUND(100.0 * (n_killed - FIRST_VALUE(n_killed) OVER (ORDER BY year))
          / FIRST_VALUE(n_killed) OVER (ORDER BY year), 1)               AS pct_change_killed_vs_2019,
    covid_year
FROM v_kpi_year
ORDER BY year;

-- Q6.b Monthly deaths with a 12-month rolling average (smooths seasonality and the 2020 lockdowns).
WITH monthly AS (
    SELECT d.year_month, bool_or(d.is_covid_year) AS covid_year,
           COUNT(*) AS n_accidents, SUM(f.n_killed) AS n_killed
    FROM fact_accident f
    JOIN dim_date d USING (date_key)
    GROUP BY d.year_month
)
SELECT
    year_month, n_accidents, n_killed, covid_year,
    ROUND(AVG(n_killed) OVER (ORDER BY year_month ROWS BETWEEN 11 PRECEDING AND CURRENT ROW), 1) AS killed_rolling_12m,
    COUNT(*) OVER (ORDER BY year_month ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)               AS months_in_window
FROM monthly
ORDER BY year_month;

-- Q6.c Trend by travel mode: deaths per year and change latest year vs 2019 (2020 excluded as an anomaly).
WITH by_mode AS (
    SELECT u.user_mode, a.year, SUM(v.killed) AS n_killed
    FROM fact_victim v
    JOIN dim_user_type u USING (user_type_key)
    JOIN fact_accident a USING (accident_id)
    WHERE u.user_mode IS NOT NULL
    GROUP BY u.user_mode, a.year
)
SELECT
    user_mode,
    SUM(n_killed) FILTER (WHERE year = 2019)                      AS killed_2019,
    SUM(n_killed) FILTER (WHERE year = 2020)                      AS killed_2020_covid,
    SUM(n_killed) FILTER (WHERE year = (SELECT MAX(year) FROM fact_accident)) AS killed_latest,
    ROUND(100.0 * (SUM(n_killed) FILTER (WHERE year = (SELECT MAX(year) FROM fact_accident))
                   - SUM(n_killed) FILTER (WHERE year = 2019))
          / NULLIF(SUM(n_killed) FILTER (WHERE year = 2019), 0), 1) AS pct_change_vs_2019
FROM by_mode
GROUP BY user_mode
HAVING SUM(n_killed) >= 30
ORDER BY killed_latest DESC NULLS LAST;

-- =============================================================================================
-- Q7. RECOMMENDATIONS - where, when and for whom deaths concentrate (share of all deaths).
-- =============================================================================================
WITH cube AS (
    SELECT
        CASE WHEN f.in_town THEN 'En agglomération' ELSE 'Hors agglomération' END AS localisation,
        t.time_band,
        u.user_mode,
        SUM(v.killed) AS n_killed
    FROM fact_victim v
    JOIN dim_user_type u USING (user_type_key)
    JOIN fact_accident f USING (accident_id)
    JOIN dim_time_band t USING (hour)
    WHERE f.in_town IS NOT NULL AND u.user_mode IS NOT NULL
    GROUP BY 1, 2, 3
)
SELECT
    localisation, time_band, user_mode, n_killed,
    ROUND(100.0 * n_killed / SUM(n_killed) OVER (), 2)                                   AS pct_of_deaths,
    ROUND(100.0 * SUM(n_killed) OVER (ORDER BY n_killed DESC
          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) / SUM(n_killed) OVER (), 1)   AS cumulative_pct
FROM cube
ORDER BY n_killed DESC
LIMIT 15;
