-- A profile's "work you want" takes any of the 14 job categories (docs/decisions.md, 2026-11-15),
-- not only the three roles Shrey targets. The old three (ai_ml, backend, mobile) are category keys
-- too, so every saved profile stays valid. Keep this list in step with config/role_families.yaml
-- and site/src/lib/describe.ts (CATEGORY); tests/test_rls.py checks the two match.
ALTER TABLE students DROP CONSTRAINT students_target_roles_check;
ALTER TABLE students ADD CONSTRAINT students_target_roles_check CHECK (
  target_roles <@ ARRAY['ai_ml', 'security', 'qa', 'data', 'other', 'design', 'hardware', 'mobile',
                        'devops', 'fullstack', 'frontend', 'backend', 'product', 'software']
  AND cardinality(target_roles) <= 14
);
