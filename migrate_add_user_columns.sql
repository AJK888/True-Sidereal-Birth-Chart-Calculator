-- Migration: Add is_admin and credits columns to users table
-- Run this in your PostgreSQL database (Render dashboard or psql)

-- Add is_admin column (default false)
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;

-- Add credits column (default 3 free credits for new users)
ALTER TABLE users ADD COLUMN IF NOT EXISTS credits INTEGER DEFAULT 3;

-- Also add the credit_transactions table if it doesn't exist
CREATE TABLE IF NOT EXISTS credit_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    stripe_payment_id VARCHAR(255),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add tokens_used and credits_charged to chat_messages if they don't exist
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS tokens_used INTEGER;
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS credits_charged INTEGER DEFAULT 1;

-- Verify the changes
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'users';

