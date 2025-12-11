-- Fix admin_bypass_logs sequence after migration
-- Run this in Supabase SQL Editor if you get duplicate key errors

-- Reset the sequence to the maximum ID + 1
SELECT setval(
    'admin_bypass_logs_id_seq',
    COALESCE((SELECT MAX(id) FROM admin_bypass_logs), 0) + 1,
    false
);

-- Verify the sequence is correct
SELECT currval('admin_bypass_logs_id_seq') as current_sequence_value;
SELECT MAX(id) as max_id FROM admin_bypass_logs;

