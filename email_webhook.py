from fastapi import FastAPI, Request, HTTPException
import os
import re
from supabase import create_client, Client
from dotenv import load_dotenv

# Load env variables
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "my_secret_key_123") # For basic auth if needed

app = FastAPI()

def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def extract_domain(email_string: str) -> str:
    """Extracts domain from an email address string (e.g. 'john@vosker.com' -> 'vosker.com')."""
    match = re.search(r'@([\w.-]+)', email_string)
    if match:
        domain = match.group(1).lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    return None

@app.post("/webhook/email")
async def receive_email(request: Request):
    """
    Webhook endpoint to receive forwarded emails.
    Assuming the payload comes from a service like Zapier, Make, or SendGrid Inbound Parse.
    """
    # 1. Parse JSON Payload
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Adapt these fields based on the actual webhook provider you use (e.g. Zapier)
    sender_email = data.get("sender", "") or data.get("from", "")
    subject = data.get("subject", "")
    body_text = data.get("text", "") or data.get("body", "")

    if not sender_email or not body_text:
        return {"status": "ignored", "reason": "Missing sender or body"}

    # 2. Extract Domain
    domain = extract_domain(sender_email)
    if not domain:
         return {"status": "ignored", "reason": "Could not parse domain"}

    supabase = get_supabase()

    # 3. Match Domain to Company
    # Use ILIKE or EQ depending on how primary_domain is stored
    response = supabase.table("companies").select("id, company_name").eq("primary_domain", domain).execute()
    
    companies = response.data
    if not companies:
        return {"status": "ignored", "reason": f"No company found matching domain: {domain}"}
    
    # Assuming first match is correct (in reality, might need more robust matching if multiple companies share a domain)
    company_id = companies[0]['id']
    company_name = companies[0]['company_name']

    # 4. Insert Note
    note_content = f"Subject: {subject}\n\n{body_text}"
    
    insert_data = {
        "company_id": company_id,
        "type": "email",
        "content": note_content
    }
    
    try:
        supabase.table("notes").insert(insert_data).execute()
        return {"status": "success", "matched_company": company_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# To run locally: uvicorn email_webhook:app --reload
