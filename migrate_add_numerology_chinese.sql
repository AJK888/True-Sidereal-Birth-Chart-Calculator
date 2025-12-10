-- Migration: Add numerology and Chinese zodiac fields to famous_people table
-- Run this before running calculate_famous_people_charts.py

-- Add numerology columns
ALTER TABLE famous_people ADD COLUMN life_path_number VARCHAR(10);
ALTER TABLE famous_people ADD COLUMN day_number VARCHAR(10);

-- Add Chinese zodiac columns
ALTER TABLE famous_people ADD COLUMN chinese_zodiac_animal VARCHAR(50);
ALTER TABLE famous_people ADD COLUMN chinese_zodiac_element VARCHAR(50);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_famous_people_life_path ON famous_people(life_path_number);
CREATE INDEX IF NOT EXISTS idx_famous_people_chinese_animal ON famous_people(chinese_zodiac_animal);

