import os
import io
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from homeWork.models import Homework
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.http import MediaIoBaseDownload

import google.generativeai as genai
from docx import Document
import re  # Import regex for username cleanup

# Define Google API Scopes
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file',
]


class Command(BaseCommand):
    help = "Fetch all .docx files from Google Drive, generate AI-based homework, and store it in the database."

    def handle(self, *args, **kwargs):
        creds = self.authenticate_google()
        files = self.get_all_docx_files(creds)

        if not files:
            self.stdout.write(self.style.WARNING(
                "⚠️ No .docx files found in Google Drive."))
            return

        for file in files:
            file_name = file['name']
            file_id = file['id']

            # Extract and clean username
            username = self.extract_valid_username(file_name)

            # Skip processing if username is invalid
            if not username:
                self.stdout.write(self.style.ERROR(
                    f"❌ Skipping {file_name} - Invalid username."))
                continue

            # Download, Process, and Create Homework
            file_path = self.download_file(file_id, file_name, creds)
            document_content = self.read_docx(file_path)
            homework_text = self.generate_homework(document_content)
            self.create_homework_in_django(username, homework_text)

            # Create homework in Django
            self.create_homework_in_django(username, homework_text)
            # delete file from drive ido need to check if its working
            drive_service = build('drive', 'v3', credentials=creds)
            drive_service.files().delete(fileId=file_id).execute()
            self.stdout.write(self.style.SUCCESS(
                f"🗑️ Deleted file {file_name} from Google Drive"))

            if os.path.exists(file_path):
                os.remove(file_path)
                self.stdout.write(self.style.SUCCESS(
                    "🗑️ Deleted file: {file_name}"))

        self.stdout.write(self.style.SUCCESS(
            "✅ All homework files processed successfully."))

    def authenticate_google(self):
        creds = None
        token_file = 'token.json'
        credentials_file = 'credentials.json'

        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
            with open(token_file, 'w') as token:
                token.write(creds.to_json())

        return creds

    def get_all_docx_files(self, creds):
        """Retrieve all `.docx` files from Google Drive."""
        drive_service = build('drive', 'v3', credentials=creds)
        query = "mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'"
        results = drive_service.files().list(q=query, spaces='drive',
                                             fields="files(id, name)").execute()

        return results.get('files', [])

    def download_file(self, file_id, file_name, creds):
        """Download a file from Google Drive."""
        drive_service = build('drive', 'v3', credentials=creds)
        request = drive_service.files().get_media(fileId=file_id)
        file_path = os.path.join(os.getcwd(), file_name)

        with io.FileIO(file_path, 'wb') as file:
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()

        return file_path

    def read_docx(self, file_path):
        """Extract text from a `.docx` file."""
        document = Document(file_path)
        return "\n".join([paragraph.text for paragraph in document.paragraphs])

    def generate_homework(self, content):
        """Generate AI-based homework using Gemini API."""
        genai.configure(api_key="AIzaSyDnL8RfShx-pgxLRaMoby4kZKJJocnG3s8")
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = "This is a summary of an Arabic lesson in Hebrew. The content might be weird due to parsing issues. Create homework for the students."

        response = model.generate_content(prompt + "\n\n" + content)
        return response.text if response else "No AI-generated homework."

    def create_homework_in_django(self, username, homework_text):
        """Store the AI-generated homework in the Django database."""
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"⚠️ User '{username}' not found. Skipping file."))
            return

        Homework.objects.create(user=user, text=homework_text)
        self.stdout.write(self.style.SUCCESS(
            f"✅ Successfully created homework for {username}"))

    def extract_valid_username(self, file_name):
        """
        Extracts a valid username from the file name.
        Removes spaces, numbers, and special characters.
        """
        base_name = os.path.splitext(file_name)[0]  # Remove .docx extension
        # Remove invalid characters
        cleaned_username = re.sub(r'[^a-zA-Z0-9_]', '', base_name)

        # Ensure the username is not empty and exists in the database
        if cleaned_username and User.objects.filter(username=cleaned_username).exists():
            return cleaned_username
        return None
