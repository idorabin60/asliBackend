import os
import io
import base64
from django.core.management.base import BaseCommand
from homeWork.models import Homework
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from googleapiclient.http import MediaIoBaseDownload
import googleapiclient
import google.generativeai as genai
from docx import Document
import openai
import re  # Import regex for username cleanup
from homeWork.prompt_data_parser import prompt_data_parser
from homeWork.prompt_data_parser import add_newline_after_number
from dotenv import load_dotenv
from django.contrib.auth import get_user_model
from homeWork.models import Homework, VocabularyMatch, GrammaticalPhenomenon, FillInBlank
import datetime
import json

User = get_user_model()

load_dotenv()   # ← will load KEY=VALUE lines from .env into os.environ

# Define Google API Scopes
SCOPES = ["https://www.googleapis.com/auth/drive"]


class Command(BaseCommand):

    help = "Fetch all .docx files from Google Drive, generate AI-based homework, and store it in the database."

    def handle(self, *args, **kwargs):
        load_dotenv()  # Load from .env file

        openai.api_key = os.getenv("OPEN_AI_API_KEY")

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
                if not file['name'].endswith('.docx'):
                    file_name = file['name']+".docx"
                else:
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
                self.create_homework_from_json(email, homework_text, file_id)

                # ✅ Delete local copy of file
                if os.path.exists(file_path):
                    os.remove(file_path)
                    self.stdout.write(self.style.SUCCESS(
                        f"🗑️ Deleted local file: {file_name}\n"))

            self.stdout.write(self.style.SUCCESS(
                "✅ All homework files processed successfully.\n"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ ERROR: {str(e)}\n"))

    def extract_valid_username(self, file_name):
        base = os.path.splitext(file_name)[0]
        m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', base)
        return m.group(0) if m else None

    def authenticate_google(self):
        """Authenticate with Google API using service account credentials."""
        self.stdout.write("🟢 Authenticating Google API...\n")
        base64_key = os.getenv("GOOGLE_CREDENTIALS_B64")

        if base64_key:
            self.stdout.write(
                "🧩 Detected GOOGLE_CREDENTIALS_B64 from environment.\n")
            credentials_path = "/tmp/service_account.json"
            try:
                with open(credentials_path, "wb") as f:
                    f.write(base64.b64decode(base64_key))
            except Exception as e:
                raise Exception(
                    f"❌ Failed to decode/write service account: {e}")
        else:
            BASE_DIR = os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            credentials_path = os.path.join(BASE_DIR, 'service_account.json')

            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"❌ Service account file not found at: {credentials_path}"
                )

        creds = Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES)
        self.stdout.write("✅ Google API Authentication successful.\n")
        return creds

    def get_all_docx_files(self, creds):
        """Retrieve all `.docx` files from Google Drive."""
        self.stdout.write("🟢 Fetching .docx files from Google Drive...\n")

        drive_service = build('drive', 'v3', credentials=creds)
        folder_id = "1NdM_pXYk5_Nd9I4E-pEwxOvrlEdzLrxy"
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
    # ✅ Save to /tmp for Render compatibility
        file_path = os.path.join("/tmp", file_name)
        try:
            # 1) Get the actual MIME type from Drive
            file_meta = drive_service.files().get(
                fileId=file_id,
                fields="mimeType"
            ).execute()
            mime = file_meta.get("mimeType", "")
            if not mime:
                raise ValueError("Could not retrieve MIME type from Drive.")
            if mime == "application/vnd.google-apps.document":
                export_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                request = drive_service.files().export_media(
                    fileId=file_id,
                    mimeType=export_mime
                )
            else:
                request = drive_service.files().get_media(fileId=file_id)
            with io.FileIO(file_path, 'wb') as file_handle:
                downloader = MediaIoBaseDownload(file_handle, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        progress = int(status.progress() * 100)
                        self.stdout.write(f"📥 Download progress: {progress}%")
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

    def generate_homework(self, content: str) -> dict:
        """
        Sends the lesson transcript to GPT-4o with a JSON-only prompt
        and returns the parsed dict.
        """
        self.stdout.write("🟢 Generating AI homework JSON...")
        system_message = {
            "role": "system",
            "content": (
                "You are a helpful assistant. Return ONLY valid JSON "
                "with keys: vocab_matches, grammatical_phenomenon, fill_in_the_blank_exercises."
            )
        }
        user_prompt = """פרומפט ליצירת סיכום שיעור בערבית מדוברת (תעתיק עברי) + יצירת פעילויות מבוססות המודל שלנו

חוקי התוכן והשפה (מעודכן):
1. כתוב את כל התוכן בערבית מדוברת (לא ספרותית, לא דיאלקט זר).
2. כל מילה בודדת בערבית (שאינה בתוך משפט מלא) תופיע כך: <ערבית> ‎(<תעתיק עברי>). למשל: كتاب ‎(כִּתַאבּ)
3. אל תשתמש בשום סוגריים אחרים מלבד הפורמט שבסעיף 2.
4. בפעילות “השלם את המשפט” (fill_in_the_blank_exercises) החזר שני שדות נפרדים:
   • **sentence_arabic** – משפט מלא בערבית בלבד עם ___  
   • **sentence_hebrew** – אותו משפט בתעתיק עברי עם ___  
   (אין מעבר־שורה בתוך אחד השדות.)
5. הקפד על הגייה ואותיות (א-ב-ג'-ד וכו') לפי הטבלה שלנו.
6. **זיהוי אוצר מילים חדש**  
   • כלול רק מילים שאינן ב-`known_vocab` של התלמיד  
   • מלה חייבת להופיע בתמלול ≥ 2 פעמים **או** להיות מסומנת במפורש כמילה חדשה.  
   • אל תכלול מילים פשוטות/תפקודיות (כינויי גוף, “של”, “עם”…).  
   • בחר מילים מאתגרות אך תואמות לרמת הלומד; אל תמציא מילים.
7. **בניית תרגילי השלמה**  
   • מינימום 5 מילים בכל משפט.  
   • שלב את המילים החדשות שאותרו.  
   • הצג תופעות דקדוק (למשל שימוש בזמנים).  
  • ודא תשובה נכונה אחת בלבד; המילים ב-**bank_words** יהיו רלוונטיות ובתוכן **חייב** להיכלל גם ה־**correct_answer**.  
   • שמור על היגיון ורצף טבעי.
8. רהיטות ומקצועיות בלבד; אל תשתמש בשפה בוטה.

מבנה הסיכום הנדרש:

#תופעה תחבירית חדשה  
הסבר בעברית + דוגמאות בערבית (עם תעתיק, לפי סעיף 2) + תרגום.

#אוצר מילים חדש  
15 פריטים:  
- arabic_word  מילה בודדת לפי סעיף 2  
- hebrew_word  התרגום לעברית

#שיעורי בית  
15 תרגילי “השלם את המשפט” כמתואר בסעיף 4.  
בשדות **correct_answer** ו-**bank_words** השתמש בפורמט סעיף 2.

החזר **אך ורק** JSON במבנה הבא (ללא טקסט נוסף):

{
  "vocab_matches": [
    {
      "arabic_word": "<ערבית-בודדה> ‎(<תעתיק-עברי>)",
      "hebrew_word": "<תרגום-עברית>"
    }
    // … 14 נוספים
  ],
  "grammatical_phenomenon": {
    "text": "<הסבר בעברית + דוגמאות בפורמט הנדרש + תרגום>"
  },
  "fill_in_the_blank_exercises": [
    {
      "sentence_arabic": "أنا بحب ___",
      "sentence_hebrew": "אנה בחב ___",
      "correct_answer": "<ערבית-בודדה> ‎(<תעתיק-עברי>)",
      "bank_words": [
        "<ערבית-בודדה> ‎(<תעתיק-עברי>)",
        "<ערבית-בודדה> ‎(<תעתיק-עברי>)",
        "<ערבית-בודדה> ‎(<תעתיק-עברי>)"
      ]
    }
    // … 14 נוספים
  ]
}

"""
        full_messages = [
            system_message,
            {"role": "user", "content": user_prompt},
            {"role": "user", "content": f"תמלול השיעור:\n\n{content}"}
        ]
        resp = openai.chat.completions.create(
            model="o4-mini",
            temperature=1,
            messages=full_messages,
        )
        raw = resp.choices[0].message.content
        # If the model wrapped in ```json blocks, strip them:
        if raw.startswith("```"):
            raw = raw.strip("```json").strip("```").strip()
        return json.loads(raw)

    def create_homework_from_json(self, email: str, data: dict, file_id: str):
        """Given the parsed JSON, create all related DB entries."""
        self.stdout.write(f"🟢 Storing homework for {email}...")
        user = User.objects.get(email=email)
        hw = Homework.objects.create(
            user=user,
            due_date=datetime.date.today(),
            file_id=file_id
        )
        # vocabulary
        for item in data.get("vocab_matches", []):
            VocabularyMatch.objects.create(
                homework=hw,
                arabic_word=item["arabic_word"],
                hebrew_word=item["hebrew_word"],
            )
        # grammatical phenomenon
        GrammaticalPhenomenon.objects.create(
            homework=hw,
            text=data["grammatical_phenomenon"]["text"]
        )
        # fill-in-the-blank
        for ex in data.get("fill_in_the_blank_exercises", []):
            FillInBlank.objects.create(
                homework=hw,
                sentence=ex["sentence_arabic"],
                hebrew_sentence=ex["sentence_hebrew"],
                options=ex["bank_words"],
                correct_option=ex["correct_answer"],
            )
        self.stdout.write(self.style.SUCCESS(" ✅ Stored all exercises.\n"))
