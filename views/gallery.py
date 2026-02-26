import streamlit as st
import os
import sys

# Ensure backend imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from supabase_utils import get_supabase

def show_gallery():

    st.title("📸 Medya Kütüphanesi (Google Drive)")
    st.markdown("Fuar boyunca kaydedilen tüm resim, katalog ve kartvizitler burada toplanır.")

    # --- Fetch All Attachments ---
    @st.cache_data(ttl=60)
    def fetch_all_media():
        supabase = get_supabase()
        # Fetch all attachments and join with companies to get names/booths
        response = supabase.table("attachments").select("*, companies(company_name, booth_number, segment)").order("created_at", desc=True).execute()
        return response.data

    media_items = fetch_all_media()

    if not media_items:
        st.info("Henüz Google Drive'a veya sisteme yüklenmiş bir medya yok.")
        st.stop()

    # --- Filters ---
    st.sidebar.title("🔍 Kütüphane Filtreleri")

    # Extract unique filters
    all_booths = sorted(list(set([m['companies']['booth_number'] for m in media_items if m.get('companies')])))
    all_segments = sorted(list(set([m['companies']['segment'] for m in media_items if m.get('companies') and m['companies'].get('segment')])))

    # We embedded tags into the file_path url fragment for gdrive files: "#tags=tag1,tag2"
    all_tags = set()
    for m in media_items:
        file_path = m.get('file_path', '')
        if '#tags=' in file_path:
            tags_str = file_path.split('#tags=')[1]
            for t in tags_str.split(','):
                if t.strip() and t.strip() != "untagged":
                    all_tags.add(t.strip())
    all_tags = sorted(list(all_tags))

    filter_booth = st.sidebar.selectbox("Stand Numarası (Booth)", ["Tümü"] + all_booths)
    filter_segment = st.sidebar.selectbox("Firma Segmenti", ["Tümü"] + all_segments)
    filter_tag = st.sidebar.selectbox("Ürün Etiketi (Tag)", ["Tümü"] + all_tags)

    # Apply Filters
    filtered_media = media_items
    if filter_booth != "Tümü":
        filtered_media = [m for m in filtered_media if m.get('companies') and m['companies']['booth_number'] == filter_booth]
    if filter_segment != "Tümü":
        filtered_media = [m for m in filtered_media if m.get('companies') and m['companies']['segment'] == filter_segment]
    if filter_tag != "Tümü":
        filtered_media = [m for m in filtered_media if f"#tags=" in m.get('file_path', '') and filter_tag in m.get('file_path', '')]

    st.success(f"{len(filtered_media)} medya dosyası listeleniyor.")

    # --- Display Grid ---
    cols = st.columns(4)
    for idx, m in enumerate(filtered_media):
        with cols[idx % 4]:
            with st.container(border=True):
                company_info = m.get('companies')
                if company_info:
                    st.markdown(f"**{company_info.get('company_name', 'Bilinmiyor')}**")
                    st.caption(f"📍 Stand: {company_info.get('booth_number', 'Bilinmiyor')}")
            
                # If it's a gdrive link, it's just a clickable URL
                file_type = m.get('file_type', '')
                file_url = m.get('file_path', '')
                is_gdrive = "drive.google.com" in file_url
            
                # Formatting tags for display
                display_tags = ""
                if '#tags=' in file_url:
                    t_str = file_url.split('#tags=')[1]
                    if t_str != "untagged":
                        display_tags = "🏷️ " + t_str[:30] + ("..." if len(t_str)>30 else "")
            
                if display_tags:
                    st.caption(display_tags)
                
                if is_gdrive:
                    clean_url = file_url.split('#')[0]
                    thumb_url = None
                    file_id = None
                    parts = file_url.split('#')
                    for p in parts:
                        if p.startswith('thumb='):
                            thumb_url = p.replace('thumb=', '')
                        elif p.startswith('id='):
                            file_id = p.replace('id=', '')
                    
                    if thumb_url:
                        st.image(thumb_url, use_column_width=True)
                        st.markdown(f"📦 [Drive'da Aç]({clean_url})")
                    else:
                        st.markdown(f"🔗 [Görüntüle]({clean_url})")
                        
                    if st.button("🗑️ Sil", key=f"del_gal_{m['id']}", use_container_width=True):
                        from google_drive_utils import delete_drive_file
                        from supabase_utils import delete_attachment
                        if file_id:
                            delete_drive_file(file_id)
                        delete_attachment(m['id'])
                        st.rerun()
                elif "image" in file_type and file_url.startswith("http"):
                    st.image(file_url, caption="Supabase", use_column_width=True)
                    if st.button("🗑️ Sil", key=f"del_gal_{m['id']}", use_container_width=True):
                        from supabase_utils import delete_attachment
                        delete_attachment(m['id'])
                        st.rerun()
                else:
                    from supabase_utils import get_public_url
                    public_link = get_public_url(file_url)
                    st.image(public_link, use_column_width=True)
                    if st.button("🗑️ Sil", key=f"del_gal_{m['id']}", use_container_width=True):
                        from supabase_utils import delete_attachment
                        delete_attachment(m['id'])
                        st.rerun()
