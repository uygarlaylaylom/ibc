import os
import json
import io
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Scopes needed for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# The credentials file that the user will drop into the project root
CREDENTIALS_FILE = 'credentials.json'

def get_drive_service():
    """Authenticates and returns the Google Drive API service."""
    try:
        if "gcp_service_account" in st.secrets:
            creds_info = st.secrets["gcp_service_account"]
            if isinstance(creds_info, str):
                creds_dict = json.loads(creds_info)
            else:
                creds_dict = dict(creds_info)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Google Drive Kimlik Doğrulama Hatası (st.secrets JSON formatı bozuk olabilir): {e}")
        
    # Fallback to local file for testing
    if not os.path.exists(CREDENTIALS_FILE):
        print("No Google Service Account credentials found in st.secrets or local credentials.json")
        return None
        
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)
    return service

def find_or_create_folder(folder_name, parent_id=None):
    """Finds a folder by name or creates it if it doesn't exist inside parent."""
    service = get_drive_service()
    if not service: return None
    
    # If no parent_id is given, try to use a Root ID from secrets
    if not parent_id:
        parent_id = st.secrets.get("GDRIVE_ROOT_FOLDER_ID", None)
        
    try:
        # Check if folder exists
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
            
        # supportsAllDrives allows working within shared drives if applicable
        response = service.files().list(q=query, spaces='drive', fields='files(id, name)', supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        files = response.get('files', [])
        
        if files:
            return files[0].get('id')
            
        # Create folder
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            file_metadata['parents'] = [parent_id]
            
        folder = service.files().create(body=file_metadata, fields='id', supportsAllDrives=True).execute()
        
        # Don't try to change permissions if we're inside a folder we don't own completely,
        # but try to make it reader accessible if possible
        try:
            service.permissions().create(
                fileId=folder.get('id'),
                body={'type': 'anyone', 'role': 'reader'},
                supportsAllDrives=True
            ).execute()
        except:
            pass # Ignore if we can't change permissions, the parent folder sharing should cascade
            
        return folder.get('id')
    except Exception as e:
        import traceback
        st.error(f"Google Drive Klasör Oluşturma Hatası '{folder_name}': {e}")
        print(traceback.format_exc())
        return None

def upload_file_to_drive(file_bytes, file_name, mime_type, folder_id):
    """Uploads a file to a specific Google Drive folder and returns the webViewLink."""
    service = get_drive_service()
    if not service: return None
    
    file_metadata = {
        'name': file_name
    }
    if folder_id:
        file_metadata['parents'] = [folder_id]
        
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
    try:
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink, webContentLink', supportsAllDrives=True).execute()
    except Exception as e:
        import traceback
        st.error(f"Google Drive Yükleme Hatası: {e}")
        print(traceback.format_exc())
        return None
        
    # webContentLink forces a download, webViewLink previews in browser.
    return file.get('webViewLink')
