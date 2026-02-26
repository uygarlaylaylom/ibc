import streamlit as st
import pandas as pd
import re
from typing import List, Dict, Any
import datetime
import io
import os
import sys

from supabase_utils import (
    get_supabase, get_companies, update_company, get_notes, add_note, delete_note, 
    get_attachments, upload_attachment, get_public_url, get_contacts, add_contact, delete_contact
)
from ocr_local import extract_text_from_image_bytes
from seed_database import seed_companies
from google_drive_utils import find_or_create_folder, upload_file_to_drive

# --- Configuration ---
st.set_page_config(page_title="IBS 2026 İstihbarat", page_icon="🏢", layout="wide")

# --- Authentication ---
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        if st.session_state.get("pwd_input", "") == st.secrets.get("APP_PASSWORD", "fuar2026"):
            st.session_state["password_correct"] = True
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Lütfen Giriş Şifresini Yazın", type="password", on_change=password_entered, key="pwd_input")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Lütfen Giriş Şifresini Yazın", type="password", on_change=password_entered, key="pwd_input")
        st.error("😕 Hatalı şifre.")
        return False
    else:
        return True

if not check_password():
    st.stop()


# --- Navigation (SPA) ---
st.sidebar.title("📌 IBS 2026 Navigasyon")
app_mode = st.sidebar.radio("Modül Seçin:", ["Firma Listesi", "Medya Kütüphanesi", "Analiz & Görevler"])
st.sidebar.markdown("---")

