import streamlit as st
import os
import json
import requests
from google_auth_oauthlib.flow import Flow

# Use the exact same scopes
SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

def get_client_config():
    """Build the client config dictionary from st.secrets"""
    client_id = st.secrets.get("GOOGLE_CLIENT_ID")
    client_secret = st.secrets.get("GOOGLE_CLIENT_SECRET")
    redirect_uri = st.secrets.get("REDIRECT_URI", "http://localhost:8501")
    
    # We must append /oauth2callback if the user set redirect_uri as the root
    # But actually, for pure Streamlit query params, it's easier to redirect
    # exactly to the root URL so Streamlit parses the ?code= query param on load.
    
    # Streamlit Cloud naturally redirects back to the main app URL.
    return {
        "web": {
            "client_id": client_id,
            "project_id": "streamlit-app",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret,
            "redirect_uris": [redirect_uri + "/oauth2callback", redirect_uri],
            "javascript_origins": [redirect_uri]
        }
    }

def get_user_info(credentials):
    """Retrieve user email and profile from Google"""
    user_info_service = "https://www.googleapis.com/oauth2/v1/userinfo"
    headers = {'Authorization': f'Bearer {credentials.token}'}
    response = requests.get(user_info_service, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Kullanıcı bilgileri alınamadı. HTTP {response.status_code}")
        return None

def check_custom_google_auth():
    """Main function to drop into app.py to protect the page."""
    
    client_config = get_client_config()
    redirect_uri = st.secrets.get("REDIRECT_URI", "http://localhost:8501")

    # Only initialize the Flow when needed
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )

    # 1. If already authenticated in session state, check whitelist and let them in
    if st.session_state.get('google_auth_user_email'):
        allowed_raw = st.secrets.get("ALLOWED_EMAILS", "")
        allowed_emails = [e.strip().lower() for e in allowed_raw.split(",") if e.strip()]
        user_email = st.session_state['google_auth_user_email']
        
        if allowed_emails and user_email not in allowed_emails:
            st.error(f"❌ '{user_email}' adresi bu uygulamaya erişim iznine sahip değil.")
            if st.button("Çıkış Yap ve Başka Hesap Dene"):
                st.session_state.clear()
                st.rerun()
            st.stop()
        return True # Authorized!

    # 2. Check if we are returning from Google OAuth with a ?code= parameter
    code = st.query_params.get("code")
    
    if code:
        try:
            # We have a code! Exchange it for a token
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Fetch user email
            user_info = get_user_info(credentials)
            if user_info and 'email' in user_info:
                st.session_state['google_auth_user_email'] = user_info['email'].lower()
                
                # Clear the query params so the URL looks clean again
                st.query_params.clear()
                st.rerun()
            else:
                st.error("Google'dan email adresiniz alınamadı.")
                st.stop()
        except Exception as e:
            st.error(f"Giriş başarısız. Google Code doğrulanamadı: {e}")
            # Don't stop, let them try again

    # 3. If no session and no code, show the Login Button
    st.markdown("## 🏢 IBS 2026 Fuar Asistanı")
    st.info("Bu uygulamaya erişmek için yetkili Google hesabınızla giriş yapın.")
    
    auth_url, _ = flow.authorization_url(prompt='consent')
    
    st.markdown(
        f'<a href="{auth_url}" target="_self" '
        f'style="display: inline-block; padding: 10px 20px; background-color: #4285F4; color: white; '
        f'text-decoration: none; border-radius: 5px; font-weight: bold;">'
        f'G ile Giriş Yap</a>',
        unsafe_allow_html=True
    )
    
    st.stop()
