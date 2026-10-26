-- CrashMap France - star schema (PostgreSQL 16)
-- Grain: fact_accident = 1 row per accident, fact_vehicle = 1 row per vehicle,
--        fact_victim = 1 row per person involved (including unhurt users).
-- Loaded by src/crashmap/load_postgres.py (python run.py load).

DROP SCHEMA IF EXISTS crashmap CASCADE;
CREATE SCHEMA crashmap;
SET search_path TO crashmap;

-- Analysis parameters (minimum number of accidents before a rate is shown)
CREATE TABLE analysis_params (
    param_name  text PRIMARY KEY,
    param_value integer NOT NULL
);

-- ----------------------------------------------------------------------------------------------
-- Dimensions
-- ----------------------------------------------------------------------------------------------

CREATE TABLE dim_date (
    date_key      integer PRIMARY KEY,          -- YYYYMMDD
    date          date    NOT NULL UNIQUE,
    year          smallint NOT NULL,
    quarter       smallint NOT NULL,
    month         smallint NOT NULL,
    month_name    text    NOT NULL,
    year_month    char(7) NOT NULL,
    day           smallint NOT NULL,
    day_of_week   smallint NOT NULL,            -- 1 = Monday ... 7 = Sunday
    weekday_name  text    NOT NULL,
    is_weekend    boolean NOT NULL,
    is_covid_year boolean NOT NULL
);

CREATE TABLE dim_time_band (
    hour            smallint PRIMARY KEY CHECK (hour BETWEEN 0 AND 23),
    hour_label      text NOT NULL,
    time_band       text NOT NULL,
    time_band_order smallint NOT NULL
);

-- Department-level population (INSEE populations de reference 2023)
CREATE TABLE dim_population (
    dep_code        text PRIMARY KEY,
    dep_name        text NOT NULL,
    region_code     text,
    region_name     text NOT NULL,
    zone            text NOT NULL,              -- Metropole / Outre-mer (DROM) / Outre-mer (COM)
    population      integer,                    -- NULL when INSEE has no legal population (976, 986-988)
    population_year smallint NOT NULL
);

-- Commune x in-town / out-of-town
CREATE TABLE dim_location (
    location_key   text PRIMARY KEY,            -- <commune code>-<A|H|X>
    com_code       text NOT NULL,
    com_name       text,
    com_population integer,
    dep_code       text NOT NULL REFERENCES dim_population (dep_code),
    dep_name       text,
    region_name    text,
    zone           text,
    in_town        boolean,
    in_town_label  text
);

-- Junk dimension: light x weather x road surface
CREATE TABLE dim_conditions (
    conditions_key integer PRIMARY KEY,
    lum            smallint,
    lum_label      text,
    atm            smallint,
    atm_label      text,
    surf           smallint,
    surf_label     text,
    night          boolean
);

-- Junk dimension: road category x speed limit band x layout (alignment, intersection)
CREATE TABLE dim_road (
    road_key           integer PRIMARY KEY,
    catr               smallint,
    catr_label         text,
    vma_band           text,
    vma_band_order     smallint,
    plan               smallint,
    plan_label         text,
    intersection       smallint,
    intersection_label text
);

CREATE TABLE dim_user_type (
    user_type_key integer PRIMARY KEY,
    catu          smallint NOT NULL,
    catu_label    text NOT NULL,
    user_mode     text                          -- travel mode: Pieton or vehicle group
);

CREATE TABLE dim_vehicle_type (
    catv                     smallint PRIMARY KEY,
    catv_label               text NOT NULL,
    vehicle_group            text NOT NULL,
    is_two_wheeler           boolean NOT NULL,
    is_motorised_two_wheeler boolean NOT NULL,
    is_bicycle               boolean NOT NULL,
    is_personal_mobility     boolean NOT NULL,
    is_heavy_vehicle         boolean NOT NULL
);

-- ----------------------------------------------------------------------------------------------
-- Facts
-- ----------------------------------------------------------------------------------------------

CREATE TABLE fact_accident (
    accident_id                    bigint PRIMARY KEY,
    date_key                       integer  NOT NULL REFERENCES dim_date (date_key),
    hour                           smallint REFERENCES dim_time_band (hour),
    location_key                   text     NOT NULL REFERENCES dim_location (location_key),
    dep_code                       text     NOT NULL REFERENCES dim_population (dep_code),
    conditions_key                 integer  NOT NULL REFERENCES dim_conditions (conditions_key),
    road_key                       integer  NOT NULL REFERENCES dim_road (road_key),
    year                           smallint NOT NULL,
    in_town                        boolean,
    vma                            smallint,
    collision_type                 text,
    n_vehicles                     smallint NOT NULL,
    n_users                        smallint NOT NULL,
    n_victims                      smallint NOT NULL,
    n_killed                       smallint NOT NULL,
    n_hospitalized                 smallint NOT NULL,
    n_lightly_injured              smallint NOT NULL,
    n_unhurt                       smallint NOT NULL,
    fatal                          boolean  NOT NULL,
    serious                        boolean  NOT NULL,
    pedestrian_involved            boolean  NOT NULL,
    two_wheeler_involved           boolean  NOT NULL,
    motorised_two_wheeler_involved boolean  NOT NULL,
    bicycle_involved               boolean  NOT NULL,
    personal_mobility_involved     boolean  NOT NULL,
    heavy_vehicle_involved         boolean  NOT NULL,
    lat                            double precision,
    lon                            double precision,
    coord_precise                  boolean  NOT NULL
);

CREATE TABLE fact_vehicle (
    vehicle_key       text PRIMARY KEY,
    accident_id       bigint NOT NULL REFERENCES fact_accident (accident_id),
    catv              smallint REFERENCES dim_vehicle_type (catv),
    fixed_obstacle    text,
    mobile_obstacle   text,
    impact_point      text,
    maneuver          text,
    engine            text,
    n_users           smallint NOT NULL,
    n_killed          smallint NOT NULL,
    n_hospitalized    smallint NOT NULL,
    n_lightly_injured smallint NOT NULL
);

CREATE TABLE fact_victim (
    victim_id       text PRIMARY KEY,
    accident_id     bigint   NOT NULL REFERENCES fact_accident (accident_id),
    vehicle_key     text     NOT NULL REFERENCES fact_vehicle (vehicle_key),
    user_type_key   integer  NOT NULL REFERENCES dim_user_type (user_type_key),
    catv            smallint REFERENCES dim_vehicle_type (catv),  -- vehicle occupied (or that hit the pedestrian)
    grav            smallint,
    severity        text,
    severity_order  smallint,
    killed          smallint NOT NULL,
    hospitalized    smallint NOT NULL,
    lightly_injured smallint NOT NULL,
    unhurt          smallint NOT NULL,
    sex             text,
    age             smallint,
    age_band        text,
    age_band_order  smallint,
    trip_purpose    text,
    equipment_known boolean  NOT NULL,
    seatbelt_worn   boolean,
    helmet_worn     boolean
);
