import streamlit as st
import sys, os, re, datetime
from collections import Counter

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from supabase_utils import get_supabase, get_companies, update_company

# ──────────────────────────────────────────────────────────
# Mevcut Gmail arama anahtar kelimeleri — kullanıcı buraya ekleyebilir
# ──────────────────────────────────────────────────────────
BASE_KEYWORDS = [
    "IBS", "KBIS", "International Builders", "Kitchen Bath", "NAHB", "NKBA",
    "booth", "exhibitor", "trade show", "product catalog", "price list",
    "Orlando", "Las Vegas", "nahb.org", "kbis.com", "ibsvegas.com",
    "brochure", "quote", "distributor", "partnership", "sample", "catalog",
    "new product", "launch", "exclusive", "meeting", "appointment",
    "flooring", "roofing", "windows", "doors", "hvac", "insulation", "lighting",
    "cabinets", "countertop", "bath", "kitchen", "deck", "outdoor", "hardware",
    "framing", "siding", "waterproof", "trim", "molding", "fastener"
]

# Gürültüden arındırmak için atlanacak genel kelimeler
STOPWORDS = set([
    "the", "and", "for", "are", "with", "this", "that", "from", "have", "our",
    "your", "will", "you", "can", "has", "all", "any", "more", "new", "been",
    "but", "not", "www", "com", "net", "org", "http", "https", "mail", "email",
    "please", "dear", "hello", "hi", "thank", "thanks", "best", "regards",
    "click", "here", "view", "see", "visit", "contact", "info", "just", "about",
    "re:", "fwd:", "was", "its", "their", "also", "they", "follow",
])


