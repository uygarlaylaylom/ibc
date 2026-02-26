import streamlit as st
import sys, os, re, datetime
from collections import Counter

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from supabase_utils import get_supabase, get_companies

# ──────────────────────────────────────────────────────────
# Mevcut Gmail arama anahtar kelimeleri
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

STOPWORDS = set([
    "the", "and", "for", "are", "with", "this", "that", "from", "have", "our",
    "your", "will", "you", "can", "has", "all", "any", "more", "new", "been",
    "but", "not", "www", "com", "net", "org", "http", "https", "mail", "email",
    "please", "dear", "hello", "hi", "thank", "thanks", "best", "regards",
    "click", "here", "view", "see", "visit", "contact", "info", "just", "about",
    "re:", "fwd:", "was", "its", "their", "also", "they", "follow",
])


def _get_gemini():
    """Gemini API istemcisini döner. Hata olursa None."""
    try:
        import google.generativeai as genai
        api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        return genai.GenerativeModel("gemini-1.5-flash")
    except Exception:
        return None


def _gemini_analyze(model, email_content, company_names):
    """Gemini'ye emaili analiz ettirir. Dict döner."""
    company_list_str = ", ".join(company_names[:50])
    prompt = f"""Aşağıdaki bir fuar/ticari etkinlik emailidir. Lütfen kısaca Türkçe analiz et:

EMAIL:
{email_content[:2500]}

Şu formatta yanıtla (JSON olmadan, düz metin):
1. ÖZET: (1-2 cümle, emailin ana konusu)
2. FİRMA TAHMİNİ: (Gönderen muhtemelen şu firmalardan biridir, listeden en yakın olanı seç veya "Listede yok" de: {company_list_str})
3. ÜRÜN/KATEGORİ: (Email hangi ürün veya kategoriden bahsediyor?)
4. AKSİYON: (Yapılması gereken en önemli eylem nedir? Örn: "Fiyat listesi iste", "Demo ayarla", "Görmezden gel")
5. ÖNCELİK: (Yüksek / Orta / Düşük ve neden)"""

    try:
        resp = model.generate_content(prompt)
        return resp.text
    except Exception as e:
        return f"⚠️ Gemini hatası: {e}"


