import streamlit as st
import os
import sys

# Ensure backend imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import io
from PIL import Image
from supabase_utils import get_supabase, get_companies, delete_attachment, get_public_url, update_attachment_path
from google_drive_utils import find_or_create_folder, list_folder_files, move_drive_file, delete_drive_file, upload_file_to_drive

def show_gallery():

    st.title("📸 Medya Kütüphanesi & Dropzone")
    st.markdown("Fuarda telefonunuzla Google Drive '00_INBOX_SAHIPSIZ' klasörüne yüklediğiniz medyaları buradan firmalara atayabilirsiniz.")

    tab1, tab2 = st.tabs(["📥 Sahipsizler (Inbox)", "📚 Tüm Arşiv"])

    with tab1:
        st.subheader("İşlem Bekleyen Medyalar")
        
        # 1. Get or Create Inbox Folder
        inbox_folder_id = find_or_create_folder("00_INBOX_SAHIPSIZ")
        if not inbox_folder_id:
            st.error("Google Drive API ayarlanamadı veya INBOX klasörü bulunamadı.")
            st.stop()
            
        def compress_image(uploaded_file, max_size_kb=500):
            try:
                img = Image.open(uploaded_file)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                output = io.BytesIO()
                img.save(output, format="JPEG", quality=85, optimize=True)
                size_kb = len(output.getvalue()) / 1024
                quality = 85
                while size_kb > max_size_kb and quality > 10:
                    quality -= 10
                    output = io.BytesIO()
                    img.save(output, format="JPEG", quality=quality, optimize=True)
                    size_kb = len(output.getvalue()) / 1024
                return output.getvalue()
            except Exception as e:
                st.error(f"Error compressing: {e}")
                return uploaded_file.getvalue()
                
        # 2. Add File Uploader for manual add
        st.write("📤 **Veya Buradan Dosya Yükleyin / Sürükleyip Bırakın:**")
        uploaded_files = st.file_uploader("Inbox'a Yükle", accept_multiple_files=True, type=["png", "jpg", "jpeg", "pdf"], key="inbx_up")
        if st.button("Seçili Dosyaları Inbox'a Yükle", type="primary", use_container_width=True) and uploaded_files:
            with st.spinner("Dosyalar Google Drive Inbox'a yükleniyor..."):
                for f in uploaded_files:
                    mime = f.type
                    file_bytes = compress_image(f) if "image" in mime else f.getvalue()
                    upload_file_to_drive(file_bytes, f.name, mime, inbox_folder_id)
                st.success("Başarıyla Inbox'a düştü!")
                st.rerun()

        st.markdown("---")
        # 3. Add an info box on how to use the Dropzone natively
        st.info("💡 **İpucu:** Telefonunuzdan direkt Google Drive'ı açıp `IBS_2026_Gallery / 00_INBOX_SAHIPSIZ` klasörüne fotoğraf yükleyebilirsiniz. Yenile tuşuna basınca buraya düşerler.")
        if st.button("🔄 Drive'ı Tara", use_container_width=True):
            st.rerun()

        # 3. Pull files
        with st.spinner("Inbox taranıyor..."):
            inbox_files = list_folder_files(inbox_folder_id)
            
        if not inbox_files:
            st.success("Tebrikler! İşlem bekleyen sahipsiz medya yok. 🎉")
        else:
            # Add a global search bar exactly like in Firma Listesi
            gal_search = st.text_input("🔍 Hızlı Firma Ara (Stand No, İsim vs.)", placeholder="Arama yaparsanız alttaki menülerde sadece eşleşenler çıkar", key="gal_comp_search")
            
            with st.spinner("Firmalar yükleniyor..."):
                companies = get_companies(search_query=gal_search) if gal_search else get_companies()
                
            comp_options = {c['id']: f"{c['booth_number']} - {c['company_name']}" for c in companies}
            
            if not comp_options:
                st.warning("⚠️ Aramanızla eşleşen firma bulunamadı. Lütfen kelimeyi veya numarayı değiştirin.")
            
            # Pagination logic for Inbox
            if 'inbox_page' not in st.session_state:
                st.session_state['inbox_page'] = 1

            inbox_items_per_page = 40
            inbox_total = len(inbox_files)
            inbox_total_pages = max(1, (inbox_total + inbox_items_per_page - 1) // inbox_items_per_page)

            if st.session_state['inbox_page'] > inbox_total_pages:
                st.session_state['inbox_page'] = 1
                
            inb_current_page = st.session_state['inbox_page']
            
            st.success(f"İşlem bekleyen {inbox_total} medya var. (Sayfa {inb_current_page} / {inbox_total_pages})")

            # Pagination buttons for Inbox
            if inbox_total_pages > 1:
                col_p, col_m, col_n = st.columns([1, 4, 1])
                with col_p:
                    if st.button("⬅️ Önceki", disabled=inb_current_page <= 1, key="prev_inb", use_container_width=True):
                        st.session_state['inbox_page'] = inb_current_page - 1
                        st.rerun()
                with col_n:
                    if st.button("Sonraki ➡️", disabled=inb_current_page >= inbox_total_pages, key="next_inb", use_container_width=True):
                        st.session_state['inbox_page'] = inb_current_page + 1
                        st.rerun()
            
            # Slice the media for current page
            s_idx = (inb_current_page - 1) * inbox_items_per_page
            e_idx = s_idx + inbox_items_per_page
            page_inbox_files = inbox_files[s_idx:e_idx]

            # Show grid of inbox files
            slider_inbox = st.slider("🖼️ Yan Yana Kaç Resim Gösterilsin? (Inbox)", min_value=1, max_value=6, value=3, key="slider_inbox")
            cols = st.columns(slider_inbox)
            for idx, f in enumerate(page_inbox_files):
                with cols[idx % slider_inbox]:
                    with st.container(border=True):
                        st.markdown(f"**{f.get('name')}**")
                        
                        preview_url = f.get('thumbnailLink')
                        file_id = f.get('id')
                        web_link = f.get('webViewLink')
                        file_name_lower = f.get('name', '').lower()
                        
                        # --- Smart Suggestions based on filename ---
                        suggested_comp_id = list(comp_options.keys())[0] # Default to first
                        for comp_id, label in comp_options.items():
                            comp_name_lower = label.split(" - ")[1].lower()
                            # If company name length > 3 and is in filename
                            if len(comp_name_lower) > 3 and comp_name_lower in file_name_lower:
                                suggested_comp_id = comp_id
                                break
                                
                        suggested_tags = []
                        if "katalog" in file_name_lower or "catalog" in file_name_lower:
                            suggested_tags.append("Katalog")
                        if "kartvizit" in file_name_lower or "card" in file_name_lower:
                            suggested_tags.append("Kartvizit")
                        if "fiyat" in file_name_lower or "price" in file_name_lower or "teklif" in file_name_lower:
                            suggested_tags.append("Fiyat Teklifi")
                        if "ürün" in file_name_lower or "product" in file_name_lower:
                            suggested_tags.append("Ürün Görseli")
                            
                        # Convert default tag list to comma string
                        default_tags_str = ", ".join(suggested_tags)
                        
                        if preview_url:
                            # Drive thumbnails often end with =s220, replace to get higher resolution
                            hq_preview = preview_url.replace("=s220", "=s1200") if "=s" in preview_url else preview_url
                            st.image(hq_preview, use_container_width=True)
                            st.caption(f"[Drive'da Orijinalini Aç]({web_link})")
                        else:
                            st.markdown(f"📦 [Drive'da Aç]({web_link})")
                            
                        # Assignment Form
                        with st.form(key=f"assign_form_{file_id}"):
                            # Pre-select index based on suggestion
                            default_idx = list(comp_options.keys()).index(suggested_comp_id)
                            
                            selected_comp_id = st.selectbox("💡 Hangi Firmanın?", options=list(comp_options.keys()), format_func=lambda x: comp_options[x], index=default_idx, key=f"sel_{file_id}")
                            tags_input = st.text_input("Etiket (Katalog, Kartvizit vs)", value=default_tags_str, placeholder="Örn: Katalog, Kartvizit", key=f"tgi_{file_id}")
                            
                            if st.form_submit_button("Ata ve Kaydet", type="primary", use_container_width=True):
                                # Logic to move and save
                                comp = next((c for c in companies if c['id'] == selected_comp_id), None)
                                if comp:
                                    clean_cname = "".join(c for c in comp['company_name'] if c.isalnum() or c in " _-").strip()
                                    subfolder_name = f"{comp['booth_number']}_{clean_cname}"
                                    
                                    with st.spinner("Dosya Drive'da taşınıyor..."):
                                        comp_folder_id = find_or_create_folder(subfolder_name)
                                        if comp_folder_id:
                                            success = move_drive_file(file_id, comp_folder_id)
                                            if success:
                                                # Insert to Supabase DB
                                                supabase = get_supabase()
                                                
                                                clean_tags = [t.strip().replace('#', '') for t in tags_input.split(',')] if tags_input else []
                                                tags_param = ",".join(clean_tags) if clean_tags else "untagged"
                                                db_path = f"{web_link}#id={file_id}#tags={tags_param}"
                                                
                                                try:
                                                    supabase.table("attachments").insert({
                                                        "company_id": comp['id'],
                                                        "file_name": f.get('name'),
                                                        "file_type": f.get('mimeType'),
                                                        "file_path": db_path
                                                    }).execute()
                                                    st.toast(f"Dosya başarıyla {comp['company_name']} firmasına atandı!", icon="✅")
                                                    st.rerun()
                                                except Exception as e:
                                                    st.error(f"Veritabanına yazılırken hata: {e}")
                                            else:
                                                st.error("Google Drive taşıma işlemi başarısız oldu.")
                                        else:
                                            st.error("Firma klasörü yaratılamadı.")

    with tab2:
        st.subheader("📚 Sistemdeki Tüm Medyalar")
        # --- Fetch All Attachments ---
        @st.cache_data(ttl=60)
        def fetch_all_media():
            supabase = get_supabase()
            response = supabase.table("attachments").select("*, companies(company_name, booth_number, segment)").order("created_at", desc=True).execute()
            return response.data

        media_items = fetch_all_media()

        if not media_items:
            st.info("Sisteme atanmış herhangi bir medya bulunamadı.")
        else:
            # Extract unique filters
            all_booths = sorted(list(set([m['companies']['booth_number'] for m in media_items if m.get('companies')])))
            all_segments = sorted(list(set([m['companies']['segment'] for m in media_items if m.get('companies') and m['companies'].get('segment')])))

            all_tags = set()
            for m in media_items:
                file_path = m.get('file_path', '')
                if '#tags=' in file_path:
                    tags_str = file_path.split('#tags=')[1]
                    for t in tags_str.split(','):
                        if t.strip() and t.strip() != "untagged":
                            all_tags.add(t.strip())
            all_tags = sorted(list(all_tags))

            st.markdown("🔍 **Kütüphane Filtreleri**")
            col1, col2, col3 = st.columns(3)
            filter_booth = col1.selectbox("Stand Numarası", ["Tümü"] + all_booths)
            filter_segment = col2.selectbox("Firma Segmenti", ["Tümü"] + all_segments)
            filter_tag = col3.selectbox("Ürün Etiketi", ["Tümü"] + all_tags)

            # Apply Filters
            filtered_media = media_items
            if filter_booth != "Tümü":
                filtered_media = [m for m in filtered_media if m.get('companies') and m['companies']['booth_number'] == filter_booth]
            if filter_segment != "Tümü":
                filtered_media = [m for m in filtered_media if m.get('companies') and m['companies']['segment'] == filter_segment]
            if filter_tag != "Tümü":
                filtered_media = [m for m in filtered_media if f"#tags=" in m.get('file_path', '') and filter_tag in m.get('file_path', '')]

            # Pagination logic
            if 'gal_page' not in st.session_state:
                st.session_state['gal_page'] = 1

            items_per_page = 40
            total_items = len(filtered_media)
            total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)

            # Ensure current page is valid when changing filters
            if st.session_state['gal_page'] > total_pages:
                st.session_state['gal_page'] = 1
                
            current_page = st.session_state['gal_page']

            st.success(f"Toplam {total_items} medya dosyası bulundu. (Sayfa {current_page} / {total_pages})")

            # Pagination buttons
            if total_pages > 1:
                col_prev, col_mid, col_next = st.columns([1, 4, 1])
                with col_prev:
                    if st.button("⬅️ Önceki", disabled=current_page <= 1, key="prev_page_gal", use_container_width=True):
                        st.session_state['gal_page'] = current_page - 1
                        st.rerun()
                with col_next:
                    if st.button("Sonraki ➡️", disabled=current_page >= total_pages, key="next_page_gal", use_container_width=True):
                        st.session_state['gal_page'] = current_page + 1
                        st.rerun()

            # Slice the media for current page
            start_idx = (current_page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            page_items = filtered_media[start_idx:end_idx]

            # --- Display Grid ---
            slider_lib = st.slider("🖼️ Yan Yana Kaç Resim Gösterilsin? (Arşiv)", min_value=1, max_value=8, value=4, key="slider_lib")
            cols2 = st.columns(slider_lib)
            for idx, m in enumerate(page_items):
                with cols2[idx % slider_lib]:
                    with st.container(border=True):
                        company_info = m.get('companies')
                        if company_info:
                            st.markdown(f"**{company_info.get('company_name', 'Bilinmiyor')}**")
                            st.caption(f"📍 Stand: {company_info.get('booth_number', 'Bilinmiyor')}")
                    
                        file_type = m.get('file_type', '')
                        file_url = m.get('file_path', '')
                        is_gdrive = "drive.google.com" in file_url
                    
                        display_tags = ""
                        if '#tags=' in file_url:
                            t_str = file_url.split('#tags=')[1]
                            if t_str != "untagged":
                                display_tags = "🏷️ " + t_str[:30] + ("..." if len(t_str)>30 else "")
                    
                        if display_tags:
                            st.caption(display_tags)
                        
                        if is_gdrive:
                            clean_url = file_url.split('#')[0]
                            file_id = None
                            parts = file_url.split('#')
                            for p in parts[1:]:
                                if p.startswith('id='):
                                    file_id = p[3:]
                            
                            if file_id:
                                preview_url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w400"
                                if file_type == "image" or "application" not in file_type: # Fallback
                                    rot_key = f"rot_gal_{m['id']}"
                                    angle = st.session_state.get(rot_key, 0)
                                    
                                    # Use st.image for native fullscreen expansion icon
                                    hq_preview = preview_url.replace("sz=w400", "sz=w1200")
                                    st.image(hq_preview, use_container_width=True)
                                    st.caption(f"[Drive'da Aç]({clean_url})")
                                    
                                    if st.button("🔄 Çevir", key=f"btn_{rot_key}", use_container_width=True):
                                        st.session_state[rot_key] = (angle + 90) % 360
                                        st.rerun()
                                else:
                                    st.markdown(f"📦 [Drive'da Aç]({clean_url})")
                            
                            with st.expander("📝 Etiketi Düzenle"):
                                new_tags_raw = st.text_input("Etiketler", value=display_tags.replace('🏷️ ', ''), key=f"edit_gal_{m['id']}")
                                if st.button("💾 Kaydet", key=f"save_gal_{m['id']}", use_container_width=True):
                                    new_tags_list = [t.strip().replace('#', '') for t in new_tags_raw.split(',') if t.strip()]
                                    new_t_str = ",".join(new_tags_list) if new_tags_list else "untagged"
                                    raw_path = file_url
                                    parts = raw_path.split('#')
                                    new_parts = [parts[0]]
                                    for p in parts[1:]:
                                        if p.startswith('id='): new_parts.append(p)
                                    new_parts.append(f"tags={new_t_str}")
                                    update_attachment_path(m['id'], "#".join(new_parts))
                                    st.rerun()
                            
                            
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("🗑️ Sil", key=f"del_gal_{m['id']}", use_container_width=True):
                                    if file_id:
                                        delete_drive_file(file_id)
                                    delete_attachment(m['id'])
                                    st.rerun()
                            with c2:
                                if st.button("🔙 Geri Al", help="Inbox'a geri gönderir", key=f"undo_{m['id']}", use_container_width=True):
                                    inb_id = find_or_create_folder("00_INBOX_SAHIPSIZ")
                                    if file_id and inb_id:
                                        move_drive_file(file_id, inb_id)
                                    delete_attachment(m['id'])
                                    st.toast("Medya Inbox'a geri gönderildi!", icon="↪️")
                                    st.rerun()
                        elif "image" in file_type and file_url.startswith("http"):
                            st.image(file_url, use_column_width=True)
                            if st.button("🗑️ Sil", key=f"del_gal_{m['id']}", use_container_width=True):
                                delete_attachment(m['id'])
                                st.rerun()
                        else:
                            public_link = get_public_url(file_url)
                            st.image(public_link, use_column_width=True)
                            if st.button("🗑️ Sil", key=f"del_gal_{m['id']}", use_container_width=True):
                                delete_attachment(m['id'])
                                st.rerun()