def show_email_inbox():
    st.title("📬 Email Kutusu")
    st.markdown("Gmail'den toplanan fuar emailleri. Firmaya atanmamış olanları burada eşleştirebilirsiniz.")

    supabase = get_supabase()

    # ── Sekmeler ──────────────────────────────────────────
    tab1, tab2 = st.tabs(["📩 Eşleşmemiş Emailler", "💡 Anahtar Kelime Önerileri"])

    # ──────────────────────────────────────────
    # SEKME 1: Eşleşmemiş Emailler
    # ──────────────────────────────────────────
    with tab1:
        # Tüm firmaları dropdown için çek
        companies = get_companies()
        company_options = {c['company_name']: c['id'] for c in companies if c.get('company_name')}
        company_names_sorted = ["— Firma Seç —"] + sorted(company_options.keys())

        # Eşleşmemiş emailler = company_id IS NULL, type=email
        resp = (supabase.table("notes")
                .select("*")
                .is_("company_id", "null")
                .eq("type", "email")
                .order("created_at", desc=True)
                .limit(200)
                .execute())
        emails = resp.data or []

        if not emails:
            st.info("📭 Eşleşmemiş email yok. Harika!")
            return

        # Fuar filtresi
        all_events = list(set([_detect_event(e.get('content', '')) for e in emails]))
        event_filter = st.selectbox("🎪 Fuar Filtrele", ["Tümü"] + sorted(all_events), key="inbox_event")
        
        # Urgency filtresi
        urgency_filter = st.selectbox("🔥 Öncelik Filtrele", ["Tümü", "🔴 Yüksek (7+)", "🟡 Orta (4-6)", "🟢 Düşük (0-3)"], key="inbox_urgency")

        st.markdown(f"**{len(emails)} eşleşmemiş email**")
        st.markdown("---")

        matched_count = 0
        for em in emails:
            content = em.get('content', '')
            event_tag = _detect_event(content)
            urgency = _score_urgency(content)

            # Filtre uygula
            if event_filter != "Tümü" and event_tag != event_filter:
                continue
            if urgency_filter == "🔴 Yüksek (7+)" and urgency < 7:
                continue
            if urgency_filter == "🟡 Orta (4-6)" and not (4 <= urgency <= 6):
                continue
            if urgency_filter == "🟢 Düşük (0-3)" and urgency > 3:
                continue

            matched_count += 1
            
            urgency_badge = "🔴" if urgency >= 7 else "🟡" if urgency >= 4 else "🟢"
            date_str = _parse_date(em.get('created_at', ''))
            
            # Email başlık satırından konu çıkar
            subject = _extract_subject(content)

            with st.container(border=True):
                col_meta, col_action = st.columns([0.75, 0.25])
                
                with col_meta:
                    st.markdown(f"{urgency_badge} **{subject}**")
                    st.caption(f"🎪 {event_tag}  ·  📅 {date_str}  ·  Skor: {urgency}/10")
                
                with col_action:
                    sel_company = st.selectbox(
                        "Firmaya Ata",
                        company_names_sorted,
                        key=f"assign_{em['id']}",
                        label_visibility="collapsed"
                    )
                    if sel_company != "— Firma Seç —":
                        if st.button("💾 Ata", key=f"save_assign_{em['id']}", type="primary", use_container_width=True):
                            comp_id = company_options[sel_company]
                            supabase.table("notes").update({"company_id": comp_id}).eq("id", em['id']).execute()
                            st.success(f"✅ '{sel_company}' firmasına atandı!")
                            st.rerun()

                # Önizleme
                with st.expander("📄 Email İçeriğini Göster"):
                    # İlk 800 karakter
                    preview = content[:800] + ("…" if len(content) > 800 else "")
                    st.text(preview)

        if matched_count == 0:
            st.info("Bu filtreyle eşleşen email bulunamadı.")

    # ──────────────────────────────────────────
    # SEKME 2: Anahtar Kelime Önerileri
    # ──────────────────────────────────────────
    with tab2:
        st.markdown("### 💡 Email İçeriklerinden Yeni Anahtar Kelime Önerileri")
        st.markdown(
            "Emaillerinizde sık geçen ama mevcut arama listemizde **olmayan** kelimeler. "
            "Bunları listeye eklerseniz ilgili emailler daha erken yakalanır."
        )

        # Tüm emailleri al (eşleşmiş + eşleşmemiş)
        all_resp = (supabase.table("notes")
                    .select("content")
                    .eq("type", "email")
                    .execute())
        all_emails = all_resp.data or []

        if not all_emails:
            st.info("Öneri için email yok.")
            return

        # Tüm içeriklerden kelime frekansı çıkar
        word_freq = Counter()
        for em in all_emails:
            body = em.get('content', '')
            words = re.findall(r'\b[A-Za-z][a-zA-Z]{3,}\b', body)
            for w in words:
                w_lower = w.lower()
                if w_lower not in STOPWORDS:
                    word_freq[w_lower] += 1

        # Mevcut keyword listesinde olmayanları bul
        base_lower = set([k.lower() for k in BASE_KEYWORDS])
        candidates = [(w, c) for w, c in word_freq.items()
                      if w not in base_lower and c >= 3]  # En az 3 kez geçenler
        candidates.sort(key=lambda x: -x[1])
        top_candidates = candidates[:40]

        if not top_candidates:
            st.success("🎉 Tüm sık geçen kelimeler zaten listemizde!")
            return

        st.markdown(f"**{len(top_candidates)} yeni kelime önerisi** (3+ kez geçen):")
        st.markdown("---")

        # Supabase'de keywords tablosu yoksa, kendi .gs link öneri listesine ekliyoruz
        # Kullanıcı buradan seçer, biz kodu güncelleriz
        selected_words = []
        cols = st.columns(4)
        for i, (word, count) in enumerate(top_candidates):
            with cols[i % 4]:
                if st.checkbox(f"`{word}` ({count}x)", key=f"kw_{word}"):
                    selected_words.append(word)

        if selected_words:
            st.markdown("---")
            st.success(f"**{len(selected_words)} kelime seçildi:** {', '.join(selected_words)}")
            st.markdown("Bu kelimeleri Gmail arama listesine eklemek için aşağıdaki butona tıklayın:")
            
            if st.button("➕ Seçili Kelimeleri Kaydet (Apps Script'e Eklenecek)", type="primary"):
                # Supabase'de bir `email_keywords` tablosu yoksa properties'e yazarız
                props_resp = supabase.table("notes").select("id").limit(1).execute()
                
                # Şimdilik session_state'e kaydet ve kullanıcıya göster
                if "custom_keywords" not in st.session_state:
                    st.session_state["custom_keywords"] = []
                st.session_state["custom_keywords"] = list(set(
                    st.session_state.get("custom_keywords", []) + selected_words
                ))

                st.info(
                    f"✅ Şu kelimeler listeye eklendi: **{', '.join(selected_words)}**\n\n"
                    "Bu kelimeler `gmail_to_supabase.gs` dosyasındaki arama sorgusuna "
                    "eklenebilir. Geliştiriciye (Antigravity) bildirin."
                )

        # Eklenmiş özel kelimeler listesi
        if st.session_state.get("custom_keywords"):
            st.markdown("---")
            st.markdown("**📋 Şu an aktif özel anahtar kelimeler:**")
            for kw in st.session_state["custom_keywords"]:
                c1, c2 = st.columns([0.8, 0.2])
                with c1:
                    st.code(kw)
                with c2:
                    if st.button("🗑️", key=f"del_kw_{kw}"):
                        st.session_state["custom_keywords"].remove(kw)
                        st.rerun()


# ──────────────────────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ──────────────────────────────────────────────────────────

def _detect_event(text):
    t = text.lower()
    if "kbis" in t or "kitchen bath" in t or "kitchen & bath" in t: return "KBIS"
    if "ibs" in t or "international builders" in t or "ibsvegas" in t: return "IBS"
    if "nahb" in t: return "NAHB"
    if "nkba" in t: return "NKBA"
    if "orlando" in t: return "KBIS-Orlando"
    if "las vegas" in t: return "IBS-LasVegas"
    return "Fuar-Genel"

def _score_urgency(text):
    s = text.lower()
    score = 0
    high = ["urgent", "deadline", "offer", "price list", "quote", "teklif",
            "meeting", "appointment", "expires", "asap", "exclusive", "today",
            "katalog", "catalog", "sample", "demo request", "fiyat"]
    med  = ["new product", "launch", "announcement", "schedule", "brochure",
            "partnership", "distributor", "follow up", "follow-up", "product line"]
    for w in high:
        if w in s: score += 2
    for w in med:
        if w in s: score += 1
    return min(score, 10)

def _extract_subject(content):
    """Email içeriğinden konu satırını çıkarmaya çalışır."""
    lines = content.split('\n')
    for line in lines[:3]:
        if '**' in line:
            return line.replace('📧', '').replace('**', '').strip()
    return lines[0][:80] if lines else "(Konu yok)"

def _parse_date(iso_str):
    try:
        dt = datetime.datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return iso_str[:10] if iso_str else "?"
