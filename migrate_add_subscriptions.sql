-- Migration: Add subscription fields and tables
-- Run this in your PostgreSQL database (Render dashboard or psql)

-- Add subscription columns to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(50) DEFAULT 'inactive';
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_start_date TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_end_date TIMESTAMP;

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_stripe_customer_id ON users(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_users_stripe_subscription_id ON users(stripe_subscription_id);
CREATE INDEX IF NOT EXISTS idx_users_subscription_status ON users(subscription_status);

-- Create subscription_payments table
CREATE TABLE IF NOT EXISTS subscription_payments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    stripe_payment_intent_id VARCHAR(255),
    stripe_invoice_id VARCHAR(255),
    amount INTEGER NOT NULL,
    currency VARCHAR(10) DEFAULT 'usd',
    status VARCHAR(50) NOT NULL,
    payment_date TIMESTAMP NOT NULL,
    billing_period_start TIMESTAMP,
    billing_period_end TIMESTAMP,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for subscription_payments
CREATE INDEX IF NOT EXISTS idx_subscription_payments_user_id ON subscription_payments(user_id);
CREATE INDEX IF NOT EXISTS idx_subscription_payments_payment_intent ON subscription_payments(stripe_payment_intent_id);
CREATE INDEX IF NOT EXISTS idx_subscription_payments_invoice ON subscription_payments(stripe_invoice_id);

-- Create admin_bypass_logs table
CREATE TABLE IF NOT EXISTS admin_bypass_logs (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255),
    endpoint VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT
);

-- Create index for admin_bypass_logs
CREATE INDEX IF NOT EXISTS idx_admin_bypass_logs_timestamp ON admin_bypass_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_admin_bypass_logs_user_email ON admin_bypass_logs(user_email);

-- Verify the changes
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'users' AND column_name LIKE '%subscription%';

