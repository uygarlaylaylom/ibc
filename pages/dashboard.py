import streamlit as st
import pandas as pd
import re
from typing import List, Dict, Any
import datetime

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from supabase_utils import get_supabase
from tasks_module.repository import get_all_tasks, update_task_status, bulk_update_tasks, insert_task
from tasks_module.parser import parse_and_create_task

st.set_page_config(page_title="IBC İstihbarat", layout="wide", initial_sidebar_state="expanded")

# CUSTOM CSS FOR STYLING (HIDING SCROLLBARS, TWEAKING STYLES)
st.markdown("""
<style>
    /* Styling mentions and hashtags */
    .mention { color: #4F46E5; font-weight: 600; cursor: pointer; text-decoration: none; }
    .mention:hover { text-decoration: underline; }
    .hashtag { background-color: #E2E8F0; color: #475569; padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; margin-right: 4px; display: inline-block;}
    .priority-high { background-color: #FEE2E2; color: #EF4444; padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: bold;}
    .priority-normal { background-color: #DBEAFE; color: #3B82F6; padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: bold;}
    .priority-low { background-color: #DCFCE7; color: #22C55E; padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: bold;}
    .breadcrumb { font-size: 0.875rem; color: #64748B; margin-bottom: 1rem;}
    .task-category { font-size: 0.75rem; color: #94A3B8; margin-top: -8px; margin-bottom: 8px;}
    .stat-card-value { font-size: 1.875rem; font-weight: 700; }
    
    /* Make exact streamlit columns for Kanban scrollable instead of whole page if they get too long */
    [data-testid="column"] { overflow-y: auto; overflow-x: hidden; }
</style>
""", unsafe_allow_html=True)

def get_client_safely():
    if "supabase_client" not in st.session_state:
        st.session_state.supabase_client = get_supabase()
    return st.session_state.supabase_client

# Fetch Data
all_tasks = get_all_tasks(get_client_safely())

# ==========================================================
# 2. SOL KENAR ÇUBUĞU (SIDEBAR / TAXONOMY EXPLORER)
# ==========================================================
with st.sidebar:
    st.markdown("### 🏢 IBC İstihbarat")
    search_query = st.text_input("🔍 Kategorilerde veya firmalarda ara...")
    st.divider()
    
    st.markdown("#### Ürün Grupları Gezgini")
    
    # State for selected category
    if "selected_category" not in st.session_state:
        st.session_state.selected_category = "Tüm Kategoriler"
        
    def select_cat(cat_name):
        st.session_state.selected_category = cat_name

    # Dummy category tree for UI demonstration
    categories_dict = {
        "Görüntü Teknolojileri": ["Kameralar", "Lensler", "Monitörler", "Video Mikserleri"],
        "Ses Teknolojileri": ["Mikrofonlar", "Ses Mikserleri", "Hoparlörler"],
        "Aydınlatma": ["Stüdyo Işıkları", "Taşınabilir Işıklar"],
        "Yayın Sistemleri": ["Vericiler", "Kodlayıcılar"]
    }
    
    if st.button("📁 Tüm Kategoriler", on_click=select_cat, args=("Tüm Kategoriler",), use_container_width=True):
        pass
        
    for main_cat, sub_cats in categories_dict.items():
        with st.expander(f"📁 {main_cat}", expanded=False):
            if st.button(main_cat, key=f"btn_{main_cat}", on_click=select_cat, args=(main_cat,), use_container_width=True):
                pass
            for sub_cat in sub_cats:
                # Add some indenting
                if st.button(f"📄 {sub_cat}", key=f"btn_{main_cat}_{sub_cat}", on_click=select_cat, args=(f"{main_cat} > {sub_cat}",), use_container_width=True):
                    pass

    st.divider()
    
    # Yeni Not Ekle (Smart Parsing Input)
    st.markdown("#### 📝 Yeni Firma / Not Ekle")
    new_company = st.text_input("Firma Adı")
    new_note = st.text_area("Notunuzu girin (Örn: #acil toplantı ayarla @Sony [Kameralar])", height=100)
    
    if st.button("Kaydet", type="primary", use_container_width=True):
        if new_company and new_note:
            new_task = parse_and_create_task(new_company, new_note)
            if new_task:
                # Make sure brackets matches the expected schema in repository 
                # (For simplicity, we pass bracket_category if parser extracted it)
                inserted = insert_task(get_client_safely(), new_task)
                if inserted:
                    st.success("Not kaydedildi!")
                    st.rerun()
                else:
                    st.error("Veritabanına kaydedilirken hata oluştu.")
            else:
                st.warning("Not ayrıştırılamadı. Geçerli bir etiket (tag), mention veya kategori bulunamadı.")
        else:
            st.warning("Firma adı ve not alanı zorunludur.")


