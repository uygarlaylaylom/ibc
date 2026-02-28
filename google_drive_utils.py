import os
import json
import io
import streamlit as st
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Scopes needed for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# The credentials file that the user will drop into the project root
TOKEN_FILE = 'token.json'

def get_drive_service():
    """Authenticates and returns the Google Drive API service using User OAuth token."""
    try:
        if "GDRIVE_TOKEN_JSON" in st.secrets:
            token_info = st.secrets["GDRIVE_TOKEN_JSON"]
            if isinstance(token_info, str):
                token_dict = json.loads(token_info)
            else:
                token_dict = dict(token_info)
            creds = Credentials.from_authorized_user_info(token_dict, SCOPES)
            # Auto-refresh the token if it has expired
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
            return build('drive', 'v3', credentials=creds)
    except Exception as e:
        import traceback
        st.error(f"Google Drive st.secrets Yükleme Hatası (JSON parçalanamadı): {e}")
        st.code(traceback.format_exc())
        return None
        
    if not os.path.exists(TOKEN_FILE):
        return None
        
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
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
        response = service.files().list(q=query, fields='files(id, name)').execute()
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
            
        folder = service.files().create(body=file_metadata, fields='id').execute()
        
        # Don't try to change permissions if we're inside a folder we don't own completely,
        # but try to make it reader accessible if possible
        try:
            service.permissions().create(
                fileId=folder.get('id'),
                body={'type': 'anyone', 'role': 'reader'}
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
    """Uploads a file to a specific Google Drive folder and returns the webViewLink, id, and thumbnailLink."""
    service = get_drive_service()
    if not service: return None, None, None
    
    file_metadata = {
        'name': file_name
    }
    if folder_id:
        file_metadata['parents'] = [folder_id]
        
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
    try:
        # Request thumbnailLink and file id
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink, thumbnailLink').execute()
    except Exception as e:
        import traceback
        st.error(f"Google Drive Yükleme Hatası: {e}")
        print(traceback.format_exc())
        return None, None, None
        
    return file.get('webViewLink'), file.get('id'), file.get('thumbnailLink')

def delete_drive_file(file_id):
    """Deletes a file permanently from Google Drive."""
    service = get_drive_service()
    if not service: return False
    
    try:
        service.files().delete(fileId=file_id).execute()
        return True
    except Exception as e:
        import traceback
        print(f"Google Drive Silme Hatası: {e}")
        return False

def move_drive_file(file_id, new_folder_id):
    """Moves a file from its current parent folder(s) to a new folder."""
    service = get_drive_service()
    if not service: return False
    
    try:
        # Retrieve the existing parents to remove
        file = service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents', []))
        
        # Move the file to the new folder
        service.files().update(
            fileId=file_id,
            addParents=new_folder_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
        return True
    except Exception as e:
        import traceback
        print(f"Google Drive Dosya Taşıma Hatası: {e}")
        print(traceback.format_exc())
        return False

def list_folder_files(folder_id):
    """Returns a list of all files inside a specific Google Drive folder."""
    service = get_drive_service()
    if not service: return []
    
    try:
        # Only list files (not folders), not trashed
        query = f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed=false"
        response = service.files().list(
            q=query, 
            fields="files(id, name, mimeType, webViewLink, thumbnailLink)",
            pageSize=100
        ).execute()
        return response.get('files', [])
    except Exception as e:
        print(f"Drive dosya listeleme hatası: {e}")
        return []
