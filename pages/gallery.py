import streamlit as st
import os
import sys

# Ensure backend imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from supabase_utils import get_supabase

# --- Configuration ---
st.set_page_config(page_title="Medya Kütüphanesi", page_icon="📸", layout="wide")

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

# We embedded tags into file_type for gdrive files: "gdrive_file|tag1,tag2"
all_tags = set()
for m in media_items:
    file_type = m.get('type', '')
    if '|' in file_type:
        tags_str = file_type.split('|')[1]
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
    filtered_media = [m for m in filtered_media if filter_tag in m.get('type', '')]

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
            file_type = m.get('type', '')
            file_url = m.get('file_path', '')
            
            # Formatting tags for display
            display_tags = ""
            if '|' in file_type:
                t_str = file_type.split('|')[1]
                if t_str != "untagged":
                    display_tags = "🏷️ " + t_str[:30] + ("..." if len(t_str)>30 else "")
            
            if display_tags:
                st.caption(display_tags)
                
            if "gdrive" in file_type:
                st.markdown(f"📦 [Drive'da Görüntüle]({file_url})")
            elif "image" in file_type and file_url.startswith("http"):
                # Usually old supabase gets public URL from bucket, but if it's stored raw:
                pass 
            else:
                # Basic Supabase bucket public URL fetcher
                from supabase_utils import get_public_url
                public_link = get_public_url(file_url)
                st.image(public_link, use_column_width=True)