# ==========================================================
# 3. ANA İÇERİK ALANI (MAIN CONTENT)
# ==========================================================

# Ekmek Kırıntısı (Breadcrumb) ve Görünüm Seçici
top_col1, top_col2 = st.columns([1, 1])
with top_col1:
    st.markdown(f"<div class='breadcrumb'>Dashboard > <b>{st.session_state.selected_category}</b></div>", unsafe_allow_html=True)

with top_col2:
    view_mode = st.segmented_control("Görünüm Seçici", ["Kanban", "Tablo"], default="Kanban", selection_mode="single")
    # if empty, default to Kanban
    if not view_mode:
        view_mode = "Kanban"

# Filter tasks based on selected category 
filtered_tasks = []
for t in all_tasks:
    # Basic filtering: if "Tüm Kategoriler", show all. 
    # If a specific tree node is selected, check if bracket_category matches or if search matches.
    cat_match = True
    if st.session_state.selected_category != "Tüm Kategoriler":
        cat_str = st.session_state.selected_category
        # if the task has bracket_category matching the selection exactly, or containing it
        task_cat = t.get("bracket_category") or ""
        if cat_str.split(" > ")[-1] not in task_cat and cat_str not in task_cat:
            cat_match = False
            
    # Search Query Filter
    search_match = True
    if search_query:
        sq = search_query.lower()
        company = str(t.get("source_company", "")).lower()
        desc = str(t.get("task_description", "")).lower()
        if sq not in company and sq not in desc:
            search_match = False

    if cat_match and search_match:
        filtered_tasks.append(t)

# Metrikler (Stat Cards)
total_tasks = len(filtered_tasks)
urgent_count = sum(1 for t in filtered_tasks if t.get("priority") == "High")
done_count = sum(1 for t in filtered_tasks if t.get("status") == "Done")

stat_col1, stat_col2, stat_col3 = st.columns(3)
with stat_col1:
    with st.container(border=True):
        st.markdown(f"**Toplam Görev**<br><span class='stat-card-value'>{total_tasks}</span>", unsafe_allow_html=True)
with stat_col2:
    with st.container(border=True):
        st.markdown(f"**🔴 Acil İşler**<br><span class='stat-card-value text-red-600' style='color:#EF4444'>{urgent_count}</span>", unsafe_allow_html=True)
with stat_col3:
    with st.container(border=True):
        st.markdown(f"**✅ Tamamlanan**<br><span class='stat-card-value' style='color:#22C55E'>{done_count}</span>", unsafe_allow_html=True)

st.write("") # Spacer

# Helper rendering function for mentions
def render_description_with_mentions(desc):
    # Highlight @mentions in HTML
    return re.sub(r'(@\w+)', r'<span class="mention">\1</span>', desc)

# Helper rendering for priorities
def get_priority_html(priority):
    if priority == "High":
        return "<span class='priority-high'>High</span>"
    elif priority == "Low":
        return "<span class='priority-low'>Low</span>"
    else:
        return "<span class='priority-normal'>Normal</span>"


