-- Migration: Add reading purchase and free month tracking fields
-- Run this migration to add support for $28 reading purchase and free month of chats

-- Add columns to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS has_purchased_reading BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS reading_purchase_date TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS free_chat_month_end_date TIMESTAMP;

-- Note: If using SQLite, you may need to recreate the table or use a migration tool
-- For PostgreSQL, the above ALTER TABLE statements should work

