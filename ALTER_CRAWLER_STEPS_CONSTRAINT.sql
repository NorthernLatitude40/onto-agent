-- Migration script to add 'playwright' as a valid target_type value
-- This updates the check constraint on crawler_steps table

-- First, drop the existing constraint
ALTER TABLE crawler_steps 
DROP CONSTRAINT IF EXISTS crawler_steps_target_type_check;

-- Then recreate it with the new allowed values
ALTER TABLE crawler_steps 
ADD CONSTRAINT crawler_steps_target_type_check 
CHECK (target_type IN ('api', 'html', 'unstructured', 'playwright'));
