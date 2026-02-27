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


# --- Navigation (SPA) ---
st.sidebar.title("📌 IBS 2026 Navigasyon")
app_mode = st.sidebar.radio("Modül Seçin:", ["Firma Listesi", "Medya Kütüphanesi", "🧠 İstihbarat Merkezi"])
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

    # Detailed IBS Products / Sub-Categories (Flat Tree)
    FLAT_CATEGORIES_DETAILED = [
        "1️⃣ Structural - Framing Systems", "1️⃣ Structural - Steel Framing", "1️⃣ Structural - Insulating Concrete Forms", 
        "1️⃣ Structural - Concrete Systems", "1️⃣ Structural - Structural Connectors", "1️⃣ Structural - Sheathing", 
        "1️⃣ Structural - Subfloor", "1️⃣ Structural - Anchors", "1️⃣ Structural - Fasteners",
        "2️⃣ Envelope - Siding", "2️⃣ Envelope - Cladding", "2️⃣ Envelope - Exterior Trim", "2️⃣ Envelope - Weather Barriers", 
        "2️⃣ Envelope - Air Barriers", "2️⃣ Envelope - Waterproofing", "2️⃣ Envelope - Sealants",
        "3️⃣ Roofing - Asphalt Roofing", "3️⃣ Roofing - Metal Roofing", "3️⃣ Roofing - Flat Roofing", 
        "3️⃣ Roofing - Roofing Accessories", "3️⃣ Roofing - Roof Drainage",
        "4️⃣ Windows & Doors - Windows", "4️⃣ Windows & Doors - Exterior Doors", "4️⃣ Windows & Doors - Interior Doors", 
        "4️⃣ Windows & Doors - Garage Doors", "4️⃣ Windows & Doors - Skylights", "4️⃣ Windows & Doors - Louvers", 
        "4️⃣ Windows & Doors - Entry Systems",
        "5️⃣ Insulation - Insulation", "5️⃣ Insulation - Spray Foam", "5️⃣ Insulation - Radiant Systems", 
        "5️⃣ Insulation - Energy Efficiency Systems", "5️⃣ Insulation - Weatherization",
        "6️⃣ HVAC - HVAC Systems", "6️⃣ HVAC - HVAC Controls", "6️⃣ HVAC - Ventilation", "6️⃣ HVAC - Indoor Air Quality", 
        "6️⃣ HVAC - Heat Pumps",
        "7️⃣ Plumbing - Plumbing Fixtures", "7️⃣ Plumbing - Pipe Systems", "7️⃣ Plumbing - Water Heaters", 
        "7️⃣ Plumbing - Drainage Systems",
        "8️⃣ Electrical - Wiring Devices", "8️⃣ Electrical - Lighting", "8️⃣ Electrical - Lighting Controls", 
        "8️⃣ Electrical - Electrical Distribution",
        "9️⃣ Smart Home - Home Automation", "9️⃣ Smart Home - Access Control", "9️⃣ Smart Home - Security Systems", 
        "9️⃣ Smart Home - Connected Devices",
        "🔟 Kitchen & Bath - Kitchen Cabinets", "🔟 Kitchen & Bath - Bathroom Fixtures", "🔟 Kitchen & Bath - Countertops", 
        "🔟 Kitchen & Bath - Storage Systems",
        "11️⃣ Interior - Flooring", "11️⃣ Interior - Paint", "11️⃣ Interior - Coatings", "11️⃣ Interior - Wall Systems", 
        "11️⃣ Interior - Ceilings", "11️⃣ Interior - Trim", "11️⃣ Interior - Molding",
        "12️⃣ Outdoor - Composite Decking", "12️⃣ Outdoor - Wood Decking", "12️⃣ Outdoor - Railings", "12️⃣ Outdoor - Pergolas", 
        "12️⃣ Outdoor - Gazebos", "12️⃣ Outdoor - Outdoor Kitchens",
        "13️⃣ Landscape - Pavers", "13️⃣ Landscape - Retaining Walls", "13️⃣ Landscape - Irrigation", "13️⃣ Landscape - Greenhouses",
        "14️⃣ Materials - Aluminum Products", "14️⃣ Materials - Steel Products", "14️⃣ Materials - Extrusions", 
        "14️⃣ Materials - Stone", "14️⃣ Materials - Masonry", "14️⃣ Materials - Glass Systems",
        "15️⃣ Software - Construction Software", "15️⃣ Software - Estimating Tools", "15️⃣ Software - Permit Platforms", 
        "15️⃣ Software - Advisory Services", "15️⃣ Software - Financing Platforms", "15️⃣ Software - Web Development"
    ]
    AVAILABLE_PRODUCTS = FLAT_CATEGORIES_DETAILED

    # --- Sidebar Filters ---
    st.sidebar.markdown("---")

    st.sidebar.title("🔍 Filters & Search")
    search_query = st.sidebar.text_input("Search (Booth, Name...)", "")

    st.sidebar.markdown("### Status Filters")
    visited_only = st.sidebar.checkbox("✅ Visited Only", False)
    min_priority = st.sidebar.slider("🔥 Minimum Priority (1-5)", min_value=1, max_value=5, value=1)

    st.sidebar.markdown("### Content Filters")
    has_notes = st.sidebar.checkbox("📝 Has Manual Notes", False)
    has_email = st.sidebar.checkbox("📧 Received Email", False)

    # --- Fetch Data (Pre-Filter) ---
    try:
        with st.spinner("Katalog yükleniyor..."):
            companies = get_companies(
                search_query=search_query,
                visited_only=visited_only,
                min_priority=min_priority,
                has_notes=has_notes,
                has_email=has_email
            )
            # PHASE 5: Build Global Tag Registry dynamically from active DB items
            dynamic_tags = sorted(list(set(tag for c in companies for tag in (c.get('tags') or []))))
            
    except Exception as e:
        import traceback
        st.error(f"Veritabanı bağlantı hatası: {e}")
        st.code(traceback.format_exc())
        st.stop()

    st.sidebar.markdown("### Category Filters")
    selected_segment = st.sidebar.selectbox("📂 Segment / Product Group", AVAILABLE_SEGMENTS, index=0)
    # Use dynamic tags ensuring nothing is hidden
    selected_tag_filter = st.sidebar.selectbox("🏷️ Company Tag", ["All"] + dynamic_tags, index=0)
    selected_product_filter = st.sidebar.selectbox("📦 Product", ["All"] + AVAILABLE_PRODUCTS, index=0)

    st.sidebar.markdown("---")
    st.sidebar.info("Upload marketing emails via the Webhook or add them directly here.")

    # --- Apply Post-Filters (Python-side) ---
    if selected_segment != "All":
        companies = [c for c in companies if c.get('segment') == selected_segment]
    
    if selected_tag_filter != "All":
        companies = [c for c in companies if c.get('tags') and selected_tag_filter in c['tags']]
    
    if selected_product_filter != "All":
        companies = [c for c in companies if c.get('products') and selected_product_filter in c['products']]

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
                        if new_web != comp.get('website'):
                            # Ensure https:// prefix so the link actually opens
                            if new_web and not new_web.startswith('http'):
                                new_web = 'https://' + new_web
                            updates['website'] = new_web
                    
                        if updates:
                            update_company(comp['id'], **updates)
                            st.success("Tüm bilgiler kaydedildi! (Sayfa yenileniyor...)")
                            st.rerun()
            
                if comp.get('website'):
                    url = comp['website'] if comp['website'].startswith('http') else 'https://' + comp['website']
                    st.markdown(f"🔗 <a href='{url}' target='_blank'>Ziyaret Et / Visit</a>", unsafe_allow_html=True)
            
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
                    # Load current values
                    current_tags = comp.get('tags') or []
                    current_products = comp.get('products') or []

                # ── Görsel Etiketler & Agentic Asistan (Phase 4) ──────────────────
                st.markdown("---")
                
                # Smart Agent Proactive Warnings
                # Check current activities roughly by looking at global lists (or making a small query if needed, but we avoid too many queries)
                notes_data = get_notes(comp['id'])
                emails = [n for n in notes_data if n.get('type') == 'email']
                tasks = [n for n in notes_data if n.get('type') in ('task', 'To Do', 'In Progress')]
                
                warning_col, tag_col = st.columns([0.6, 0.4])
                
                with warning_col:
                    st.markdown("### 🤖 Otonom Asistan")
                    needs_attention = False
                    
                    if emails and not tasks:
                        st.warning("⚠️ **E-posta Alındı:** Müşteriden email var ancak planlanmış bir görev/aksiyon bulunmuyor.")
                        needs_attention = True
                    if comp.get('priority', 1) >= 4 and not comp.get('visited'):
                        st.error("🔥 **Kritik Ziyaret:** Önceliği çok yüksek ancak henüz standına gidilmedi!")
                        needs_attention = True
                    if not emails and not notes_data:
                        st.info("💡 Henüz hiç etkileşim yok. Tanışma maili atmak ister misiniz?")
                        needs_attention = True
                    if not needs_attention:
                        st.success("✨ Her şey yolunda, bu firma için bekleyen acil durum yok.")
                        
                    # Phase 4: Mail Drafter
                    if st.button("✍️ Taslak E-posta (Follow-up) Oluştur", key=f"draft_{comp['id']}"):
                        with st.spinner("AI iletişim geçmişini analiz ediyor..."):
                            try:
                                from openai import OpenAI
                                import os
                                api_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY"))
                                if api_key:
                                    client = OpenAI(api_key=api_key)
                                    ctx = f"Firma: {comp.get('company_name', '')}\\nSegment: {comp.get('segment', '')}\\n"
                                    if emails: ctx += f"Son Email: {emails[0]['content'][:400]}\\n"
                                    
                                    prompt = f"Sen profesyonel bir fuar asistanısın. Bu firma için kısa, etkili ve dönüş odaklı bir takip (follow-up) e-postası taslakla. Metin referans verileri:\\n{ctx}"
                                    resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], temperature=0.7)
                                    st.session_state[f"mail_draft_{comp['id']}"] = resp.choices[0].message.content.strip()
                            except Exception as e:
                                st.error(f"Taslak oluşturulamadı: {e}")

                    if st.session_state.get(f"mail_draft_{comp['id']}"):
                        st.text_area("Mail Taslağınız:", st.session_state[f"mail_draft_{comp['id']}"], height=150, key=f"draft_txt_{comp['id']}")
                        import urllib.parse
                        subject = urllib.parse.quote(f"IBS Fuarı Görüşmemiz - {comp.get('company_name', '')}")
                        body = urllib.parse.quote(st.session_state[f"mail_draft_{comp['id']}"])
                        st.markdown(f"<a href='mailto:?subject={subject}&body={body}' target='_blank'><button style='padding: 5px 10px; border-radius: 5px; background-color: #0078D4; color: white; border: none; cursor: pointer;'>📧 Outlook/Mail'de Aç ve Gönder</button></a>", unsafe_allow_html=True)

                    # Phase 4 Retroactive Categorizer
                    manual_notes = [n for n in notes_data if n.get('type') in ('note', 'manual')]
                    if manual_notes:
                        if st.button("🔍 Mevcut Notları Tara & Kategorilendir", use_container_width=True, key=f"scan_old_{comp['id']}"):
                            with st.spinner("Geçmiş notlar okunuyor..."):
                                try:
                                    from openai import OpenAI
                                    import os, json
                                    api_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY"))
                                    if api_key:
                                        client = OpenAI(api_key=api_key)
                                        combined_text = "\\n".join([n.get('content', '') for n in manual_notes])
                                        
                                        prompt = f"""Ekteki notlar IBS inşaat fuarından alınmıştır. Lütfen bu şirketin notlarında geçen tüm inşaat/yapı ürünlerini analiz edin.
ÖNEMLİ: Notların dili İngilizce, Türkçe veya karışık olabilir. Sizin göreviniz metnin özünü anlayıp (örn: "wooden stair parts, balusters" -> "Interior Finishes - Trim" veya "Molding", "alüminyum" -> "Aluminum Products"), KATEGORİLER listesinden EN ALAKALI, UYGUN VE GENİŞ kategorileri bularak eşleştirmektir. Ürün listemizde metindeki ürünün alt kümesi veya üst kümesi varsa bile onu seçebilirsiniz. Tek şart: Seçtiğiniz isimler bu KATEGORİLER listesindekilerle BİREBİR YAZILIŞTA aynı olmalıdır.
                                        
KATEGORİLER:
{FLAT_CATEGORIES_DETAILED}

SADECE JSON FORMATINDA YANIT VER:
{{
  "detected_categories": ["KATEGORİLER listesinden birebir aynı formatta isimler"]
}}

Notlar: {combined_text}"""
                                        resp = client.chat.completions.create(
                                            model="gpt-4o-mini",
                                            response_format={ "type": "json_object" },
                                            messages=[{"role": "user", "content": prompt}],
                                            temperature=0.1
                                        )
                                        result = json.loads(resp.choices[0].message.content)
                                        valid_cats = [c for c in result.get('detected_categories', []) if c in FLAT_CATEGORIES_DETAILED]
                                        st.session_state[f"retro_cats_{comp['id']}"] = valid_cats
                                except Exception as e:
                                    st.error(f"Tarama hatası: {e}")
                                    
                        if st.session_state.get(f"retro_cats_{comp['id']}") is not None:
                            detected = st.session_state[f"retro_cats_{comp['id']}"]
                            if detected:
                                st.info("Eski notlarda şu kategoriler bulundu:\\n- " + "\\n- ".join(detected))
                                new_prods = [d for d in detected if d not in current_products]
                                if new_prods:
                                    if st.button(f"✅ Hepsini Firmaya Ekle ({len(new_prods)} Yeni)", type="primary", key=f"add_retro_{comp['id']}"):
                                        merged = list(set(current_products + new_prods))
                                        update_company(comp['id'], products=merged)
                                        st.toast("Kategoriler genişletildi!", icon="📦")
                                        # Clear widget state to force multiselect to reflect new DB values
                                        for key_to_clear in [f"prod_edit_{comp['id']}", f"tags_edit_{comp['id']}"]:
                                            if key_to_clear in st.session_state:
                                                del st.session_state[key_to_clear]
                                        st.session_state[f"retro_cats_{comp['id']}"] = None
                                        st.rerun()
                                else:
                                    st.success("Tüm bulunan ürünler zaten firmanın kataloğuna eklenmiş.")
                            else:
                                st.warning("Eski notlarda yeni bir ürün veya kategori eşleşmesi bulunamadı.")


                with tag_col:
                    st.markdown("### 🏷️ Kategori & Ürünler")
                    current_tags = comp.get('tags') or []
                    current_products = comp.get('products') or []
                    
                    # PHASE 6: Instant Interactive Tagging Arrays
                    # We define callbacks that immediately save when the user clicks 'x' or adds a tag.
                    def instant_tag_save(cid):
                        new_tags = st.session_state[f"inst_tags_{cid}"]
                        update_company(cid, tags=new_tags)
                    
                    def instant_prod_save(cid):
                        new_prods = st.session_state[f"inst_prod_{cid}"]
                        update_company(cid, products=new_prods)

                    all_tag_opts = list(set(AVAILABLE_TAGS + current_tags + dynamic_tags))
                    
                    # OPTIMISTIC UI FIX: Merge db tags with temporary session tags to beat DB lag natively
                    if f"temp_tg_{comp['id']}" in st.session_state:
                        temp_tg = st.session_state[f"temp_tg_{comp['id']}"]
                        if temp_tg not in current_tags:
                            current_tags.append(temp_tg)
                            
                    if f"temp_list_tg_{comp['id']}" in st.session_state:
                        for tmptg in st.session_state[f"temp_list_tg_{comp['id']}"]:
                            if tmptg not in current_tags:
                                current_tags.append(tmptg)

                    all_tag_opts = list(set(AVAILABLE_TAGS + current_tags + dynamic_tags))
                    
                    st.multiselect(
                        "📌 Şirket Etiketleri (Silmek için ❌ basın)", 
                        options=all_tag_opts, 
                        default=current_tags, 
                        key=f"inst_tags_{comp['id']}",
                        on_change=instant_tag_save,
                        args=(comp['id'],)
                    )
                    
                    st.multiselect(
                        "📦 Ürün Kategorileri", 
                        options=list(set(FLAT_CATEGORIES_DETAILED + current_products)), 
                        default=current_products, 
                        key=f"inst_prod_{comp['id']}",
                        on_change=instant_prod_save,
                        args=(comp['id'],)
                    )
                    
                    custom_tag = st.text_input("➕ Yeni Özgün Etiket Ekle (Enter'a basın):", placeholder="#VIP, #TeklifBekliyor", key=f"custom_tag_{comp['id']}")
                    if custom_tag:
                        clean_tag = custom_tag.strip().title()
                        if not clean_tag.startswith('#'):
                            clean_tag = '#' + clean_tag
                            
                        if clean_tag not in current_tags:
                            merged_tags = current_tags + [clean_tag]
                            update_company(comp['id'], tags=merged_tags)
                            
                            # Optimistically store new tag, clear widget memory to force re-evaluating default
                            st.session_state[f"temp_tg_{comp['id']}"] = clean_tag
                            if f"inst_tags_{comp['id']}" in st.session_state:
                                del st.session_state[f"inst_tags_{comp['id']}"]
                                
                        # ALWAYS clear text input to prevent it from getting stuck on UI, then reload
                        st.session_state[f"custom_tag_{comp['id']}"] = ""
                        st.rerun()

            
                # Content Tabs
                tab1, tab2, tab3, tab4 = st.tabs(["📝 Notes", "📂 Attachments", "📧 History", "👤 Contacts & OCR"])
            
            
                # TAB 1: Notes & Intelligence
                with tab1:
                    def render_notes_fragment(comp):
                        ai_cols = st.columns(4)
                        with ai_cols[0]:
                            if st.button("🗂️ Toplantı Brifingi", help="Bu firma ile görüşmeden önce bilinmesi gerekenlerin özetini çıkarır.", use_container_width=True, key=f"ai_brief_{comp['id']}"):
                                st.session_state[f"run_ai_brief_{comp['id']}"] = True
                        with ai_cols[1]:
                            if st.button("✏️ AI Not Asistanı", help="Kabataslak notunuzu IBS formatına (#etiket @kişi) çevirir.", use_container_width=True, key=f"ai_note_{comp['id']}"):
                                st.session_state[f"show_ai_note_{comp['id']}"] = not st.session_state.get(f"show_ai_note_{comp['id']}", False)
                        with ai_cols[2]:
                            if st.button("⚡ Takip Listesi", help="Tüm notlardan çıkarılan aksiyonları listeler.", use_container_width=True, key=f"ai_tasks_{comp['id']}"):
                                st.session_state[f"run_ai_tasks_{comp['id']}"] = True
                        with ai_cols[3]:
                            if st.button("🏷️ AI Etiket Öner", help="Mevcut notları analiz edip firmaya özel YENİ etiketler önerir.", use_container_width=True, key=f"ai_tags_btn_{comp['id']}"):
                                st.session_state[f"show_ai_tags_{comp['id']}"] = not st.session_state.get(f"show_ai_tags_{comp['id']}", False)

                        st.markdown("---")

                        notes = get_notes(comp['id'])

                        # 1. AI Not Asistanı UI
                        if st.session_state.get(f"show_ai_note_{comp['id']}", False):
                            with st.container(border=True):
                                st.markdown("🤖 **Akıllı Not Asistanı**")
                                raw_note = st.text_area("Kabataslak notunuzu yazın:", key=f"raw_note_{comp['id']}", height=100)
                            
                                col_n1, col_n2 = st.columns(2)
                                with col_n1:
                                    if st.button("✨ Analiz Et ve Formatla", use_container_width=True, key=f"format_btn_{comp['id']}"):
                                        if raw_note:
                                            with st.spinner("AI ürünleri tarıyor ve notu formatlıyor..."):
                                                try:
                                                    from openai import OpenAI
                                                    import os
                                                    import json
                                                    api_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY"))
                                                    if api_key:
                                                        client = OpenAI(api_key=api_key)
                                                        prompt = f"""Sen profesyonel bir B2B Fuar asistanısın. Aşağıdaki ham ürün notunu IBS fuar formatına uygun şekilde (önemliyse #acil, kişi varsa @isim) temiz ve maddeler halinde düzenle.
Aynı zamanda notta bahsedilen inşaat/yapı ürünlerini analiz et. ÖNEMLİ: Kullanıcının notu İngilizce, Türkçe veya karışık olabilir. Lütfen cümlenin anlamını ve bağlamını analiz ederek, bahsedilen ürünleri (örn: Ahşap merdiven parçaları, stair parts, balusters -> "11️⃣ Interior Finishes - Trim" veya "11️⃣ Interior Finishes - Molding" vb.) aşağıdaki KATEGORİLER listesinden EN YAKIN VE EN MANTIKLI olan geniş kategorilerle eşleştir. Kusursuz nokta atışı olmak zorunda değil, doğru bağlamdaki en yakın kategoriyi seçebilirsin. Tek şart: Seçtiğin isimler AŞAĞIDAKİ LİSTEDEN kopyalanmış BİREBİR AYNI karakter formatında olmalıdır.

KATEGORİLER:
{FLAT_CATEGORIES_DETAILED}

LÜTFEN SADECE AŞAĞIDAKİ JSON FORMATINDA YANIT VER:
{{
  "formatted_note": "Düzenlenmiş, net ve sektörel not metni",
  "detected_categories": ["KATEGORİLER listesinden birebir aynı formatta kopyalanmış en alakalı isimler"]
}}

Not: {raw_note}"""

                                                        resp = client.chat.completions.create(
                                                            model="gpt-4o-mini",
                                                            response_format={ "type": "json_object" },
                                                            messages=[
                                                                {"role": "system", "content": "You are a helpful assistant that strictly outputs JSON."},
                                                                {"role": "user", "content": prompt}
                                                            ],
                                                            temperature=0.1
                                                        )
                                                        
                                                        result = json.loads(resp.choices[0].message.content)
                                                        st.session_state[f"fmt_note_{comp['id']}"] = result.get('formatted_note', '').strip()
                                                        
                                                        # Validate detected categories strictly against known list
                                                        valid_cats = [c for c in result.get('detected_categories', []) if c in FLAT_CATEGORIES_DETAILED]
                                                        st.session_state[f"det_cats_{comp['id']}"] = valid_cats
                                                except Exception as e:
                                                    st.error(f"Hata: {e}")
                            
                                with col_n2:
                                    if st.session_state.get(f"fmt_note_{comp['id']}"):
                                        final_note = st.text_area("Kaydedilecek Not:", value=st.session_state[f"fmt_note_{comp['id']}"], key=f"final_n_{comp['id']}")
                                        detected = st.session_state.get(f"det_cats_{comp['id']}", [])
                                        
                                        if detected:
                                            st.info(f"AI Eşleştirmesi ({len(detected)} ürün grubu): " + ", ".join(detected))
                                            btn_text = "💾 Kaydet & Formata Ekle"
                                        else:
                                            btn_text = "💾 Sadece Notu Kaydet"
                                            
                                        if st.button(btn_text, type="primary", use_container_width=True, key=f"save_ai_note_{comp['id']}"):
                                            extracted_tags = add_note(comp['id'], final_note, note_type="manual", company_name=comp['company_name'])
                                            if extracted_tags:
                                                st.session_state[f"temp_list_tg_{comp['id']}"] = extracted_tags
                                            
                                            # Merge categories into company profile
                                            if detected:
                                                curr = comp.get('products') or []
                                                merged = list(set(curr + detected))
                                                if set(merged) != set(curr):
                                                    update_company(comp['id'], products=merged)
                                                    st.toast("Ürün kataloğu da otomatik genişletildi! 📦", icon="✅")
                                                    
                                            # CLEAR inst_* widgets so they redraw with fresh DB data natively
                                            for key_to_clear in [f"inst_prod_{comp['id']}", f"inst_tags_{comp['id']}"]:
                                                if key_to_clear in st.session_state:
                                                    del st.session_state[key_to_clear]
                                                    
                                            st.toast("İşlem Başarılı!", icon="✅")
                                        
                                            st.session_state[f"show_ai_note_{comp['id']}"] = False
                                            st.session_state[f"fmt_note_{comp['id']}"] = ""
                                            st.session_state[f"det_cats_{comp['id']}"] = []
                                            st.rerun()

                        # 1.5. AI Etiket Önerisi (Feature 8)
                        if st.session_state.get(f"show_ai_tags_{comp['id']}", False):
                            with st.container(border=True):
                                st.markdown("🤖 **Akıllı Etiket Önerisi**")
                                all_text = "\\n".join([n['content'] for n in notes if n['content']])
                                
                                if len(all_text.strip()) < 10:
                                    st.info("Bu firma için yeterli not veya email içeriği bulunmuyor. Lütfen önce biraz veri girin.")
                                else:
                                    if st.button("✨ Notları Oku ve Öner", use_container_width=True, key=f"gen_tags_{comp['id']}"):
                                        with st.spinner("Notlar analiz ediliyor ve benzersiz etiketler üretiliyor..."):
                                            try:
                                                from openai import OpenAI
                                                import os, json
                                                api_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY"))
                                                if api_key:
                                                    client = OpenAI(api_key=api_key)
                                                    prompt = (
                                                        f"Sen B2B fuarında görüşülen firmaların yeteneklerini sınıflandıran bir veri analistisin.\\n"
                                                        f"Aşağıdaki notlar {comp['company_name']} firmasına aittir:\\n{all_text}\\n\\n"
                                                        f"Şu anki etiketleri şunlar: {current_tags}. BUNLARI KESİNLİKLE TEKRAR ÖNERME.\\n"
                                                        f"Lütfen firmanın iş modelini, sektörünü ve odak noktasını tanımlayan 3 ila 6 TANE YENİ, kilit kelime niteliğinde etiket öner (örn: #MimariGlass, #Toptancı, #WoodSupply).\\n"
                                                        f"Etiketler mutlaka '#' işaretiyle başlamalı, boşluk içermemeli ve CamelCase formatında olmalıdır.\\n"
                                                    )
                                                    resp = client.chat.completions.create(
                                                        model="gpt-4o-mini",
                                                        response_format={ "type": "json_object" },
                                                        messages=[
                                                            {"role": "system", "content": "You are a helpful assistant that strictly outputs JSON with the format {'suggested_tags': ['#Tag1', '#Tag2']}."},
                                                            {"role": "user", "content": prompt}
                                                        ],
                                                        temperature=0.3
                                                    )
                                                    res = json.loads(resp.choices[0].message.content)
                                                    safe_sugg = [str(t) for t in res.get('suggested_tags', []) if str(t) not in current_tags]
                                                    st.session_state[f"sugg_tags_{comp['id']}"] = safe_sugg
                                            except Exception as e:
                                                st.error(f"Hata: {e}")
                                            
                                    if st.session_state.get(f"sugg_tags_{comp['id']}"):
                                        sugg_opts = st.session_state[f"sugg_tags_{comp['id']}"]
                                        sel_tags = st.multiselect("Önerilen Yeni Etiketler (İsteğinize göre seçimleri daraltabilirsiniz):", options=sugg_opts, default=sugg_opts, key=f"sel_sugg_{comp['id']}")
                                        if st.button("💾 Seçilileri Firmaya Ekle", type="primary", use_container_width=True, key=f"save_sugg_{comp['id']}"):
                                            merged_tags = list(set(current_tags + sel_tags))
                                            update_company(comp['id'], tags=merged_tags)
                                            
                                            # Optimistically inject tags into UI immediately
                                            if sel_tags:
                                                st.session_state[f"temp_list_tg_{comp['id']}"] = sel_tags
                                                
                                            # Flush cache natively to prevent stale Streamlit Multiselect UI state natively
                                            for key_tgt in [f"inst_tags_{comp['id']}", f"sugg_tags_{comp['id']}"]:
                                                if key_tgt in st.session_state:
                                                    del st.session_state[key_tgt]
                                            st.session_state[f"show_ai_tags_{comp['id']}"] = False
                                            st.success("Yeni etiketler başarıyla entegre edildi!")
                                            st.rerun()

                        # 2. Toplantı Brifingi İşlemi
                        if st.session_state.get(f"run_ai_brief_{comp['id']}"):
                            with st.container(border=True):
                                st.markdown("🗂️ **Toplantı Brifingi**")
                                with st.spinner("Notlar ve emailler analiz ediliyor..."):
                                    try:
                                        from openai import OpenAI
                                        import os
                                        api_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY"))
                                        if api_key:
                                            client = OpenAI(api_key=api_key)
                                        
                                            all_text = "\n".join([n['content'] for n in notes])
                                            prompt = (
                                                f"Sen bir fuar asistanısın. {comp['company_name']} firmasıyla toplantıya gireceğim.\n"
                                                f"Aşağıdaki geçmiş notlar ve emaillere bakarak bana 3 maddelik çok kısa bir özet (brifing) çıkar.\n"
                                                f"Nelere dikkat etmeliyim, açıkta kalan konular neler?\n\nVeri: {all_text}"
                                            )
                                            resp = client.chat.completions.create(
                                                model="gpt-4o-mini",
                                                messages=[{"role": "user", "content": prompt}],
                                                temperature=0.4
                                            )
                                            st.markdown(resp.choices[0].message.content.strip())
                                            if st.button("Kapat", key=f"close_brief_{comp['id']}"):
                                                st.session_state[f"run_ai_brief_{comp['id']}"] = False
                                                st.rerun()
                                    except Exception as e:
                                        st.error(f"Hata: {e}")

                        # 3. Takip Listesi İşlemi
                        if st.session_state.get(f"run_ai_tasks_{comp['id']}"):
                            with st.container(border=True):
                                st.markdown("⚡ **Önerilen Takip Aksiyonları**")
                                with st.spinner("Görevler güncelleniyor..."):
                                    try:
                                        from openai import OpenAI
                                        import os
                                        api_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY"))
                                        if api_key:
                                            client = OpenAI(api_key=api_key)
                                        
                                            all_text = "\n".join([n['content'] for n in notes])
                                            prompt = (
                                                f"Bu firmanın notlarından çıkarılması gereken SOMUT GÖREVLER listesi oluştur.\n"
                                                f"Eğer notta görev yoksa 'Görev bulunamadı' yaz. "
                                                f"Madde imi olarak '-' kullan.\n\nNotlar: {all_text}"
                                            )
                                            resp = client.chat.completions.create(
                                                model="gpt-4o-mini",
                                                messages=[{"role": "user", "content": prompt}],
                                                temperature=0.3
                                            )
                                            st.markdown(resp.choices[0].message.content.strip())
                                            if st.button("Kapat", key=f"close_tasks_{comp['id']}"):
                                                st.session_state[f"run_ai_tasks_{comp['id']}"] = False
                                                st.rerun()
                                    except Exception as e:
                                        st.error(f"Hata: {e}")

                        st.markdown("---")

                        # --- EMAILS SEKTION ---
                        emails = [n for n in notes if n['type'] == 'email']
                        if emails:
                            with st.expander(f"📥 Bu Firmadan Gelen Emailler ({len(emails)} Adet)", expanded=True):
                                sorted_emails = sorted(emails, key=lambda x: x['created_at'], reverse=True)
                                for em in sorted_emails:
                                    date_str = datetime.datetime.fromisoformat(em['created_at'].replace('Z', '+00:00')).strftime("%Y-%m-%d %H:%M")
                                    
                                    # Native Mailto Logic for Replying
                                    import urllib.parse
                                    email_target = comp.get('email')
                                    if not email_target:
                                        # Fallback to general domain info if raw email is empty
                                        email_target = f"info@{comp.get('primary_domain', '')}" if comp.get('primary_domain') else ""
                                        
                                    subj = urllib.parse.quote(f"Re: Fuar Görüşmemiz ({comp['company_name']})")
                                    short_preview = em['content'][:500] if len(em['content']) > 500 else em['content']
                                    body = urllib.parse.quote(f"\\n\\n---\\nGeçmiş Email Kaydı:\\n{short_preview}")
                                    mailto_link = f"mailto:{email_target}?subject={subj}&body={body}"
                                    
                                    st.markdown(f"""
                                    <div class="note-box" style="border-left: 4px solid #3B82F6; background-color: #F8FAFC; margin-bottom: 10px; position: relative;">
                                        <small style="color:#64748b;">📧 <b>Gelen Kutu</b> | {date_str}</small>
                                        <a href="{mailto_link}" target="_blank" style="position: absolute; right: 10px; top: 10px; background-color: #3B82F6; color: white; padding: 4px 12px; border-radius: 6px; text-decoration: none; font-size: 0.85em; font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">↪ Yanıtla (Email Aç)</a><br>
                                        <div style="font-size: 0.9em; white-space: pre-wrap; margin-top: 10px; color: #334155;">{em['content']}</div>
                                    </div>
                                    """, unsafe_allow_html=True)
                        else:
                            st.info("Bu firma ile henüz eşleşmiş bir email yok. Sağ üstteki + Butonundan ekleyebilirsiniz.")
                            
                        st.markdown("---")

                        # Standart Manuel Not Ekleme
                        with st.expander("➕ Hızlı Not Ekle"):
                            new_note = st.text_area("Notunuzu yazın:", key=f"note_input_{comp['id']}")
                            if st.button("Kaydet", key=f"save_note_{comp['id']}"):
                                extracted_tags = add_note(comp['id'], new_note, note_type="manual", company_name=comp['company_name'])
                                if extracted_tags:
                                    st.session_state[f"temp_list_tg_{comp['id']}"] = extracted_tags
                                
                                st.success("Note saved!")
                                # If the note contained hashtags, the DB tags were updated. We must flush the old multiselect state!
                                if f"inst_tags_{comp['id']}" in st.session_state:
                                    del st.session_state[f"inst_tags_{comp['id']}"]
                                st.rerun()
                
                        # Manuel Notları kronolojik listele
                        manual_notes = [n for n in notes if n['type'] != 'email']
                        sorted_notes = sorted(manual_notes, key=lambda x: x['created_at'], reverse=True)
                    
                        for n in sorted_notes:
                            date_str = datetime.datetime.fromisoformat(n['created_at'].replace('Z', '+00:00')).strftime("%Y-%m-%d %H:%M")
                        
                            col_note, col_del = st.columns([0.85, 0.15])
                            with col_note:
                                st.markdown(f"""
                                <div class="note-box">
                                    <small style="color:#555;">📝 {date_str}</small><br>
                                    {n['content']}
                                </div>
                                """, unsafe_allow_html=True)
                            with col_del:
                                if st.button("🗑️", key=f"del_note_{n['id']}"):
                                    delete_note(n['id'])
                                    st.rerun()

                    render_notes_fragment(comp)

                    # TAB 2: Attachments / Media
                with tab2:
                    st.info("📦 **Dosyalar Google Drive'a Yüklenecektir** (IBS_2026_Gallery)")
                
                    # Check for existing Google Drive folder for this company or just use a main folder
                    # We'll put everything in one main folder or subfolders, let's use: IBS_2026_Gallery / [Booth]_[Name]
                
                    upload_mode = st.radio(
                        "Kaynak Seç",
                        ["📁 Dosya Yükle", "📷 Kameradan Çek"],
                        horizontal=True,
                        key=f"up_mode_{comp['id']}"
                    )

                    uploaded_files = []
                    if upload_mode == "📁 Dosya Yükle":
                        uploaded_files = st.file_uploader(
                            "Katalog veya Fotoğraf Yükle (Çoklu Seçim)",
                            type=['png', 'jpg', 'jpeg', 'pdf'],
                            key=f"file_{comp['id']}",
                            accept_multiple_files=True
                        ) or []
                    else:
                        cam_img = st.camera_input("📷 Fotoğraf Çek", key=f"cam_{comp['id']}")
                        if cam_img:
                            uploaded_files = [cam_img]

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
                    notes = get_notes(comp['id'])
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
                             if st.button("🤖 Gemini ile Kartviziti Tara", key=f"run_ocr_{comp['id']}", type="primary"):
                                 with st.spinner("Gemini kartviziti analiz ediyor..."):
                                     try:
                                         from openai import OpenAI
                                         import base64
                                         api_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY"))
                                         client = OpenAI(api_key=api_key)
                                         
                                         img_bytes = ocr_img.getvalue()
                                         encoded_img = base64.b64encode(img_bytes).decode("utf-8")
                                         
                                         prompt = (
                                             "Bu bir kartvizit fotoğrafıdır. Tüm metni oku ve yapılandırılmış bilgileri çıkar.\n"
                                             "Şu formatta yanıtla (her satır ayrı):\n"
                                             "AD_SOYAD: <kişinin tam adı>\n"
                                             "UNVAN: <pozisyon/ünvan>\n"
                                             "SIRKET: <şirket adı>\n"
                                             "EMAIL: <e-posta adresi>\n"
                                             "TELEFON: <telefon numarası>\n"
                                             "WEB: <website>\n"
                                             "ADRES: <adres varsa>\n"
                                             "HAM_METIN: <kartvizitteki tüm metin>"
                                         )
                                         response = client.chat.completions.create(
                                             model="gpt-4o",
                                             messages=[{
                                                 "role": "user",
                                                 "content": [
                                                     {"type": "text", "text": prompt},
                                                     {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_img}"}}
                                                 ]
                                             }],
                                             max_tokens=600
                                         )
                                         raw_ocr_text = response.choices[0].message.content.strip()
                                         st.session_state[f"ocr_result_{comp['id']}"] = raw_ocr_text
                                         
                                         # Yapılandırılmış alanları parse et ve form'a otomatik doldur
                                         import re
                                         def ge(text, key):
                                             m = re.search(r'(?:^|\n)' + re.escape(key) + r'[:\s]+(.+)', text, re.IGNORECASE)
                                             return m.group(1).strip() if m else ""
                                         
                                         st.session_state[f"ocr_name_{comp['id']}"]  = ge(raw_ocr_text, "AD_SOYAD")
                                         st.session_state[f"ocr_title_{comp['id']}"] = ge(raw_ocr_text, "UNVAN")
                                         st.session_state[f"ocr_email_{comp['id']}"] = ge(raw_ocr_text, "EMAIL")
                                         st.session_state[f"ocr_phone_{comp['id']}"] = ge(raw_ocr_text, "TELEFON")
                                         
                                         # ── Google Drive'a yükle ──
                                         try:
                                             comp_name_safe = comp.get('company_name', 'Firma').replace('/', '-')[:40]
                                             folder_name = f"{comp_name_safe} - Kartvizitler"
                                             folder_id = find_or_create_folder(folder_name)
                                             
                                             ext = ocr_img.name.split('.')[-1] if hasattr(ocr_img, 'name') else 'jpg'
                                             fname = f"kartvizit_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
                                             
                                             gdrive_web_link, gdrive_file_id, _ = upload_file_to_drive(
                                                 file_bytes=img_bytes,
                                                 filename=fname,
                                                 mime_type=f"image/{ext}",
                                                 folder_id=folder_id
                                             )
                                             if gdrive_file_id:
                                                 db_url = f"{gdrive_web_link}#id={gdrive_file_id}#tags=kartvizit"
                                                 upload_attachment(comp['id'], db_url, "image")
                                                 st.success(f"✅ Kartvizit okundu ve Drive'a yüklendi! Sağdaki formu kontrol edin.")
                                             else:
                                                 st.success("✅ Kartvizit okundu! Sağdaki formu kontrol edin.")
                                         except Exception as drive_err:
                                             st.success("✅ Kartvizit okundu! (Drive yükleme hatası: " + str(drive_err) + ")")
                                     except Exception as e:
                                         st.error(f"Gemini OCR hatası: {e}")
                         
                         if f"ocr_result_{comp['id']}" in st.session_state:
                             with st.expander("📄 Ham OCR Metni"):
                                 st.text(st.session_state[f"ocr_result_{comp['id']}"])

                         
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




    # --- Admin Section for Database Reset (outside company loop) ---
    st.sidebar.markdown("---")
    st.sidebar.title("⚙️ Admin Tools")
    if st.sidebar.button("🔄 Reset & Seed Database (Danger)"):
        with st.spinner("Flushing old data and importing clean Excel..."):
            seed_companies("ibs_2026_all_exhibitors_clean.xlsx")
            st.success("Database successfully reset to clean version! Refresh the page.")

elif app_mode == "Medya Kütüphanesi":
    from views.gallery import show_gallery
    show_gallery()
elif app_mode == "🧠 İstihbarat Merkezi":
    from views.intelligence_hub import show_intelligence_hub
    show_intelligence_hub()
