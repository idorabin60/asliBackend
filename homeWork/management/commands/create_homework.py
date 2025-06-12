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

                file_path = self.download_file(file_id, file_name, creds)
                document_content = self.read_docx(file_path)
                homework_text = self.generate_homework(document_content)
                text_for_lingo = """
{
  "vocab_matches": [
    { "arabic_word": "سلام ‎(סַלַאם)", "hebrew_word": "שלום" },
    { "arabic_word": "مرحبا ‎(מַרְחַבַּא)", "hebrew_word": "שלום (היי)" },
    { "arabic_word": "صباح ‎(צַבַּאח)", "hebrew_word": "בוקר" },
    { "arabic_word": "كيف ‎(כֵּיף)", "hebrew_word": "איך" },
    { "arabic_word": "قهوة ‎(קַהְוֶה)", "hebrew_word": "קפה" },
    { "arabic_word": "ميّة ‎(מַיִּה)", "hebrew_word": "מים" },
    { "arabic_word": "أكل ‎(אַקַל)", "hebrew_word": "אוכל" },
    { "arabic_word": "بدي ‎(בִּדִּי)", "hebrew_word": "אני רוצה" },
    { "arabic_word": "تمام ‎(תַמַאם)", "hebrew_word": "בסדר" },
    { "arabic_word": "وين ‎(וֵין)", "hebrew_word": "איפה" },
    { "arabic_word": "شو ‎(שׁוּ)", "hebrew_word": "מה" },
    { "arabic_word": "هلا ‎(הַלַא)", "hebrew_word": "עכשיו / היי" },
    { "arabic_word": "شوي ‎(שְׁוַי)", "hebrew_word": "קצת" },
    { "arabic_word": "جاهز ‎(גַ׳אהֶז)", "hebrew_word": "מוכן" },
    { "arabic_word": "بكرة ‎(בֻּכְרֶה)", "hebrew_word": "מחר" },
    { "arabic_word": "إسا ‎(אִסַּא)", "hebrew_word": "עכשיו" },
    { "arabic_word": "دقيقة ‎(דַקִּיקַה)", "hebrew_word": "דקה" },
    { "arabic_word": "خلص ‎(חַלַּס)", "hebrew_word": "סיים" },
    { "arabic_word": "خير ‎(חֵיר)", "hebrew_word": "טוב" },
    { "arabic_word": "هون ‎(הוֹן)", "hebrew_word": "כאן" }
  ],
  "grammatical_phenomenon": {
    "text": "בפלסטינית המדוברת שמים ‎\"بدي‎\" ‎(בִּדִּי) לפני פועל או שם־עצם כדי להביע רצון או צורך.\n\nדוגמאות:\n1. بدي ‎(בִּדִּי) قهوة ‎(קַהְוֶה) – אני רוצה קפה.\n2. بدي ‎(בִּדִּי) أشرب ‎(אַשְרַב) ميّة ‎(מַיִּה) – אני רוצה לשתות מים.\n3. بدي ‎(בִּדִּי) أروح ‎(אַרוּח) עالبيت – אני רוצה ללכת הביתה."
  },
  "fill_in_the_blank_exercises": [
    {
      "sentence_arabic": "سلام، ___ حالك اليوم تمام؟",
      "sentence_hebrew": "סַלַאם, ___ חַאלַכּ אִלְיוֹם תַמַאם?",
      "correct_answer": "كيف ‎(כֵּיף)",
      "bank_words": [
        "كيف ‎(כֵּיף)",
        "وين ‎(וֵין)",
        "شو ‎(שׁוּ)"
      ]
    },
    {
      "sentence_arabic": "بدي أعمل ___ مع حليب وسكر.",
      "sentence_hebrew": "בִּדִּי אַעְמַל ___ מַעַ חַלִיבּ וּסֻכַּר.",
      "correct_answer": "قهوة ‎(קַהְוֶה)",
      "bank_words": [
        "ميّة ‎(מַיִּה)",
        "قهوة ‎(קַהְוֶה)",
        "أكل ‎(אַקַל)"
      ]
    },
    {
      "sentence_arabic": "إذا عطشان خذ ___ من التلاجة.",
      "sentence_hebrew": "אִזַא עַטְשַאן ח'וּד ___ مִן أִתַּלַאגֶ'ה.",
      "correct_answer": "ميّة ‎(مַיִּה)",
      "bank_words": [
        "قهوة ‎(קַהְוֶה)",
        "أكل ‎(אַקَال)",
        "ميّة ‎(مַיִּה)"
      ]
    },
    {
      "sentence_arabic": "شو، ___ رايح اليوم بعد المدرسة؟",
      "sentence_hebrew": "שׁוּ, ___ רַאיֵח أִלְיוּם בַּעְד أִלְמַדְرַסֶה?",
      "correct_answer": "وين ‎(וֵין)",
      "bank_words": [
        "وين ‎(וֵין)",
        "הلا ‎(הַלַא)",
        "تمام ‎(תַמַאם)"
      ]
    },
    {
      "sentence_arabic": "سلام يا صاحبي، ___ بدك تاكل الليلة؟",
      "sentence_hebrew": "סְלַאם יَا צַחְבִּי, ___ بִדַּכּ תַאכּُل אִלְלֵילֶה?",
      "correct_answer": "شو ‎(שׁוּ)",
      "bank_words": [
        "תַמַאם ‎(תַמַאם)",
        "שו ‎(שׁוּ)",
        "קַהְוֶה ‎(קַהְוֶה)"
      ]
    },
    {
      "sentence_arabic": "أنا ___ أشوف فيلم جديد اليوم.",
      "sentence_hebrew": "אַנַא ___ אַשוּף פִילְם גַ׳דִיד אִלְיוּם.",
      "correct_answer": "بدي ‎(בִּדִּי)",
      "bank_words": [
        "ميّة ‎(מַיִּה)",
        "קַהְוֶה ‎(קַהְוֶה)",
        "בִּדִּי ‎(בִּדִּי)"
      ]
    },
    {
      "sentence_arabic": "الحمد لله، الجو اليوم ___ وما في مطر.",
      "sentence_hebrew": "אַלְחַמְדֻ לִלָּה, أִלְגַ׳וּ אִלְיוּם ___ וּמַא פִי مַטַר.",
      "correct_answer": "תַמַאם ‎(תַמַאם)",
      "bank_words": [
        "תַמַאם ‎(תַמַאם)",
        "וֵין ‎(וֵין)",
        "شְׁוַי ‎(שְׁוַי)"
      ]
    },
    {
      "sentence_arabic": "___ عليكم، شو الأخبار يا جماعة؟",
      "sentence_hebrew": "___ עַלֵיכֻּם, שׁוּ أִלְאַחְ׳בַּאר יַא גַ׳מַאעַה?",
      "correct_answer": "סַלַאם ‎(סַלַאם)",
      "bank_words": [
        "וֵין ‎(וֵין)",
        "סַלַאם ‎(סַלַאם)",
        "כֵּיף ‎(כֵּיף)"
      ]
    },
    {
      "sentence_arabic": "خلصت الدوام، بنبدا ___ نطبخ العشاء؟",
      "sentence_hebrew": "חַלַצְתּ אִדַּוַאם, בְּנִבְּדַא ___ نִטְבֻּח אִלְעַשַא?",
      "correct_answer": "הַלַא ‎(הַלַא)",
      "bank_words": [
        "מַיִּה ‎(مַיִּה)",
        "וֵין ‎(וֵין)",
        "הַלַא ‎(הַלַא)"
      ]
    },
    {
      "sentence_arabic": "نسيت أشرب ___ بعد الرياضة.",
      "sentence_hebrew": "נְסִית אַשְרַב ___ بַּעְד أִרְרִיַאדַה.",
      "correct_answer": "مَיִּה ‎(מַיִּה)",
      "bank_words": [
        "מַיִּה ‎(מַיִּה)",
        "קַהְוֶה ‎(קַהְוֶה)",
        "אֲכַל ‎(אֲכַל)"
      ]
    },
    {
      "sentence_arabic": "حط ___ ملح على السلطة مو كتير.",
      "sentence_hebrew": "חֻט ___ מֶלַח עַלַא אִסַּלַטַה מוּ כְּתִיר.",
      "correct_answer": "שְׁוַי ‎(שְׁוַי)",
      "bank_words": [
        "קַהְוֶה ‎(קַהְוֶה)",
        "שְׁוַי ‎(שְׁוַי)",
        "תַמַאם ‎(תַמַאם)"
      ]
    },
    {
      "sentence_arabic": "عملت ___ كتير طيب لولادي היום.",
      "sentence_hebrew": "עַמַלְתּ ___ כְּתִיר טַייַּבּ לְוְלַאדִי أִלְיוּם.",
      "correct_answer": "أֲכַל ‎(אֲכַל)",
      "bank_words": [
        "מַיִּה ‎(מַיִּה)",
        "קַהְוֶה ‎(קַהְוֶה)",
        "אֲכַל ‎(אֲכַל)"
      ]
    },
    {
      "sentence_arabic": "الغدا ___ على الطاولة تستنى فيك.",
      "sentence_hebrew": "אِلְעַ׳דַא ___ عَلَى أִט־טַאוּלֶה תִסְתַנַּא פִיכּ.",
      "correct_answer": "גַ׳אהֶז ‎(גַ׳אהֶז)",
      "bank_words": [
        "גַ׳אהֶז ‎(גַ׳אהֶז)",
        "וֵין ‎(וֵין)",
        "שְׁוַי ‎(שְׁוַי)"
      ]
    },
    {
      "sentence_arabic": "مرحبا يا أميرة، ___ عملت الواجب؟",
      "sentence_hebrew": "מַרְחַבַּא יַא אַמִירַה, ___ עַמַלְתּ أִלְוַاجִ׳בּ?",
      "correct_answer": "כֵּיף ‎(כֵּיף)",
      "bank_words": [
        "וֵין ‎(וֵין)",
        "כֵּיף ‎(כֵּיף)",
        "בֻּכְרֵה ‎(בֻּכְרֵה)"
      ]
    },
    {
      "sentence_arabic": "خلص الشغل اليوم، بنرجع ___ الصبح.",
      "sentence_hebrew": "חַלַץ אִשְשֻע׳ל أִלְיוּם, בִּנִרְגַ׳ע ___ אֻצֻּבַּח.",
      "correct_answer": "بֻּכְרֵה ‎(بֻּכְרֵה)",
      "bank_words": [
        "שְׁוַי ‎(שְׁוַי)",
        "תַמַאם ‎(תַמַאם)",
        "بֻּכְרֵה ‎(بֻּכְרֵה)"
      ]
    },
    {
      "sentence_arabic": "استنى ___ وبعدين منطلع مع بعض.",
      "sentence_hebrew": "אִסְתַנַּא ___ וּبַּעְדֵין مִנִטְלַע مַעַ בַּעְד.",
      "correct_answer": "שְׁוַי ‎(שְׁוַי)",
      "bank_words": [
        "שְׁוַי ‎(שְׁוַי)",
        "מַיִּה ‎(מַיִּה)",
        "קַהְוֶה ‎(קַהְוֶה)"
      ]
    },
    {
      "sentence_arabic": "___, בִּדִּי אַחְכִּי מַעַכּ דַקִּיקַה בַּס.",
      "sentence_hebrew": "___, בִּדִּי אַחְכִּי مַעַכּ דַקִּיקַה بַּס.",
      "correct_answer": "سَلَام ‎(סַלַאם)",
      "bank_words": [
        "כֵּיף ‎(כֵּיף)",
        "סַלַאם ‎(סַלַאם)",
        "וֵין ‎(וֵין)"
      ]
    },
    {
      "sentence_arabic": "خلصنا الدرس وراجعين البيت ___ ان شاء الله.",
      "sentence_hebrew": "חַלַצְנַא أִלְדַרְס וּרַאגְ׳עִין אִלְבֵּית ___ אינ שַׁא אַללַּה.",
      "correct_answer": "תַמַאם ‎(תַמַאם)",
      "bank_words": [
        "כֵּיף ‎(כֵּיף)",
        "שְׁוַי ‎(שְׁוַי)",
        "תַמַאם ‎(תַמַאם)"
      ]
    },
    {
      "sentence_arabic": "بدك تطلع ___ ولا تستنى شوي؟",
      "sentence_hebrew": "בִּדַּכּ تִטְלַע ___ וَلَّا תִسְתַנַּא שְׁוַי?",
      "correct_answer": "אִסַּא ‎(אִסַּא)",
      "bank_words": [
        "אִסַּא ‎(אִסַּא)",
        "בֻּכְרֵה ‎(בֻּכְרֵה)",
        "מַיִּה ‎(מַיִּה)"
      ]
    },
    {
      "sentence_arabic": "ما ___ الأكل לִסַּא, ובַּסְתַנַּא דַקִּיקַה.",
      "sentence_hebrew": "ما ___ الأكل לִסַּא, ובַּסְתַנַּא דַקִּיקַה.",
      "correct_answer": "חַלַּס ‎(חַלַּס)",
      "bank_words": [
        "מַיִּה ‎(מַיִּה)",
        "חַלַּס ‎(חַלַּס)",
        "קַהְוֶה ‎(קַהְوֶה)"
      ]
    }
  ]
}
"""

                self.create_homework_from_json(
                    email, json.loads(text_for_lingo), file_id)

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
        user_prompt = """}פרומפט ליצירת סיכום שיעור בערבית מדוברת (תעתיק עברי) + יצירת פעילויות מבוססות המודל שלנו
חוקי התוכן והשפה (מעודכן):
1.	כתוב את כל התוכן בערבית מדוברת (לא ספרותית, לא דיאלקט זר).
2.	כל מילה בודדת בערבית (שאינה בתוך משפט מלא) תופיע כך: ערבית ‎(<תעתיק עברי>) למשל: كتاب ‎(כִּתַאבּ) --- ללא ‎<‎…‎> (אין סוגריים משולשים). • בתוך ‎( … ) מותרות אך ורק אותיות עבריות מנוקדות; אין רווחים, ספרות או אותיות ערביות. • مثال שגוי: كتاب ‎(كِתַאבּ) ❌ נכון: كتاب ‎(כִּתַאבּ) ✔
3.	אל תשתמש בשום סוגריים אחרים מלבד הפורמט שבסעיף 2.
4.	בפעילות “השלם את המשפט” החזר שני שדות נפרדים: • sentence_arabic – משפט מלא בערבית בלבד שבו מופיע ‎___ (רצף קו תחתון אחד) במקום המילה החסרה. • sentence_hebrew – אותו משפט בתעתיק עברי, גם הוא עם ‎___ באותו מקום. אין לכלול את התשובה הנכונה בגוף המשפטים.
5.	הקפד על הגייה ואותיות (א-ב-ג'-ד וכו') לפי הטבלה שלנו. • השתמש אך ורק במפת התעתיק המוסכמת (ب=בּ, ت=ת, ج=ג׳, خ=ח׳, …). • כל תעתיק חייב לכלול לפחות סימן ניקוד אחד (ַ ָ ִ ֵ ֻ ּ …).
6.	זיהוי אוצר מילים חדש • כלול רק מילים שאינן ב־known_vocab של התלמיד. • מילה חייבת להופיע בתמלול ≥ 2 פעמים או להיות מסומנת במפורש כמילה חדשה. • אל תכלול מילים פשוטות/תפקודיות (כינויי גוף, “של”, “עם”…). • בחר מילים מאתגרות אך תואמות לרמת הלומד; אל תמציא מילים.
7.	בניית תרגילי השלמה • מינימום 5 מילים בכל משפט. • שלב את המילים החדשות שאותרו. • הצג תופעות דקדוק מתאימות. •ודא שהcorrect answer מופיעה בדיוק שליש מהפעמים כאופציה הראשונה בדיוק שליש כאופציה השנייה ובדיוק שליש כאופציה השלישית בbankwords דאג שאתה לא עושה שליש ראשונה רצוף שליש שנייה רצוף... אלא מערבל • ודא תשובה נכונה אחת בלבד; המילים ב־bank_words יהיו רלוונטיות ובתוכן חייב להופיע גם ה־correct_answer, • ודא שרק ה־correct_answer מתאימה ל־___; כל מילה אחרת ב־bank_words צריכה להיות בלתי־מתאימה בהקשר. שים לב להשתמש במילות קישור,כינויי שייכות ויידוע במידת הצורך כדי שלמשפטים שיצרת יהיה מבנה תחבירי נכון- גם על המילים בבנק וורד או על המילה הנכונה במידת הצורך “אם שם העצם במשפט צריך להיות מיודע (או בלתי־מיודע) לפי התחביר, כתוב אותו ככה גם ב-sentence_arabic וגם ב-bank_words. אל תשאיר ללומד להחליט אם להוסיף الـ.”
כחלק מבניית המשפטים והשדות, את השדה correct answer תמלא באחת מהאופציות מהbamk words  כשהיא מועתקת אליו בדיוק.
8.	רהיטות ומקצועיות בלבד; אל תשתמש בשפה בוטה.
QA פנימי (חובה לפני שליחה)
1.ודא שאין בתוך התעתיק העברי אותיות ערביות - רק אותיות עבריות וניקוד עברי. ודא שמה שכתוב בcorrect answer זהה בדיוק בכל אות ואות לאופציה הנכונה מבין הbank word 2. לכל משפט יש בדיוק correct_answer אחד אפשרי. - לדוגמה משפט: "اليوم بدي أطبخ ___ خروف." bank_words: [رز, كنافة, لحمة] רק “لحمة” תקין; “رز” / “كنافة” יצאו מגוחכים בהקשר. 3. כל תעתיק עומד במפת התעתיק וכולל ניקוד. 4. רק לאחר בדיקה זו החזר את ה־JSON. 5. ודא שאין משפטים הזוים שאין בהם הגיון או שחסר בהם מרכיב קריטי במשפט כמו למשל "sentence_arabic": "___ اليوم كان مليان سياح.", "sentence_hebrew": "___ אִלְיוֹם כַּאן מַלְיַאן סִיַאח.", "correct_answer": "مكتبة ‎(מַכְּתַבֵּה)",
אין למשפט שום משמעות הגיונית ולכן מחק אותו וצור חדש עם הגיון במקומו מבנה הסיכום הנדרש
6. עבור על כל המילים בbank word ובcorrect answer
אם מצאת מילה בתעתיק שיש בה אות ערבית כמו כאן 
"بֵּיטִنְגַ׳אן" החלף חזרה את האותיות הערביות לעבריות ותקבל מילה תקינה- בֵּיטִנְגַ׳אן
 
 

#תופעה תחבירית חדשה הסבר בעברית + דוגמאות בערבית (עם תעתיק, לפי סעיף 2) + תרגום.
#אוצר מילים חדש 20 פריטים:
•	arabic_word  מילה בודדת לפי סעיף 2
•	hebrew_word  התרגום לעברית
#שיעורי בית 20 תרגילי “השלם את המשפט” כמתואר בסעיף 4. בשדות correct_answer ו־bank_words השתמש בפורמט סעיף 2.
החזר אך ורק JSON במבנה הבא (ללא טקסט נוסף):
{ "vocab_matches": [ { "arabic_word": "كتاب ‎(כִּתַאבּ)", "hebrew_word": "ספר" } // … 19 נוספים ], "grammatical_phenomenon": { "text": "<הסבר בעברית + דוגמאות בפורמט הנדרש + תרגום>" }, "fill_in_the_blank_exercises": [ { "sentence_arabic": "أنا بحب ___", "sentence_hebrew": "אנה בחב ___", "correct_answer": "كتاب ‎(כִּתַאבּ)", "bank_words": [ "كتاب ‎(כִּתַאבּ)", "دفتر ‎(דַפְתַר)", "قلم ‎(קַלַם)" ] } // … 19נוספים ] }
"""
        full_messages = [
            system_message,
            {"role": "user", "content": user_prompt},
            {"role": "user", "content": f"תמלול השיעור:\n\n{content}"}
        ]
        resp = openai.chat.completions.create(
            model="o3",
            temperature=1,
            messages=full_messages,
        )
        raw = resp.choices[0].message.content
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
        for item in data.get("vocab_matches", []):
            VocabularyMatch.objects.create(
                homework=hw,
                arabic_word=item["arabic_word"],
                hebrew_word=item["hebrew_word"],
            )
        GrammaticalPhenomenon.objects.create(
            homework=hw,
            text=data["grammatical_phenomenon"]["text"]
        )
        for ex in data.get("fill_in_the_blank_exercises", []):
            FillInBlank.objects.create(
                homework=hw,
                sentence=ex["sentence_arabic"],
                hebrew_sentence=ex["sentence_hebrew"],
                options=ex["bank_words"],
                correct_option=ex["correct_answer"],
            )
        self.stdout.write(self.style.SUCCESS(" ✅ Stored all exercises.\n"))
