import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

def get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Supabase credentials not found. Set SUPABASE_URL and SUPABASE_KEY in .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Companies ---

def get_companies(search_query="", visited_only=False, min_priority=1, has_notes=False, has_email=False):
    """
    Fetches filtered companies from Supabase.
    Note: 'has_notes' and 'has_email' require complex joins or a database view.
    For simplicity in this prototype, we fetch companies and do minor filtering in memory or via basic eq/ilike.
    """
    supabase = get_supabase()
    
    query = supabase.table("companies").select("*")
    
    if visited_only:
        query = query.eq("visited", True)
    
    if min_priority > 1:
        query = query.gte("priority", min_priority)
        
    if search_query:
        # Supabase ilike doesn't support OR natively in python client easily without or_ syntax
        # Using the restful 'or' filter:
        query = query.or_(f"booth_number.ilike.%{search_query}%,company_name.ilike.%{search_query}%,primary_domain.ilike.%{search_query}%,segment.ilike.%{search_query}%")

    response = query.order("priority", desc=True).order("company_name").execute()
    companies = response.data
    
    # Optional: If has_notes or has_email is checked, we would need to filter these IDs.
    # In a production app, we should use a SQL View for performance.
    # Here, we do a quick second query if requested.
    if has_notes or has_email:
        notes_query = supabase.table("notes").select("company_id, type").execute()
        notes_data = notes_query.data
        
        valid_company_ids = set()
        for n in notes_data:
            if has_notes and n['type'] == 'manual':
                valid_company_ids.add(n['company_id'])
            if has_email and n['type'] == 'email':
                valid_company_ids.add(n['company_id'])
                
        companies = [c for c in companies if c['id'] in valid_company_ids]
        
    return companies

def update_company(company_id, visited=None, priority=None, tags=None, products=None):
    """Updates a company's visited status, priority, tags, or products."""
    supabase = get_supabase()
    data = {}
    if visited is not None:
        data["visited"] = visited
    if priority is not None:
        data["priority"] = priority
    if tags is not None:
        data["tags"] = tags
    if products is not None:
        data["products"] = products
        
    if data:
        try:
            supabase.table("companies").update(data).eq("id", company_id).execute()
        except dict as e:
            print("Error updating:", e)

# --- Notes ---

def get_notes(company_id):
    """Fetches notes for a specific company."""
    supabase = get_supabase()
    response = supabase.table("notes").select("*").eq("company_id", company_id).order("created_at", desc=True).execute()
    return response.data

def add_note(company_id, content, note_type="manual"):
    """Adds a new note."""
    if not content.strip():
        return
    supabase = get_supabase()
    data = {
        "company_id": company_id,
        "type": note_type,
        "content": content
    }
    supabase.table("notes").insert(data).execute()

def delete_note(note_id):
    """Deletes a specific note."""
    supabase = get_supabase()
    supabase.table("notes").delete().eq("id", note_id).execute()

# --- Attachments ---

def get_attachments(company_id):
    """Fetches attachments for a specific company."""
    supabase = get_supabase()
    response = supabase.table("attachments").select("*").eq("company_id", company_id).order("created_at", desc=True).execute()
    return response.data

def upload_attachment(company_id, file_bytes=None, file_name="", file_type="image", source="supabase"):
    """
    Uploads a file to Supabase Storage (if source=='supabase') AND records it in attachments table.
    If source=='gdrive', file_name is treated as the Google Drive link and bytes are ignored.
    """
    supabase = get_supabase()
    
    if source == "supabase":
        # Path: company_id/file_name
        storage_path = f"{company_id}/{file_name}"
        
        # Upload to bucket Ensure 'attachments' bucket exists and is public
        try:
            supabase.storage.from_("attachments").upload(
                path=storage_path, 
                file=file_bytes, 
                file_options={"content-type": "application/octet-stream"}
            )
        except Exception as e:
            print(f"File upload error (may already exist): {e}")
    else:
        # GDrive: the file_name parameter holds the URL
        storage_path = file_name

    # Save to table
    data = {
        "company_id": company_id,
        "file_path": storage_path,
        "file_type": file_type
    }
    supabase.table("attachments").insert(data).execute()

def get_public_url(file_path):
    """Gets the public URL for an attachment (handles both Supabase and GDrive)."""
    if file_path.startswith("http"):
        return file_path
    supabase = get_supabase()
    return supabase.storage.from_("attachments").get_public_url(file_path)

# --- Contacts ---

def get_contacts(company_id):
    """Fetches contacts for a specific company."""
    supabase = get_supabase()
    response = supabase.table("contacts").select("*").eq("company_id", company_id).order("created_at", desc=False).execute()
    return response.data

def add_contact(company_id, name, title=None, email=None, phone=None, notes=None):
    """Adds a new contact to a company."""
    if not name.strip():
        return
    supabase = get_supabase()
    data = {
        "company_id": company_id,
        "name": name,
        "title": title,
        "email": email,
        "phone": phone,
        "notes": notes
    }
    supabase.table("contacts").insert(data).execute()

def update_contact(contact_id, name=None, title=None, email=None, phone=None, notes=None):
    """Updates an existing contact."""
    supabase = get_supabase()
    data = {}
    if name is not None: data["name"] = name
    if title is not None: data["title"] = title
    if email is not None: data["email"] = email
    if phone is not None: data["phone"] = phone
    if notes is not None: data["notes"] = notes
    
    if data:
        supabase.table("contacts").update(data).eq("id", contact_id).execute()

def delete_contact(contact_id):
    """Deletes a contact."""
    supabase = get_supabase()
    supabase.table("contacts").delete().eq("id", contact_id).execute()

