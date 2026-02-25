import streamlit as st
import pandas as pd
from PIL import Image
import io
import datetime
from supabase_utils import (
    get_companies, update_company, get_notes, add_note, delete_note,
    get_attachments, upload_attachment, get_public_url,
    get_contacts, add_contact, delete_contact
)
from ocr_local import extract_text_from_image_bytes

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

# Primary Segments (from IBS 2026 data)
AVAILABLE_SEGMENTS = [
    "All",
    "Building Materials", 
    "Interior Finishings & Home Living", 
    "Business Management & Professional Services", 
    "Construction Tools, Systems, Equipment, & Safety", 
    "Outdoor Living, Leisure, & Modular Structures", 
    "Global Products"
]

# Common IBS Products (Extracted Default List)
AVAILABLE_PRODUCTS = [
    "Windows", "Doors", "Flooring", "Roofing", "Apparel",
    "Siding", "HVAC", "Plumbing", "Electrical", "Software", 
    "Home Automation", "Lighting", "Kitchen Appliances",
    "Cabinets", "Bath Products", "Outdoor Living", "Tools",
    "Hardware", "Fasteners", "Insulation"
]

# --- Sidebar Filters ---
st.sidebar.title("📌 Navigation")
st.sidebar.page_link("pages/dashboard.py", label="IBC Intelligence Dashboard", icon="🚀")
st.sidebar.markdown("---")

st.sidebar.title("🔍 Filters & Search")
search_query = st.sidebar.text_input("Search (Booth, Name...)", "")

st.sidebar.markdown("### Category Filters")
selected_segment = st.sidebar.selectbox("📂 Segment / Product Group", AVAILABLE_SEGMENTS, index=0)
selected_tag_filter = st.sidebar.selectbox("🏷️ Company Tag", ["All"] + AVAILABLE_TAGS, index=0)
selected_product_filter = st.sidebar.selectbox("📦 Product", ["All"] + AVAILABLE_PRODUCTS, index=0)

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
        
        # Apply strict Segment filtering
        if selected_segment != "All":
            companies = [c for c in companies if c.get('segment') == selected_segment]
            
        # Apply strict Tag filtering
        if selected_tag_filter != "All":
            companies = [c for c in companies if c.get('tags') and selected_tag_filter in c['tags']]
            
        # Apply strict Product filtering
        if selected_product_filter != "All":
            companies = [c for c in companies if c.get('products') and selected_product_filter in c['products']]
            
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
                <p><i>{comp.get('description', 'No description available')}</i></p>
            </div>
            """, unsafe_allow_html=True)
            
            # Editable Website inline
            col_web1, col_web2 = st.columns([0.8, 0.2])
            with col_web1:
                new_web = st.text_input("Website", value=comp.get('website', ''), key=f"web_{comp['id']}")
            with col_web2:
                if st.button("Save URL", key=f"save_web_{comp['id']}"):
                    if new_web != comp.get('website'):
                        update_company(comp['id'], website=new_web)
                        st.success("Saved!")
                        st.rerun()
            
            if comp.get('website'):
                st.markdown(f"🔗 <a href='{comp['website']}' target='_blank'>Ziyaret Et</a>", unsafe_allow_html=True)
            
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
                # Load current values, ensure they exist in allowed options
                current_tags = comp.get('tags') or []
                current_products = comp.get('products') or []
                
                all_tags_options = list(set(AVAILABLE_TAGS + current_tags))
                new_tags = st.multiselect(
                    "Tags", 
                    options=all_tags_options, 
                    default=current_tags,
                    key=f"tags_{comp['id']}"
                )
                
                all_products_options = list(set(AVAILABLE_PRODUCTS + current_products))
                new_products = st.multiselect(
                    "Products", 
                    options=all_products_options, 
                    default=current_products,
                    key=f"products_{comp['id']}"
                )
                
                # Check for changes and show save button
                if set(new_tags) != set(current_tags) or set(new_products) != set(current_products):
                    if st.button("💾 Save Categories", key=f"save_cats_{comp['id']}"):
                        update_company(comp['id'], tags=new_tags, products=new_products)
                        st.rerun()

                    
            st.markdown("---")
            
            # Content Tabs
            tab1, tab2, tab3, tab4 = st.tabs(["📝 Notes", "📂 Attachments", "📧 History", "👤 Contacts & OCR"])
            
            
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
            
            # TAB 4: Contacts & OCR
            with tab4:
                 st.write("**Kişiler & Kartvizit Tarama**")
                 ocr_col, manual_col = st.columns([1, 1])
                 
                 with ocr_col:
                     st.info("📷 **Kartvizit OCR İşlemi (Yerel Sürüm)**\nResmi yükleyin, metni okuyun ve yandaki forma aktarın.")
                     ocr_img = st.file_uploader("Kartvizit Yükle (OCR)", type=['png', 'jpg', 'jpeg'], key=f"ocr_up_{comp['id']}")
                     
                     raw_ocr_text = ""
                     if ocr_img is not None:
                         if st.button("OCR'ı Başlat", key=f"run_ocr_{comp['id']}"):
                             with st.spinner("Tesseract metni çıkarıyor..."):
                                 raw_ocr_text = extract_text_from_image_bytes(ocr_img.getvalue())
                                 st.session_state[f"ocr_result_{comp['id']}"] = raw_ocr_text
                                 
                     if f"ocr_result_{comp['id']}" in st.session_state:
                         st.text_area("OCR Ham Metni (Kopyalamak için):", st.session_state[f"ocr_result_{comp['id']}"], height=200, key=f"raw_text_{comp['id']}")
                         
                 with manual_col:
                     with st.container(border=True):
                         st.write("➕ **Yeni Kişi Ekle**")
                         c_name = st.text_input("Ad Soyad", key=f"c_name_{comp['id']}")
                         c_title = st.text_input("Ünvan", key=f"c_title_{comp['id']}")
                         c_email = st.text_input("E-posta", key=f"c_email_{comp['id']}")
                         c_phone = st.text_input("Telefon", key=f"c_phone_{comp['id']}")
                         if st.button("Kişiyi Kaydet", type="primary", key=f"save_contact_{comp['id']}"):
                             if c_name:
                                 add_contact(comp['id'], name=c_name, title=c_title, email=c_email, phone=c_phone)
                                 st.success("Kişi kaydedildi!")
                                 st.rerun()
                             else:
                                 st.warning("Ad Soyad zorunludur.")
                 
                 st.write("---")
                 contacts_list = get_contacts(comp['id'])
                 if contacts_list:
                     for c in contacts_list:
                         ccol1, ccol2, ccol3 = st.columns([3, 3, 1])
                         with ccol1:
                             st.markdown(f"**{c.get('name', '')}** <small>({c.get('title', '')})</small>", unsafe_allow_html=True)
                         with ccol2:
                             st.markdown(f"📧 {c.get('email', '')}<br>📞 {c.get('phone', '')}", unsafe_allow_html=True)
                         with ccol3:
                             if st.button("🗑️", key=f"del_c_{c['id']}"):
                                 delete_contact(c['id'])
                                 st.rerun()
                 else:
                     st.info("Henüz kayıtlı kişi yok.")

    if len(companies) > 50:
        st.warning("Showing top 50 results. Use the search bar to find more specific companies.")
