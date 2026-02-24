import streamlit as st
import pandas as pd
from PIL import Image
import io
import datetime
from supabase_utils import (
    get_companies, update_company, get_notes, add_note, delete_note,
    get_attachments, upload_attachment, get_public_url
)

# --- Configuration ---
st.set_page_config(page_title="IBS 2026 Booth Tracker", page_icon="🏢", layout="wide")

# Custom CSS for modern look
st.markdown("""
<style>
    .reportview-container { background: #f0f2f6; }
    .company-card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px;}
    .company-card h3 { color: #111; }
    .company-card p { color: #222; font-size: 1.05em; }
    .booth-badge { background-color: #ff4b4b; color: white; padding: 5px 10px; border-radius: 5px; font-weight: bold; }
    .note-box { background-color: #f8f9fa; border-left: 4px solid #4CAF50; padding: 10px; margin-bottom: 10px; border-radius: 4px; color: #111;}
    .email-box { background-color: #e3f2fd; border-left: 4px solid #2196F3; padding: 10px; margin-bottom: 10px; border-radius: 4px; color: #111;}
    .delete-btn-container { text-align: right; }
</style>
""", unsafe_allow_html=True)

# --- Helper Functions ---
def compress_image(uploaded_file, max_size_kb=500):
    """Compresses an uploaded image using PIL."""
    try:
        img = Image.open(uploaded_file)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        output = io.BytesIO()
        # Initial save at 85% quality
        img.save(output, format="JPEG", quality=85, optimize=True)
        size_kb = len(output.getvalue()) / 1024
        
        quality = 85
        # Reduce quality if still too large
        while size_kb > max_size_kb and quality > 10:
            quality -= 10
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=quality, optimize=True)
            size_kb = len(output.getvalue()) / 1024
            
        return output.getvalue()
    except Exception as e:
        st.error(f"Error compressing image: {e}")
        return uploaded_file.getvalue()

# Pre-defined Tag Categories for Checkboxes
AVAILABLE_TAGS = [
    "Hot Prospect", "Distributor", "Manufacturer", "Service Provider",
    "Sent Catalog", "Needs Follow-up", "Innovator", "Competitor"
]

# --- Sidebar Filters ---
st.sidebar.title("🔍 Filters & Search")
search_query = st.sidebar.text_input("Search (Booth, Name, Segment...)", "")

st.sidebar.markdown("### Status Filters")
visited_only = st.sidebar.checkbox("✅ Visited Only", False)
min_priority = st.sidebar.slider("🔥 Minimum Priority (1-5)", min_value=1, max_value=5, value=1)

st.sidebar.markdown("### Content Filters")
has_notes = st.sidebar.checkbox("📝 Has Manual Notes", False)
has_email = st.sidebar.checkbox("📧 Received Email", False)

st.sidebar.markdown("---")
st.sidebar.info("Upload marketing emails via the Webhook or add them directly here.")

# --- Fetch Data ---
try:
    with st.spinner("Loading companies..."):
        companies = get_companies(
            search_query=search_query,
            visited_only=visited_only,
            min_priority=min_priority,
            has_notes=has_notes,
            has_email=has_email
        )
except Exception as e:
    st.error("Error connecting to database. Please check your .env credentials.")
    st.stop()

# --- Main Dashboard ---
st.title("🏢 IBS 2026 Booth Tracker")

if not companies:
    st.warning("No companies found matching your filters.")
