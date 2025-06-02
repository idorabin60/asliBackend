# views.py

import os
import json
import traceback
import openai
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from dotenv import load_dotenv

load_dotenv()


@csrf_exempt
def gpt_chat_view(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    raw_body = request.body
    print("▶️ RAW request.body:", raw_body)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
        print("▶️ Parsed payload:", payload)
        prompt = payload.get("prompt", "").strip()
        if not prompt:
            return JsonResponse({"error": "Missing 'prompt' in request body."}, status=400)
    except json.JSONDecodeError as jde:
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)

    openai.api_key = os.getenv("OPEN_AI_API_KEY")
    if not openai.api_key:
        return JsonResponse({"error": "OPENAI_API_KEY not set in environment."}, status=500)

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        assistant_reply = response.choices[0].message.content.strip()
        return JsonResponse({"response": assistant_reply})

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"error": f"OpenAI API error: {str(e)}"}, status=500)
