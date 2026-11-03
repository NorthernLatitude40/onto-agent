-- Migration script for adding configurable parameters to scraper_configs table
-- This script adds new columns to support configurable scraping parameters
-- instead of hardcoded values in the _scrape_with_requests method

-- Add default_params column for storing default request parameters as JSON
ALTER TABLE scraper_configs 
ADD COLUMN IF NOT EXISTS default_params JSON;

-- Add sort_order column with default value matching current hardcoded behavior
ALTER TABLE scraper_configs 
ADD COLUMN IF NOT EXISTS sort_order VARCHAR(50) DEFAULT 'price_asc';

-- Add page_size column with default value matching current hardcoded behavior
ALTER TABLE scraper_configs 
ADD COLUMN IF NOT EXISTS page_size INTEGER DEFAULT 9999;

-- Add vehicle_type column with default value matching current hardcoded behavior
ALTER TABLE scraper_configs 
ADD COLUMN IF NOT EXISTS vehicle_type VARCHAR(100) DEFAULT 'campervan';

-- Optional: Update existing configurations to use the new defaults
-- This ensures backward compatibility and consistent behavior
-- UPDATE scraper_configs SET sort_order = 'price_asc' WHERE sort_order IS NULL;
-- UPDATE scraper_configs SET page_size = 9999 WHERE page_size IS NULL;
-- UPDATE scraper_configs SET vehicle_type = 'campervan' WHERE vehicle_type IS NULL;

-- Migration for enhancing steps field to support full API request configuration
ALTER TABLE scraper_configs
ADD COLUMN IF NOT EXISTS steps JSON;
