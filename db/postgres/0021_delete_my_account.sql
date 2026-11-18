-- "Delete everything" removes the login too (docs/decisions.md, 2026-11-18, security review M4).
-- Before, the browser deleted the profile row and the login (auth.users, with the email) stayed.
-- This function deletes only the caller's own login; ON DELETE CASCADE then removes the profile
-- (students), and from it the chats, connections, fit checks and tailored resumes. The email-reveal
-- log stays with the person's id cleared (0020), and usage_events keeps its 48-hour counts by email
-- hash (H1). The resume PDF is removed by the browser first, through the Storage API: Supabase
-- refuses SQL deletes on storage tables.
--
-- SECURITY DEFINER because the authenticated role can't touch auth.users. It acts on auth.uid()
-- only, takes no arguments, and pins search_path so no other schema's objects can stand in.
CREATE FUNCTION public.delete_my_account() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE
  me uuid := auth.uid();
BEGIN
  IF me IS NULL THEN
    RAISE EXCEPTION 'not signed in' USING ERRCODE = '42501';
  END IF;
  DELETE FROM auth.users WHERE id = me;
END;
$$;

REVOKE ALL ON FUNCTION public.delete_my_account() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.delete_my_account() TO authenticated;