if app_mode == "Firma Listesi":

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
        import traceback
        st.error(f"Veritabanı bağlantı hatası: {e}")
        st.code(traceback.format_exc())
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
                    <h3><span class="booth-badge">{comp['booth_number']}</span></h3>
                </div>
                """, unsafe_allow_html=True)
            
                # --- Editable Core Details ---
                col_name, col_seg = st.columns([0.7, 0.3])
                with col_name:
                    new_name = st.text_input("Şirket Adı / Company Name", value=comp.get('company_name', ''), key=f"name_{comp['id']}")
                with col_seg:
                    new_seg = st.text_input("Segment", value=comp.get('segment', ''), key=f"seg_{comp['id']}")
                
                new_desc = st.text_area("Açıklama / Description", value=comp.get('description', ''), key=f"desc_{comp['id']}")
            
                # Editable Website inline
                col_web1, col_web2 = st.columns([0.8, 0.2])
                with col_web1:
                    new_web = st.text_input("Website", value=comp.get('website', ''), key=f"web_{comp['id']}")
                with col_web2:
                    # We save all 4 core fields at once to avoid multiple clicks
                    if st.button("💾 Bilgileri Kaydet (Save)", key=f"save_core_{comp['id']}", type="primary", use_container_width=True):
                        updates = {}
                        if new_name != comp.get('company_name'): updates['company_name'] = new_name
                        if new_seg != comp.get('segment'): updates['segment'] = new_seg
                        if new_desc != comp.get('description'): updates['description'] = new_desc
                        if new_web != comp.get('website'): updates['website'] = new_web
                    
                        if updates:
                            update_company(comp['id'], **updates)
                            st.success("Tüm bilgiler kaydedildi! (Sayfa yenileniyor...)")
                            st.rerun()
            
                if comp.get('website'):
                    st.markdown(f"🔗 <a href='{comp['website']}' target='_blank'>Ziyaret Et / Visit</a>", unsafe_allow_html=True)
            
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

                # TAB 2: Attachments / Media
                with tab2:
                    st.info("📦 **Dosyalar Google Drive'a Yüklenecektir** (IBS_2026_Gallery)")
                
                    # Check for existing Google Drive folder for this company or just use a main folder
                    # We'll put everything in one main folder or subfolders, let's use: IBS_2026_Gallery / [Booth]_[Name]
                
                    uploaded_files = st.file_uploader("Katalog veya Fotoğraf Yükle (Çoklu Seçim)", type=['png', 'jpg', 'jpeg', 'pdf'], key=f"file_{comp['id']}", accept_multiple_files=True)
                    if uploaded_files:
                        col_u1, col_u2 = st.columns(2)
                        with col_u1:
                            custom_name = st.text_input("Grup / Ortak Dosya Adı (Opsiyonel)", key=f"cname_{comp['id']}")
                        with col_u2:
                            custom_tags_val = st.text_input("Özel Etiketler (Örn: #katalog, #stand)", key=f"ctags_{comp['id']}")
                            
                        if st.button(f"{len(uploaded_files)} Dosyayı Google Drive'a Yükle", key=f"up_btn_{comp['id']}", type="primary", use_container_width=True):
                            with st.spinner("Dosyalar Drive'a gönderiliyor..."):
                                main_folder_id = find_or_create_folder("IBS_2026_Gallery")
                                if not main_folder_id:
                                    st.error("Google Drive kütüphanesine bağlanılamadı. Ayarları kontrol edin.")
                                else:
                                    clean_cname = "".join(c for c in comp['company_name'] if c.isalnum() or c in " _-").strip()
                                    subfolder_name = f"{comp['booth_number']}_{clean_cname}"
                                    subfolder_id = find_or_create_folder(subfolder_name, parent_id=main_folder_id)
                                
                                    success_count = 0
                                    for idx, uploaded_file in enumerate(uploaded_files):
                                        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                                        base_name = custom_name.strip() if custom_name.strip() else uploaded_file.name
                                        if custom_name.strip():
                                            filename = f"{timestamp}_{base_name}_{idx+1}"
                                        else:
                                            filename = f"{timestamp}_{base_name}"
                                        
                                        mime_type = uploaded_file.type
                                        file_bytes = uploaded_file.getvalue()
                                    
                                        if "image" in mime_type:
                                            try:
                                                from PIL import Image
                                                import io
                                                img = Image.open(io.BytesIO(file_bytes))
                                                max_size = (1920, 1920)
                                                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                                                if img.mode in ("RGBA", "P"):
                                                    img = img.convert("RGB")
                                                img_byte_arr = io.BytesIO()
                                                fmt = "JPEG" if "jpeg" in mime_type or "jpg" in mime_type else "PNG"
                                                img.save(img_byte_arr, format=fmt, quality=85, optimize=True)
                                                file_bytes = img_byte_arr.getvalue()
                                            except Exception as img_err:
                                                st.warning(f"Görsel sıkıştırma atlandı ({uploaded_file.name}): {img_err}")
                                        
                                        gdrive_web_link, gdrive_file_id, gdrive_thumb = upload_file_to_drive(file_bytes, filename, mime_type, subfolder_id)
                                        
                                        if gdrive_web_link:
                                            # Merge default tags and custom tags
                                            auto_tags = (comp.get('tags') or []) + (comp.get('products') or [])
                                            
                                            # Parse user inputted custom tags like "#katalog, #stand"
                                            c_tags_list = []
                                            if custom_tags_val:
                                                c_tags_list = [t.strip().replace('#', '') for t in custom_tags_val.split(',') if t.strip()]
                                            
                                            final_tags = list(set(auto_tags + c_tags_list))
                                            all_tags_str = ",".join(final_tags) if final_tags else "untagged"
                                            
                                            db_file_type = "image" if "image" in mime_type else "document"
                                            
                                            # Package URL: only store file_id and tags (no thumb - Drive thumbnails require auth)
                                            id_frag = f"#id={gdrive_file_id}" if gdrive_file_id else ""
                                            tag_frag = f"#tags={all_tags_str}"
                                            gdrive_link_package = f"{gdrive_web_link}{id_frag}{tag_frag}"
                                            
                                            upload_attachment(comp['id'], file_name=gdrive_link_package, file_type=db_file_type, source="gdrive")
                                            success_count += 1
                                        else:
                                            st.error(f"Hata: {uploaded_file.name} yüklenemedi.")
                                
                                    if success_count > 0:
                                        st.success(f"Başarılı! {success_count} adet dosya Drive'a kaydedildi.")
                                        st.rerun()
                            
                    attachments = get_attachments(comp['id'])
                    if attachments:
                        st.write("**Google Drive Dosyaları:**")
                        cols = st.columns(3)
                        for i, att in enumerate(attachments):
                            url = get_public_url(att['file_path'])
                            is_gdrive = "drive.google.com" in att['file_path']
                        
                            with cols[i % 3]:
                                with st.container(border=True):
                                    # Always parse metadata from the stored URL fragments
                                    raw_path = att['file_path']
                                    clean_url = raw_path.split('#')[0] if '#' in raw_path else raw_path
                                    file_id = None
                                    display_tags = ""
                                    if is_gdrive:
                                        parts = raw_path.split('#')
                                        for p in parts[1:]:
                                            if p.startswith('id='):
                                                file_id = p[3:]
                                            elif p.startswith('tags='):
                                                t_str = p[5:]
                                                if t_str and t_str != 'untagged':
                                                    display_tags = t_str[:40]
                                    
                                    if is_gdrive and file_id:
                                        # Use Drive's embeddable preview URL (no auth required)
                                        preview_url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w400"
                                        embed_url = f"https://drive.google.com/file/d/{file_id}/preview"
                                        if att['file_type'] == 'image':
                                            st.markdown(f'<a href="{clean_url}" target="_blank"><img src="{preview_url}" style="width:100%;border-radius:6px;" onerror="this.style.display=\'none\'"/></a>', unsafe_allow_html=True)
                                        else:
                                            st.markdown(f'<iframe src="{embed_url}" width="100%" height="180" frameborder="0" allow="autoplay"></iframe>', unsafe_allow_html=True)
                                        st.markdown(f"📦 [Drive'da Aç]({clean_url})")
                                    elif att['file_type'] == 'image' and not is_gdrive:
                                        st.image(url, use_column_width=True)
                                    else:
                                        st.markdown(f"🔗 [Görüntüle]({clean_url})")
                                    
                                    if display_tags:
                                        st.caption(f"🏷️ {display_tags}")
                                    
                                    if st.button("🗑️ Sil", key=f"del_att_{att['id']}", use_container_width=True):
                                        if is_gdrive and file_id:
                                            from google_drive_utils import delete_drive_file
                                            delete_drive_file(file_id)
                                        from supabase_utils import delete_attachment
                                        delete_attachment(att['id'])
                                        st.rerun()
                    else:
                        st.info("Henüz eklenmiş dosya yok.")

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
                         st.info("📷 **Kartvizit OCR İşlemi (Yerel Sürüm)**\nResmi yükleyin veya kameradan fotoğraf çekin.")
                     
                         ocr_mode = st.radio("Fotoğraf Kaynağı", ["Dosya Yükle", "Kamera Başlat"], horizontal=True, key=f"ocr_mode_{comp['id']}")
                     
                         ocr_img = None
                         if ocr_mode == "Dosya Yükle":
                             ocr_img = st.file_uploader("Kartvizit Yükle (OCR)", type=['png', 'jpg', 'jpeg'], key=f"ocr_up_{comp['id']}")
                         else:
                             ocr_img = st.camera_input("Fotoğraf Çek", key=f"ocr_cam_{comp['id']}")
                         
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

                # --- Admin Section for Database Reset ---
                st.sidebar.markdown("---")
                st.sidebar.title("⚙️ Admin Tools")
                if st.sidebar.button("🔄 Reset & Seed Database (Danger)"):
                    with st.spinner("Flushing old data and importing clean Excel..."):
                        seed_companies("ibs_2026_all_exhibitors_clean.xlsx")
                        st.success("Database successfully reset to clean version! Refresh the page.")
                        # We don't auto rerun instantly to let them read the success message, 
                        # but they can reload the app.

                if len(companies) > 50:
                    st.warning("Showing top 50 results. Use the search bar to find more specific companies.")
elif app_mode == "Medya Kütüphanesi":
    from views.gallery import show_gallery
    show_gallery()
elif app_mode == "Analiz & Görevler":
    from views.dashboard import show_dashboard
    show_dashboard()