def show_email_inbox():
    st.title("📬 Email Kutusu")
    st.caption("Gmail'den toplanan fuar emailleri. Firmaya atanmamış olanları eşleştirin veya silin.")

    supabase = get_supabase()

    # Gemini modeli — eğer API key yoksa None
    gemini_model = _get_gemini()
    if not gemini_model:
        st.sidebar.warning("🤖 Gemini API aktif değil. `GEMINI_API_KEY` Streamlit Secrets'a ekleyin.")

    tab1, tab2 = st.tabs(["📩 Eşleşmemiş Emailler", "💡 Anahtar Kelime Önerileri"])

    # ──────────────────────────────────────────
    # SEKME 1: Eşleşmemiş Emailler
    # ──────────────────────────────────────────
    with tab1:
        companies = get_companies()
        company_options = {c['company_name']: c['id'] for c in companies if c.get('company_name')}
        company_names_list = sorted(company_options.keys())
        company_names_sorted = ["— Firma Seç —"] + company_names_list

        resp = (supabase.table("notes")
                .select("*")
                .is_("company_id", "null")
                .eq("type", "email")
                .order("created_at", desc=True)
                .limit(200)
                .execute())
        emails = resp.data or []

        if not emails:
            st.success("📭 Eşleşmemiş email yok!")
            return

        # Filtreler
        fcol1, fcol2 = st.columns(2)
        with fcol1:
            all_events = sorted(set([_detect_event(e.get('content', '')) for e in emails]))
            event_filter = st.selectbox("🎪 Fuar", ["Tümü"] + all_events, key="inbox_event")
        with fcol2:
            urgency_filter = st.selectbox("🔥 Öncelik", ["Tümü", "🔴 Yüksek (7+)", "🟡 Orta (4-6)", "🟢 Düşük (0-3)"], key="inbox_urgency")

        visible = [e for e in emails
                   if (event_filter == "Tümü" or _detect_event(e.get('content','')) == event_filter)
                   and _urgency_passes(e.get('content',''), urgency_filter)]

        st.markdown(f"**{len(visible)} / {len(emails)} email gösteriliyor**")
        st.markdown("---")

        for em in visible:
            content = em.get('content', '')
            event_tag = _detect_event(content)
            urgency = _score_urgency(content)
            urgency_badge = "🔴" if urgency >= 7 else "🟡" if urgency >= 4 else "🟢"
            date_str = _parse_date(em.get('created_at', ''))
            subject = _extract_subject(content)
            em_id = em['id']

            with st.container(border=True):
                # Başlık satırı
                hcol1, hcol2, hcol3 = st.columns([0.55, 0.30, 0.15])
                with hcol1:
                    st.markdown(f"{urgency_badge} **{subject}**")
                    st.caption(f"📅 {date_str}  ·  🎪 {event_tag}  ·  Skor {urgency}/10")
                with hcol2:
                    sel_company = st.selectbox(
                        "Firmaya Ata",
                        company_names_sorted,
                        key=f"assign_{em_id}",
                        label_visibility="collapsed"
                    )
                    if sel_company != "— Firma Seç —":
                        if st.button("💾 Ata", key=f"save_{em_id}", type="primary", use_container_width=True):
                            supabase.table("notes").update(
                                {"company_id": company_options[sel_company]}
                            ).eq("id", em_id).execute()
                            st.toast(f"✅ {sel_company} firmasına atandı!")
                            st.rerun()
                with hcol3:
                    if st.button("🗑️ Sil", key=f"del_{em_id}", use_container_width=True):
                        supabase.table("notes").delete().eq("id", em_id).execute()
                        st.toast("🗑️ Email silindi.")
                        st.rerun()

                # Detay paneli
                with st.expander("📄 İçerik & 🤖 Gemini Analizi"):
                    ecol1, ecol2 = st.columns([0.5, 0.5])

                    with ecol1:
                        st.markdown("**Email İçeriği:**")
                        preview = content[:1000] + ("…" if len(content) > 1000 else "")
                        st.text(preview)

                    with ecol2:
                        st.markdown("**🤖 Gemini Analizi:**")
                        if gemini_model:
                            cache_key = f"gemini_result_{em_id}"
                            if cache_key not in st.session_state:
                                if st.button("▶️ Gemini ile Analiz Et", key=f"gemini_btn_{em_id}"):
                                    with st.spinner("Analiz ediliyor..."):
                                        result = _gemini_analyze(gemini_model, content, company_names_list)
                                        st.session_state[cache_key] = result
                            if st.session_state.get(cache_key):
                                st.markdown(st.session_state[cache_key])
                                # Gemini firma önerisi varsa hızlı atama butonu
                                if "FİRMA TAHMİNİ:" in st.session_state[cache_key]:
                                    lines = st.session_state[cache_key].split('\n')
                                    for l in lines:
                                        if "FİRMA TAHMİNİ:" in l:
                                            suggested = l.split("FİRMA TAHMİNİ:")[-1].strip().strip(".")
                                            # Listede tam match var mı?
                                            if suggested in company_options:
                                                if st.button(f"⚡ '{suggested}' firmasına hızlı ata", key=f"quick_{em_id}"):
                                                    supabase.table("notes").update(
                                                        {"company_id": company_options[suggested]}
                                                    ).eq("id", em_id).execute()
                                                    st.toast(f"✅ {suggested} firmasına atandı!")
                                                    st.rerun()
                        else:
                            st.info("Gemini API key yok. Streamlit Secrets'a `GEMINI_API_KEY` ekleyin.\n\n[Ücretsiz anahtar al →](https://aistudio.google.com/app/apikey)")

    # ──────────────────────────────────────────
    # SEKME 2: Anahtar Kelime Önerileri
    # ──────────────────────────────────────────
    with tab2:
        st.markdown("### 💡 Email İçeriklerinden Anahtar Kelime Önerileri")
        st.caption("Emaillerinizde sık geçen ama mevcut arama listemizde **olmayan** kelimeler.")

        all_resp = supabase.table("notes").select("content").eq("type", "email").execute()
        all_emails = all_resp.data or []

        if not all_emails:
            st.info("Öneri için email yok.")
            return

        word_freq = Counter()
        for em in all_emails:
            words = re.findall(r'\b[A-Za-z][a-zA-Z]{3,}\b', em.get('content', ''))
            for w in words:
                wl = w.lower()
                if wl not in STOPWORDS:
                    word_freq[wl] += 1

        base_lower = set(k.lower() for k in BASE_KEYWORDS)
        candidates = sorted(
            [(w, c) for w, c in word_freq.items() if w not in base_lower and c >= 3],
            key=lambda x: -x[1]
        )[:40]

        if not candidates:
            st.success("🎉 Tüm sık geçen kelimeler zaten listemizde!")
            return

        st.markdown(f"**{len(candidates)} öneri** (3+ kez geçen):")
        st.markdown("---")

        selected_words = []
        cols = st.columns(4)
        for i, (word, count) in enumerate(candidates):
            with cols[i % 4]:
                if st.checkbox(f"`{word}` ({count}x)", key=f"kw_{word}"):
                    selected_words.append(word)

        if selected_words:
            st.markdown("---")
            st.success(f"**Seçilen:** {', '.join(selected_words)}")
            if st.button("➕ Bana Bildir (Apps Script'e Eklenecek)", type="primary"):
                if "custom_keywords" not in st.session_state:
                    st.session_state["custom_keywords"] = []
                st.session_state["custom_keywords"] = list(
                    set(st.session_state["custom_keywords"] + selected_words)
                )
                st.info(f"✅ Kaydedildi: **{', '.join(selected_words)}**\n\nBunları geliştiriciye bildirin — `gmail_to_supabase.gs` arama listesine eklenecek.")

        if st.session_state.get("custom_keywords"):
            st.markdown("---")
            st.markdown("**📋 Bekleyen özel kelimeler:**")
            for kw in list(st.session_state["custom_keywords"]):
                c1, c2 = st.columns([0.85, 0.15])
                c1.code(kw)
                if c2.button("✕", key=f"del_kw_{kw}"):
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
    for w in ["urgent","deadline","offer","price list","quote","teklif","meeting","appointment","expires","asap","exclusive","today","katalog","catalog","sample","demo request","fiyat"]:
        if w in s: score += 2
    for w in ["new product","launch","announcement","schedule","brochure","partnership","distributor","follow up","follow-up","product line"]:
        if w in s: score += 1
    return min(score, 10)

def _urgency_passes(content, filter_str):
    u = _score_urgency(content)
    if filter_str == "🔴 Yüksek (7+)": return u >= 7
    if filter_str == "🟡 Orta (4-6)":  return 4 <= u <= 6
    if filter_str == "🟢 Düşük (0-3)": return u <= 3
    return True

def _extract_subject(content):
    for line in content.split('\n')[:3]:
        if '**' in line:
            return line.replace('📧', '').replace('**', '').strip()[:80]
    return content[:80]

def _parse_date(iso_str):
    try:
        dt = datetime.datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return iso_str[:10] if iso_str else "?"
