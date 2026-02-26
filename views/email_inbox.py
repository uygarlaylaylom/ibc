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
        return genai.GenerativeModel("gemini-2.0-flash")
    except Exception:
        return None


def _strip_metadata(content):
    """Stored markdown header/table'ı silerek ham email metnini döner."""
    # '---' separator'dan sonraki kısmı al (gerçek email body)
    parts = content.split('---\n')
    if len(parts) >= 2:
        # Son parça genellikle body + Gemini analizi
        body = parts[1]  # tablo'dan sonraki kısım
        # Eğer daha önce Gemini analizi eklendiyse onu çıkar
        if '\ud83e\udd16 **Gemini Analizi' in body:
            body = body.split('\ud83e\udd16 **Gemini Analizi')[0]
        return body.strip()[:2000]
    return content[:2000]


def _gemini_analyze(model, email_content, company_names):
    """Gemini'ye emaili analiz ettirir. Düz metin döner."""
    clean_body = _strip_metadata(email_content)
    company_list_str = ", ".join(company_names[:40])
    prompt = (
        "Fuar email analizi. Kesinlikle sadece aşağıdaki format, başka hiçbir şey yazma:\n\n"
        f"EMAIL:\n{clean_body}\n\n"
        "Format (her satır ayrı):\n"
        f"FİRMA: <gönderen şirket adı, bu listeden seç ya da 'Listede yok' de: {company_list_str}>\n"
        "ÜRÜN: <hangi ürün/kategori>\n"
        "AKSİYON: <somut tek eylem: Demo iste / Fiyat al / Katalog iste / Takip et / Sil>\n"
        "ÖNCELİK: <Yüksek veya Orta veya Düşük>"
    )
    try:
        resp = model.generate_content(prompt)
        return resp.text
    except Exception as e:
        return f"⚠️ Hata: {e}"


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

        resp = (supabase.table("activities")
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

        # ── TOPLU ANALİZ BUTONU ─────────────────────────────────────
        if gemini_model and visible:
            if st.button(f"🤖 Tümünü Analiz Et ({len(visible)} email)", type="primary", use_container_width=True):
                with st.spinner(f"{min(len(visible), 15)} email Gemini ile analiz ediliyor..."):
                    bulk_results = []
                    for em in visible[:15]:
                        content = em.get('content', '')
                        subject = _extract_subject(content)
                        result = _gemini_analyze(gemini_model, content, company_names_list)
                        st.session_state[f"gemini_result_{em['id']}"] = result

                        # Robust parse: hem 'AKSİYON:' hem '4. AKSİYON:' hem '**AKSİYON**:' gibi varyasyonları yakala
                        def extract_field(text, key):
                            pattern = re.compile(
                                r'(?:^|\n)(?:[0-9]+\.\s*|\*{1,2})?'
                                + re.escape(key)
                                + r'\*{0,2}[:\s]+(.+)',
                                re.IGNORECASE
                            )
                            m = pattern.search(text)
                            return m.group(1).strip() if m else "—"

                        action   = extract_field(result, 'AKSİYON')
                        priority = extract_field(result, 'ÖNCELİK').split()[0] if extract_field(result, 'ÖNCELİK') != '—' else '—'
                        firma_gem = extract_field(result, 'FİRMA')  # Gemini'nin firma tahmini
                        # Firma tahminini company_options'ta ara (fuzzy-ish)
                        firma_id  = None
                        firma_gem_lower = firma_gem.lower()
                        for name, cid in company_options.items():
                            if firma_gem_lower in name.lower() or name.lower() in firma_gem_lower:
                                firma_id  = cid
                                firma_gem = name  # Tam ismi kullan
                                break
                        bulk_results.append({
                            "id":       em['id'],
                            "subject":  subject[:55],
                            "action":   action[:70],
                            "priority": priority,
                            "firma":    firma_gem,
                            "firma_id": firma_id,
                        })

                    st.session_state["bulk_analysis"] = bulk_results
                    st.rerun()

        # Toplu analiz sonuçları — interaktif satırlar
        if st.session_state.get("bulk_analysis"):
            with st.expander("📋 Toplu Analiz Sonuçları", expanded=True):
                st.caption(f"{len(st.session_state['bulk_analysis'])} email analiz edildi")
                # Başlık
                hc = st.columns([0.30, 0.25, 0.10, 0.17, 0.10, 0.08])
                hc[0].markdown("**Email**")
                hc[1].markdown("**Aksiyon**")
                hc[2].markdown("**Öncelik**")
                hc[3].markdown("**Gemini Firma**")
                hc[4].markdown("")
                hc[5].markdown("")
                st.markdown("---")

                to_remove = []
                for row in list(st.session_state["bulk_analysis"]):
                    badge = "🔴" if "Yüksek" in row["priority"] else "🟡" if "Orta" in row["priority"] else "🟢"
                    rc = st.columns([0.30, 0.25, 0.10, 0.17, 0.10, 0.08])
                    rc[0].caption(row["subject"])
                    rc[1].caption(row["action"])
                    rc[2].markdown(f"{badge}")
                    rc[3].caption(row["firma"] if row["firma"] != "—" else "—")

                    # Firmaya Ekle butonu
                    if row.get("firma_id"):
                        if rc[4].button("✅ Ekle", key=f"bulk_assign_{row['id']}",
                                         help=f"{row['firma']} firmasına ata", use_container_width=True):
                            supabase.table("activities").update(
                                {"company_id": row["firma_id"]}
                            ).eq("id", row["id"]).execute()
                            to_remove.append(row["id"])
                            st.toast(f"✅ {row['firma']} firmasına atandı!")
                    else:
                        rc[4].caption("—")

                    # Sil butonu
                    if rc[5].button("🗑️", key=f"bulk_del_{row['id']}", use_container_width=True):
                        supabase.table("activities").delete().eq("id", row["id"]).execute()
                        to_remove.append(row["id"])
                        st.toast("🗑️ Silindi")

                if to_remove:
                    st.session_state["bulk_analysis"] = [
                        r for r in st.session_state["bulk_analysis"] if r["id"] not in to_remove
                    ]
                    st.rerun()

                if st.button("🗑️ Listeyi Temizle", key="clear_bulk"):
                    del st.session_state["bulk_analysis"]
                    st.rerun()


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
                            supabase.table("activities").update(
                                {"company_id": company_options[sel_company]}
                            ).eq("id", em_id).execute()
                            st.toast(f"✅ {sel_company} firmasına atandı!")
                            st.rerun()
                with hcol3:
                    if st.button("🗑️ Sil", key=f"del_{em_id}", use_container_width=True):
                        supabase.table("activities").delete().eq("id", em_id).execute()
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
                                                    supabase.table("activities").update(
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

        all_resp = supabase.table("activities").select("content").eq("type", "email").execute()
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