else:
    st.success(f"Showing {len(companies)} companies.")
    
    # We use an expander list to avoid overwhelming the UI
    for idx, comp in enumerate(companies[:50]):  # Limit to 50 for performance to avoid slow renders
        with st.expander(f"{comp['booth_number']} - {comp['company_name']} {'✅' if comp['visited'] else ''}"):
            st.markdown(f"""
            <div class="company-card">
                <h3>{comp['company_name']} <span class="booth-badge">{comp['booth_number']}</span></h3>
                <p><strong>Segment:</strong> {comp['segment']}</p>
                <p><strong>Website:</strong> <a href="{comp['website']}" target="_blank">{comp['website']}</a></p>
                <p><i>{comp.get('description', 'No description available')}</i></p>
            </div>
            """, unsafe_allow_html=True)
            
            # Action Row: Visited & Priority & Tags
            col1, col2 = st.columns(2)
            with col1:
                is_visited = st.checkbox("Mark as Visited", value=comp['visited'], key=f"visit_{comp['id']}")
                if is_visited != comp['visited']:
                    update_company(comp['id'], visited=is_visited)
                    st.rerun()
                    
                new_priority = st.selectbox("Priority Level", [1, 2, 3, 4, 5], index=comp['priority']-1, key=f"prio_{comp['id']}")
                if new_priority != comp['priority']:
                    update_company(comp['id'], priority=new_priority)
                    st.rerun()
                    
            with col2:
                # Tags multi-select
                current_tags = comp.get('tags') or []
                selected_tags = st.multiselect("Company Categories / Tags", options=AVAILABLE_TAGS, default=current_tags, key=f"tags_{comp['id']}")
                if set(selected_tags) != set(current_tags):
                    update_company(comp['id'], tags=selected_tags)
                    st.rerun()
                    
            st.markdown("---")
            
            # Content Tabs
            tab1, tab2, tab3 = st.tabs(["📝 Notes", "📂 Attachments", "📧 History"])
            
            # TAB 1: Notes
            with tab1:
                new_note = st.text_area("Add a new note:", key=f"note_input_{comp['id']}")
                if st.button("Save Note", key=f"save_note_{comp['id']}"):
                    add_note(comp['id'], new_note, note_type="manual")
                    st.success("Note saved!")
                    st.rerun()
                
                notes = get_notes(comp['id'])
                for n in notes:
                    if n['type'] == 'manual':
                        date_str = datetime.datetime.fromisoformat(n['created_at'].replace('Z', '+00:00')).strftime("%Y-%m-%d %H:%M")
                        
                        col_note, col_del = st.columns([0.85, 0.15])
                        with col_note:
                            st.markdown(f"""
                            <div class="note-box">
                                <small style="color:#555;">{date_str}</small><br>
                                {n['content']}
                            </div>
                            """, unsafe_allow_html=True)
                        with col_del:
                            if st.button("🗑️ Delete", key=f"del_note_{n['id']}"):
                                delete_note(n['id'])
                                st.rerun()

            # TAB 2: Attachments
            with tab2:
                uploaded_file = st.file_uploader("Upload Business Card / Catalog (Image)", type=['png', 'jpg', 'jpeg'], key=f"file_{comp['id']}")
                if uploaded_file is not None:
                    if st.button("Compress & Upload", key=f"up_btn_{comp['id']}"):
                        with st.spinner("Processing..."):
                            compressed_bytes = compress_image(uploaded_file)
                            filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{uploaded_file.name}"
                            upload_attachment(comp['id'], compressed_bytes, filename, file_type="image")
                            st.success("Uploaded successfully!")
                            st.rerun()
                            
                attachments = get_attachments(comp['id'])
                if attachments:
                    st.write("**Saved Files:**")
                    cols = st.columns(3)
                    for i, att in enumerate(attachments):
                        url = get_public_url(att['file_path'])
                        with cols[i % 3]:
                            st.image(url, caption=att['file_path'].split('/')[-1], use_column_width=True)
                else:
                    st.info("No attachments yet.")

            # TAB 3: History / Emails
            with tab3:
                st.write("**Automated Email Captures**")
                email_count = 0
                for n in notes:
                    if n['type'] == 'email':
                        email_count += 1
                        date_str = datetime.datetime.fromisoformat(n['created_at'].replace('Z', '+00:00')).strftime("%Y-%m-%d %H:%M")
                        st.markdown(f"""
                        <div class="email-box">
                            <small style="color:#555;">{date_str} - 📧 Forwarded Email</small><br>
                            {n['content']}
                        </div>
                        """, unsafe_allow_html=True)
                if email_count == 0:
                    st.info("No forwarded emails received yet.")

    if len(companies) > 50:
        st.warning("Showing top 50 results. Use the search bar to find more specific companies.")
