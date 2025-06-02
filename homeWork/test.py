import re
import openai
import json
import os
import sys
import django
import datetime

# 🟢 שלב 1: הוסף את שורש הפרויקט ל־PYTHONPATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

# 🟢 שלב 2: הגדר את מודול ההגדרות של Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "asliBackend.settings")

# 🟢 שלב 3: הפעל את ההגדרות של Django
django.setup()


def import_models():
    global Homework, VocabularyMatch, FillInBlank, GrammaticalPhenomenon, User
    from homeWork.models import Homework, VocabularyMatch, FillInBlank, GrammaticalPhenomenon
    from django.contrib.auth import get_user_model
    User = get_user_model()


import_models()

# 🟢 שלב 4: רק עכשיו תייבא את המודלים

# הגדר את המפתח שלך

# שלב 1: טען את התמלול מהקובץ
transcript_path = os.path.join(os.path.dirname(__file__), "transcript.text")
with open(transcript_path, "r", encoding="utf-8") as file:
    transcript = file.read()

# שלב 2: הודעה למערכת - להחזיר רק JSON
system_message = {
    "role": "system",
    "content": (
        "You are a helpful assistant. Return ONLY valid JSON. "
        "No additional text, no markdown formatting, and no explanations."
    )
}

user_prompt = """
פרומפט ליצירת סיכום שיעור בערבית פלסטינית (תעתיק עברי) + יצירת פעילויות מבוססות המודל שלנו

חוקי התוכן והשפה (מעודכן):
1. כתוב את כל התוכן בערבית פלסטינית (לא ספרותית).
2. כל מילה בודדת בערבית (שאינה בתוך משפט מלא) תופיע כך: <ערבית> ‎(<תעתיק עברי>). למשל: كتاب ‎(כִּתַאבּ)
3. אל תשתמש בשום סוגריים אחרים מלבד הפורמט שבסעיף 2.
4. בפעילות “השלם את המשפט” (fill_in_the_blank_exercises) החזר שני שדות נפרדים:
   • **sentence_arabic** – משפט מלא בערבית בלבד עם `___`.  
   • **sentence_hebrew** – אותו משפט בתעתיק עברי עם `___`.  
   אין מעבר־שורה בתוך אחד השדות.
5. הקפד על הגייה ואותיות (א‑ב‑ג'‑ד וכו') לפי הטבלה שלנו.

מבנה הסיכום הנדרש:

#תופעה תחבירית חדשה  
הסבר בעברית + דוגמאות בערבית (עם תעתיק, לפי סעיף 2) + תרגום.

#אוצר מילים חדש  
15 פריטים:  
- arabic_word  מילה בודדת לפי סעיף 2  
- hebrew_word  התרגום לעברית

#שיעורי בית  
15 תרגילי “השלם את המשפט” כמתואר בסעיף 4.  
בשדות **correct_answer** ו‑**bank_words** השתמש בפורמט סעיף 2.

החזר **אך ורק** JSON במבנה הבא (ללא טקסט נוסף):

{
  "vocab_matches": [
    {
      "arabic_word": "<ערבית‑בודדה> ‎(<תעתיק‑עברי>)",
      "hebrew_word": "<תרגום‑עברית>"
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
      "correct_answer": "<ערבית‑בודדה> ‎(<תעתיק‑עברי>)",
      "bank_words": [
        "<ערבית‑בודדה> ‎(<תעתיק‑עברי>)",
        "<ערבית‑בודדה> ‎(<תעתיק‑עברי>)",
        "<ערבית‑בודדה> ‎(<תעתיק‑עברי>)"
      ]
    }
    // … 14 נוספים
  ]
}
"""


#                        )  # הגדר את המפתח שלך כאן
try:
    print("Start")
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {"role": "system",
                "content": "You are a helpful assistant. Return ONLY valid JSON."},
            {"role": "user", "content": user_prompt},
            {"role": "user", "content": f"תמלול השיעור:\n\n{transcript}"}
        ]
    )
    print("finish")
except:
    print("Somthing went wrong")


generated_json = response.choices[0].message.content
print(generated_json)


def extract_json_block(text):
    # gpt regex i dont get it!
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    return match.group(1) if match else text


generated_json = extract_json_block(generated_json)
try:
    parsed_data = json.loads(generated_json)
except json.JSONDecodeError as e:
    raise e


def create_homework_from_response(api_json):
    """
    Given the JSON structure from your API response, create the related
    Homework, VocabularyMatch, FillInBlank, and GrammaticalPhenomenon objects.
    Return the newly created Homework instance.
    """

    user = User.objects.get(email="idorabin60@gmail.com")
    homework = Homework.objects.create(
        due_date=datetime.date.today(), user=user)

    # Vocabulary
    for match in api_json["vocab_matches"]:
        VocabularyMatch.objects.create(
            homework=homework,
            arabic_word=match["arabic_word"],
            hebrew_word=match["hebrew_word"],
        )

    # Grammatical phenomenon
    GrammaticalPhenomenon.objects.create(
        homework=homework,
        text=api_json["grammatical_phenomenon"]["text"],
    )

    for ex in api_json["fill_in_the_blank_exercises"]:
        FillInBlank.objects.create(
            homework=homework,
            sentence=ex["sentence_arabic"],
            hebrew_sentence=ex["sentence_hebrew"],
            options=json.dumps(ex["bank_words"]),
            correct_option=ex["correct_answer"],
        )

    return homework


create_homework_from_response(parsed_data)
print("done")
