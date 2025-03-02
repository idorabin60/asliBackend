import os
import io
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from homeWork.models import Homework
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from googleapiclient.http import MediaIoBaseDownload
import googleapiclient
import google.generativeai as genai
from docx import Document
import re  # Import regex for username cleanup

# Define Google API Scopes
SCOPES = ["https://www.googleapis.com/auth/drive"]


class Command(BaseCommand):
    help = "Fetch all .docx files from Google Drive, generate AI-based homework, and store it in the database."

    def handle(self, *args, **kwargs):
        self.stdout.write("🟢 Starting the process...\n")

        try:
            creds = self.authenticate_google()
            files = self.get_all_docx_files(creds)

            if not files:
                self.stdout.write(self.style.WARNING(
                    "⚠️ No .docx files found in Google Drive.\n"))
                return

            self.stdout.write(f"✅ Found {len(files)} .docx files.\n")

            for file in files:
                file_name = file['name']
                file_id = file['id']
                self.stdout.write(
                    f"🔍 Processing file: {file_name} (ID: {file_id})\n")

                # ✅ Check if file has already been processed
                if Homework.objects.filter(file_id=file_id).exists():
                    self.stdout.write(self.style.WARNING(
                        f"⚠️ Skipping {file_name} - Already processed.\n"))
                    continue

                # ✅ Extract and validate email from the file name
                email = self.extract_valid_username(file_name)
                if not email:
                    self.stdout.write(self.style.ERROR(
                        f"❌ Skipping {file_name} - Invalid email format.\n"))
                    continue

                # ✅ Validate if user exists
                if not User.objects.filter(email=email).exists():
                    self.stdout.write(self.style.ERROR(
                        f"⚠️ Skipping {file_name} - User '{email}' does not exist in the database.\n"))
                    continue

                # ✅ Download, process, and store homework
                file_path = self.download_file(file_id, file_name, creds)
                document_content = self.read_docx(file_path)
                homework_text = self.generate_homework(document_content)
                self.create_homework_in_django(email, homework_text, file_id)

                # ✅ Delete local copy of file
                if os.path.exists(file_path):
                    os.remove(file_path)
                    self.stdout.write(self.style.SUCCESS(
                        f"🗑️ Deleted local file: {file_name}\n"))

            self.stdout.write(self.style.SUCCESS(
                "✅ All homework files processed successfully.\n"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ ERROR: {str(e)}\n"))

    def authenticate_google(self):
        """Authenticate with Google API using service account credentials."""
        self.stdout.write("🟢 Authenticating Google API...\n")

        BASE_DIR = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        json_path = os.path.join(BASE_DIR, 'service_account.json')

        if not os.path.exists(json_path):
            raise FileNotFoundError(
                f"❌ Service account file not found at: {json_path}")

        creds = Credentials.from_service_account_file(json_path, scopes=SCOPES)
        self.stdout.write("✅ Google API Authentication successful.\n")
        return creds

    def get_all_docx_files(self, creds):
        """Retrieve all `.docx` files from Google Drive."""
        self.stdout.write("🟢 Fetching .docx files from Google Drive...\n")

        drive_service = build('drive', 'v3', credentials=creds)
        folder_id = "1YvurevdgmZj7BumVGFjgEQjW9ehUbVbw"
        query = f"'{folder_id}' in parents"  # Get all files, any type

        try:
            results = drive_service.files().list(
                q=query, spaces='drive',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                fields="files(id, name)"
            ).execute()

            files = results.get('files', [])
            if files:
                self.stdout.write(
                    f"✅ Found {len(files)} .docx files in folder.\n")
            else:
                self.stdout.write(self.style.WARNING(
                    f"⚠️ No .docx files found in folder ID: {folder_id}.\n"))

            return files
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"❌ ERROR fetching files: {str(e)}\n"))
            return []

    def download_file(self, file_id, file_name, creds):
        self.stdout.write(
            f"🟢 Downloading file: {file_name} (ID: {file_id})...\n")
        drive_service = build('drive', 'v3', credentials=creds)
        file_path = os.path.join(os.getcwd(), file_name)
        try:
            request = drive_service.files().export_media(fileId=file_id,
                                                         mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            with io.FileIO(file_path, 'wb') as file:
                downloader = MediaIoBaseDownload(file, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    self.stdout.write(
                        f"📥 Download progress: {int(status.progress() * 100)}%")
            self.stdout.write(f"✅ Download completed: {file_name}\n")
            return file_path
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"❌ ERROR downloading {file_name}: {str(e)}\n"))
            return None

    def read_docx(self, file_path):
        """Extract text from a `.docx` file."""
        self.stdout.write(f"🟢 Extracting text from: {file_path}...\n")

        try:
            document = Document(file_path)
            text = "\n".join(
                [paragraph.text for paragraph in document.paragraphs])
            self.stdout.write(
                f"✅ Successfully extracted text from {file_path}\n")
            return text
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"❌ ERROR reading {file_path}: {str(e)}\n"))
            return ""

    def generate_homework(self, content):
        """Generate AI-based homework using Gemini API."""
        self.stdout.write("🟢 Generating AI homework...\n")

        try:
            genai.configure(api_key="AIzaSyDnL8RfShx-pgxLRaMoby4kZKJJocnG3s8")
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = "This is a summary of an Arabic lesson in Hebrew. The content might be weird due to parsing issues. Create homework for the students."

            response = model.generate_content(prompt + "\n\n" + content)
            generated_text = response.text if response else "No AI-generated homework."
            self.stdout.write("✅ AI homework generated successfully.\n")
            return generated_text
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"❌ ERROR generating AI homework: {str(e)}\n"))
            return ""

    def create_homework_in_django(self, email, homework_text, file_id):
        """Store the AI-generated homework in the Django database with file_id."""
        self.stdout.write(f"🟢 Storing homework in DB for user: {email}...\n")

        try:
            user = User.objects.get(email=email)
            Homework.objects.create(
                user=user, text=homework_text, file_id=file_id)
            self.stdout.write(self.style.SUCCESS(
                f"✅ Successfully created homework for {email}\n"))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"❌ ERROR: User '{email}' not found. Skipping file.\n"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"❌ ERROR storing in DB: {str(e)}\n"))

    def extract_valid_username(self, file_name):
        """
        Extracts a valid email from the file name.
        The file name must contain a valid email format.
        """
        base_name = os.path.splitext(file_name)[0]  # Remove .docx extension

    # Match a valid email format using regex
        match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', base_name)

        if match:
            email = match.group(0)  # Extract the matched email
            return email if User.objects.filter(email=email).exists() else None

        return None  # Return None if no valid email is found