# ==========================================================
# 5. KANBAN GÖRÜNÜMÜ
# ==========================================================
if view_mode == "Kanban":
    grouped_tasks = {"Todo": [], "In Progress": [], "Done": []}
    for t in filtered_tasks:
        stat = t.get("status", "Todo")
        if stat in grouped_tasks:
            grouped_tasks[stat].append(t)
            
    k_col1, k_col2, k_col3 = st.columns(3)
    
    columns_mapping = [
        (k_col1, "Yapılacaklar", "Todo"),
        (k_col2, "Sürüyor", "In Progress"),
        (k_col3, "Tamamlandı", "Done")
    ]
    
    for col, title, status_key in columns_mapping:
        with col:
            tasks_list = grouped_tasks[status_key]
            # Badge header
            st.markdown(f"<div style='background-color:#F1F5F9; padding: 8px; border-radius: 8px; margin-bottom: 12px'><b>{title}</b> <span style='background:#E2E8F0; padding: 2px 6px; border-radius: 9999px; font-size:0.75rem'>{len(tasks_list)}</span></div>", unsafe_allow_html=True)
            
            for task in tasks_list:
                with st.container(border=True):
                    # Top Row: Firm + Priority
                    r1c1, r1c2 = st.columns([3, 1])
                    with r1c1:
                        st.markdown(f"**{task.get('source_company', 'Bilinmeyen Firma')}**")
                    with r1c2:
                        st.markdown(f"<div style='text-align:right'>{get_priority_html(task.get('priority', 'Normal'))}</div>", unsafe_allow_html=True)
                    
                    # Subtitle: Category path
                    cat_path = task.get('bracket_category')
                    if cat_path:
                        st.markdown(f"<div class='task-category'>{st.session_state.selected_category.split(' > ')[0]} > {cat_path}</div>", unsafe_allow_html=True)
                        
                    # Body Text
                    desc_html = render_description_with_mentions(task.get('task_description', ''))
                    st.markdown(desc_html, unsafe_allow_html=True)
                    
                    # Date & Tags
                    due_date = task.get('due_date')
                    meta_html = ""
                    if due_date:
                        # try parse iso
                        try:
                            d = datetime.datetime.fromisoformat(due_date.replace("Z", "+00:00")).strftime("%Y-%m-%d")
                            meta_html += f"<span style='font-size:0.75rem; color:#64748B; margin-right:8px'>📅 {d}</span>"
                        except:
                            pass
                            
                    tags = task.get('tags', [])
                    if tags:
                        for tag in tags:
                            meta_html += f"<span class='hashtag'>#{tag}</span>"
                    
                    if meta_html:
                        st.markdown(f"<div style='margin-bottom:8px; margin-top:8px;'>{meta_html}</div>", unsafe_allow_html=True)
                    
                    # Bottom Row Line: Actions
                    act_col1, act_col2 = st.columns([1, 2])
                    with act_col1:
                        st.markdown("<div style='font-size:0.875rem; color:#64748B; padding-top:6px'>Durum:</div>", unsafe_allow_html=True)
                    with act_col2:
                        task_id = task['id']
                        current_status = task.get('status', status_key)
                        
                        # We use on_change to trigger immediately
                        def status_changed(t_id, state_key):
                            new_val = st.session_state[state_key]
                            success = update_task_status(get_client_safely(), t_id, new_val)
                            # Rerun is automatically handled by streamlit after on_change callback completes

                        s_key = f"status_{task_id}"
                        st.selectbox(
                            "Status", 
                            ["Todo", "In Progress", "Done"], 
                            index=["Todo", "In Progress", "Done"].index(current_status),
                            key=s_key,
                            label_visibility="collapsed",
                            on_change=status_changed,
                            args=(task_id, s_key)
                        )

# ==========================================================
# 6. TABLO GÖRÜNÜMÜ (DATA GRID)
# ==========================================================
else:
    if not filtered_tasks:
        st.info("Gösterilecek görev bulunamadı.")
    else:
        df = pd.DataFrame(filtered_tasks)
        columns_to_show = ["id", "source_company", "bracket_category", "task_description", "priority", "status"]
        columns_to_show = [c for c in columns_to_show if c in df.columns]
        df_display = df[columns_to_show]
        
        edited_df = st.data_editor(
            df_display,
            column_config={
                "id": st.column_config.TextColumn("ID", disabled=True),
                "source_company": st.column_config.TextColumn("Firma", disabled=True),
                "bracket_category": st.column_config.TextColumn("Kategori", disabled=True),
                "task_description": st.column_config.TextColumn("Görev/Not", width="large", disabled=True),
                "status": st.column_config.SelectboxColumn(
                    "Durum",
                    options=["Todo", "In Progress", "Done"],
                    required=True,
                ),
                "priority": st.column_config.SelectboxColumn(
                    "Öncelik",
                    options=["High", "Normal", "Low"],
                    required=True,
                )
            },
            hide_index=True,
            use_container_width=True,
            key="task_data_editor_main"
        )
        
        # Save edits logic for grid
        if "task_data_editor_main" in st.session_state:
            edited_rows = st.session_state["task_data_editor_main"].get("edited_rows", {})
            if edited_rows:
                updates = []
                for row_idx, changes in edited_rows.items():
                    task_id = df_display.iloc[row_idx]["id"]
                    update_payload = {"id": task_id}
                    if "status" in changes:
                        update_payload["status"] = changes["status"]
                    if "priority" in changes:
                        update_payload["priority"] = changes["priority"]
                    updates.append(update_payload)
                
                # We could auto-save or require a button. We will use a floating auto-save or a specific button
                # since the prompt says "anında güncellenmelidir" (instant update), we can just execute the update
                # directly and rerun. Let's do instant update:
                if updates:
                    success = bulk_update_tasks(get_client_safely(), updates)
                    if success:
                        st.success("Tablo değişiklikleri kaydedildi!")
                        st.rerun()
