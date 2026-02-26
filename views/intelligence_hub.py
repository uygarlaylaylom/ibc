import streamlit as st
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def show_intelligence_hub():
    """
    🧠 İstihbarat Merkezi
    Analiz & Görevler + Email Kutusu birleşik modülü
    """
    st.title("🧠 İstihbarat Merkezi")
    st.caption("Görev yönetimi, email analizi ve AI asistan tek ekranda.")

    tab1, tab2, tab3 = st.tabs(["📊 Analiz & Görevler", "📬 Email Kutusu", "🤖 AI Asistan"])

    with tab1:
        from views.dashboard import show_dashboard
        show_dashboard()

    with tab2:
        from views.email_inbox import show_email_inbox
        show_email_inbox()

    with tab3:
        _show_ai_assistant()


def _show_ai_assistant():
    """Tüm notlar + emailler + görevler üzerinde serbest Gemini chat."""
    st.markdown("### 🤖 Fuar AI Asistanı")
    st.caption("Tüm notlarınız, emailleriniz ve görevleriniz hakkında soru sorun.")

    try:
        from openai import OpenAI
        from supabase_utils import get_supabase, get_companies
        import datetime

        api_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY"))
        if not api_key:
            st.warning("OPENAI_API_KEY bulunamadı.")
            return

        client = OpenAI(api_key=api_key)
        supabase = get_supabase()

        # Hazır sorular
        st.markdown("**Hazır Sorgular:**")
        quick_cols = st.columns(3)
        quick_q = None
        with quick_cols[0]:
            if st.button("🔴 Bu haftaki acil görevler", use_container_width=True):
                quick_q = "Bu haftaki acil (#acil veya priority=High) görevleri listele, firmaya göre grupla."
        with quick_cols[1]:
            if st.button("📈 En aktif firmalar", use_container_width=True):
                quick_q = "En çok not/email olan ilk 10 firmayı listele, ne hakkında konuşulmuş?"
        with quick_cols[2]:
            if st.button("📬 Emaillerden takip listesi", use_container_width=True):
                quick_q = "Emaillerden çıkan aksiyon gerektiren konuları firmaya göre listele."

        st.markdown("---")

        # Serbest soru girişi
        user_q = st.text_input(
            "Sorunuz:",
            value=quick_q or st.session_state.get("ai_last_q", ""),
            placeholder="Örn: Flooring kategorisindeki en önemli firma hangisi?",
            key="ai_question"
        )

        if st.button("🔍 Sor", type="primary", use_container_width=True, key="ai_ask"):
            if user_q:
                st.session_state["ai_last_q"] = user_q
                with st.spinner("ChatGPT verilerinizi analiz ediyor..."):
                    # Veri topla
                    companies = get_companies()
                    notes_resp = supabase.table("activities").select("*").limit(200).execute()
                    notes = notes_resp.data or []

                    # Özet context oluştur
                    # Limit numbers reduced to prevent Gemini API 429 Quota Exceeded Token Limit errors
                    comp_summary = "\n".join([
                        f"- {c.get('company_name','?')} | Booth:{c.get('booth_number','?')} | "
                        f"Öncelik:{c.get('priority','?')} | Ürünler:{','.join((c.get('products') or [])[:3])}"
                        for c in companies[:30]  # Reduced from 80
                    ])

                    manual_notes = [n for n in notes if n.get('type') == 'note']
                    email_notes  = [n for n in notes if n.get('type') == 'email']

                    notes_summary = "\n".join([
                        f"[{n.get('created_at','')[:10]}] {n.get('content','')[:100]}"
                        for n in manual_notes[:20]  # Reduced from 50 and text cut to 100
                    ])

                    email_summary = "\n".join([
                        f"[Email] {n.get('content','')[:100]}"
                        for n in email_notes[:10]   # Reduced from 30 and text cut to 100
                    ])

                    prompt = (
                        f"Sen bir fuar (IBS/KBIS 2026) asistanısın. Aşağıdaki veriler elimde:\n\n"
                        f"=== FİRMALAR ({len(companies)} adet) ===\n{comp_summary}\n\n"
                        f"=== EL NOTLARI ({len(manual_notes)} adet) ===\n{notes_summary}\n\n"
                        f"=== EMAİLLER ({len(email_notes)} adet) ===\n{email_summary}\n\n"
                        f"=== KULLANICI SORUSU ===\n{user_q}\n\n"
                        f"Türkçe, kısa ve somut yanıt ver. Madde madde listele."
                    )

                    try:
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.3
                        )
                        st.session_state["ai_last_answer"] = response.choices[0].message.content.strip()
                    except Exception as e:
                        st.error(f"OpenAI hatası: {e}")

        # Cevap göster
        if st.session_state.get("ai_last_answer"):
            with st.container(border=True):
                st.markdown("**🤖 ChatGPT Yanıtı:**")
                st.markdown(st.session_state["ai_last_answer"])
            if st.button("🗑️ Temizle"):
                del st.session_state["ai_last_answer"]
                st.rerun()

    except ImportError:
        st.error("openai paketi yüklü değil.")
    except Exception as e:
        st.error(f"Hata: {e}")
