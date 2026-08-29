-- Dimension: Region
CREATE TABLE dim_region (
    region_id SERIAL PRIMARY KEY,
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    UNIQUE(city, state, country)
);

-- Dimension: Category
CREATE TABLE dim_category (
    category_id SERIAL PRIMARY KEY,
    category_name VARCHAR(100) UNIQUE
);

-- Dimension: Date
CREATE TABLE dim_date (
    date_id SERIAL PRIMARY KEY,
    full_date DATE UNIQUE,
    day INT,
    month INT,
    quarter INT,
    year INT
);

-- Fact table: Sales
CREATE TABLE fact_sales (
    sale_id SERIAL PRIMARY KEY,
    order_id VARCHAR(50),
    date_id INT REFERENCES dim_date(date_id),
    region_id INT REFERENCES dim_region(region_id),
    category_id INT REFERENCES dim_category(category_id),
    status VARCHAR(50),
    sales_channel VARCHAR(50),
    qty INT,
    amount NUMERIC(10,2),
    b2b BOOLEAN
);