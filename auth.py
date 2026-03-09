import os.path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Scopes needed for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive']

def main():
    creds = None
    
    # Check if we already have a token
    if os.path.exists('token.json'):
        # We will ignore the expired token and force a new login below.
        pass
        
    # Force a new login instead of trying to refresh the old revoked one
    if True:
        if not os.path.exists('client_secret.json'):
            print("HATA: 'client_secret.json' dosyasi bulunamadi!")
            print("Lutfen Google Cloud Console'dan indirdiginiz OAuth kimlik dosyasini 'client_secret.json' adiyla proje ana dizinine atin.")
            return
            
        flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
        creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run (or Streamlit)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    print("\n=======================================================")
    print("BASARILI! 'token.json' dosyasi olusturuldu.")
    print("Bu dosyanin icindeki YAZILARIN TAMAMINI kopyalayin ve Streamlit ayarlariniza (Secrets) su sekilde yapistirin:")
    print("GDRIVE_TOKEN_JSON = '''\n(Kopyaladiginiz Yazi)\n'''")
    print("=======================================================\n")

if __name__ == '__main__':
    main()
