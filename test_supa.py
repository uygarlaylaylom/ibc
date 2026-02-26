from supabase_utils import get_supabase
try:
    supabase = get_supabase()
    print("Testing get_attachments query...")
    response = supabase.table("attachments").select("*").limit(1).execute()
    print("Success:", response.data)
except Exception as e:
    print(f"Error caught: {e}")
