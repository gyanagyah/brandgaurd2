# ============================================================================
# evaluate.py — AI Evaluation Engine (Gemini API + RAG + Scoring)
# ============================================================================
# YEH FILE KYA KARTI HAI?
# -----------------------
# Ye BrandGuard ka CORE ENGINE hai — ye file sab ko connect karti hai:
#   1. retrive.py se relevant guidelines laati hai (RAG)
#   2. Gemini API ko prompt bhejti hai (text + image + guidelines)
#   3. Gemini se structured scores aur feedback maangti hai
#   4. scoring.py se final weighted score calculate karti hai
#   5. db.py mein results save karti hai
#
# GEMINI API KYA HAI? (Detailed)
# ──────────────────────────────
# Google ka AI model jo text AUR images dono samajhta hai.
# Hum isko:
#   - Post ka text bhejte hain
#   - Post ki image bhejte hain (optional)
#   - Brand guidelines bhejte hain (RAG se)
#   - Campaign objective batate hain
#   - Structured response maangte hain (JSON format mein scores + feedback)
#
# PROMPT ENGINEERING KYA HAI?
# ───────────────────────────
# AI se sahi answer lene ke liye sahi tarike se poochna.
# Jaise ek doctor se sirf "mujhe dard hai" bolne se kuch nahi hoga,
# par "mere left shoulder mein 3 din se dard hai, uthane mein problem hai"
# bolne se specific answer milega.
# Waise hi AI ko specific instructions dene se better output milta hai.
#
# STRUCTURED OUTPUT KYA HAI?
# ──────────────────────────
# AI se kahna ki "answer JSON format mein do" — taaki hum programmatically
# parse kar sakein. Nahi toh AI free text dega jo parse karna mushkil hai.
# ============================================================================

import os
import json
import base64                   # Images ko base64 encode karne ke liye
from dotenv import load_dotenv  # .env file se API key load karne ke liye
from google import genai        # Google Gemini AI SDK
from google.genai import types  # Gemini response types

import retrive                  # Hamari retrive.py (RAG retrieval)
import scoring                  # Hamari scoring.py (weighted scoring)
import db                       # Hamari db.py (database)

# ─── GEMINI API SETUP ───────────────────────────────────────────────────────
import streamlit as st

# 1. Local development ke liye data/.env file load karo
load_dotenv(os.path.join(os.path.dirname(__file__), "data", ".env"))

# 2. Pehle local environment (.env) se key check karo
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 3. Agar .env mein nahi mili (jaise Streamlit Cloud par), toh st.secrets se lo
if not GEMINI_API_KEY:
    try:
        GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY not found! Check data/.env or Streamlit Secrets.")

import os
import streamlit as st
from dotenv import load_dotenv
from google import genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# Gemini client initialize karo
client = genai.Client(api_key=GEMINI_API_KEY)


# ─── EVALUATION PROMPT ──────────────────────────────────────────────────────
# Ye prompt AI ko batata hai ki kya karna hai aur kaise karna hai.
# Prompt engineering ka ye core part hai — jitna specific prompt, utna accha output.

EVALUATION_PROMPT_TEMPLATE = """
You are BrandGuard, an expert AI brand compliance reviewer. Your job is to evaluate 
social media content before publication against the organisation's brand guidelines, 
product facts, and Indian advertising regulations.

## ORGANISATION'S GUIDELINES (Retrieved from Knowledge Base):
{guidelines}

## CONTENT TO EVALUATE:
**Campaign Objective:** {objective}
**Post Text:** {post_text}

## YOUR TASK:
Evaluate the content across these 7 categories. Give each a score from 0-100:

1. **Factual Accuracy (Weight: 20%)**: Are product details, statistics, and claims 
   correct based on the approved information in the guidelines?

2. **Regulatory Compliance (Weight: 20%)**: Does the content follow Indian advertising 
   laws (ASCI guidelines, Consumer Protection Act)? Are required disclaimers present?

3. **Brand Identity (Weight: 15%)**: Does the tone, vocabulary, and overall style 
   match the organisation's brand voice defined in the guidelines?

4. **Visual Consistency (Weight: 15%)**: Are logos, colours, and design elements used 
   correctly per brand guidelines? (If image provided, evaluate it; if not, score based 
   on text references to visuals.)

5. **Campaign Effectiveness (Weight: 10%)**: Does the content align with its stated 
   campaign objective ({objective})? Will it effectively achieve that goal?

6. **Accessibility (Weight: 10%)**: Is the content readable? Good text contrast? 
   Alt-text considerations? Clear language?

7. **Overall Design (Weight: 10%)**: Layout quality, visual appeal, and how effectively 
   the content communicates its message.

## CRITICAL CHECKS:
Flag any of these as critical issues (these will OVERRIDE the score, even if high):
- Unsupported or misleading claims
- Missing mandatory disclaimers/disclosures
- False product information
- Regulatory/legal violations
- Unauthorised logo usage
- Offensive or discriminatory content

## RESPONSE FORMAT:
You MUST respond in this exact JSON format (no other text, just JSON):
{{
    "scores": {{
        "factual_accuracy": <0-100>,
        "regulatory_compliance": <0-100>,
        "brand_identity": <0-100>,
        "visual_consistency": <0-100>,
        "campaign_effectiveness": <0-100>,
        "accessibility": <0-100>,
        "overall_design": <0-100>
    }},
    "critical_flags": [
        "<critical issue 1 if any>",
        "<critical issue 2 if any>"
    ],
    "category_feedback": {{
        "factual_accuracy": "<detailed feedback for this category>",
        "regulatory_compliance": "<detailed feedback>",
        "brand_identity": "<detailed feedback>",
        "visual_consistency": "<detailed feedback>",
        "campaign_effectiveness": "<detailed feedback>",
        "accessibility": "<detailed feedback>",
        "overall_design": "<detailed feedback>"
    }},
    "suggestions": [
        {{
            "issue": "<what the specific error is>",
            "risk": "<why it poses a risk to the brand>",
            "guideline_reference": "<which guideline/rule supports this>",
            "fix": "<how the creator can fix it>"
        }}
    ],
    "overall_summary": "<2-3 sentence summary of the evaluation>"
}}
"""


# ─── MAIN EVALUATION FUNCTION ───────────────────────────────────────────────

def evaluate_post(text_content, campaign_objective, image_path=None, 
                  submission_id=None):
    """
    MAIN FUNCTION — Post ko evaluate karo aur scores + feedback do.
    
    YE FUNCTION POORA PIPELINE CHALATA HAI:
    1. RAG: relevant guidelines retrieve karo
    2. PROMPT: guidelines + post content ko ek prompt mein combine karo
    3. GEMINI: AI se evaluation maango
    4. SCORING: weighted score calculate karo + critical checks
    5. DB: results save karo
    
    PARAMETERS:
        text_content: str — post ka text
        campaign_objective: str — post ka goal (brand_awareness, lead_gen, etc.)
        image_path: str (optional) — post ki image ka path
        submission_id: int (optional) — agar DB mein submission already hai
    
    RETURNS:
        dict — complete evaluation result
    """
    print(f"\n🔍 Starting evaluation...")
    print(f"   📝 Text: {text_content[:100]}...")
    print(f"   🎯 Objective: {campaign_objective}")
    
    # ─── STEP 1: RAG — Relevant guidelines retrieve karo ─────────────────
    print("   📚 Step 1: Retrieving relevant guidelines...")
    
    guidelines_text, raw_guidelines = retrive.retrieve_and_format(
        query_text=text_content,
        n_results=5
    )
    # guidelines_text = formatted string of relevant chunks
    # raw_guidelines = list of raw chunk objects
    
    guideline_sources = [g["source"] for g in raw_guidelines]
    print(f"   📚 Found {len(raw_guidelines)} relevant guideline chunks from: "
          f"{', '.join(set(guideline_sources)) if guideline_sources else 'none'}")
    
    # ─── STEP 2: PROMPT — Sab info combine karo ──────────────────────────
    print("   ✏️ Step 2: Building evaluation prompt...")
    
    prompt = EVALUATION_PROMPT_TEMPLATE.format(
        guidelines=guidelines_text,
        objective=campaign_objective,
        post_text=text_content if text_content else "(No text content provided)"
    )
    # .format() → template mein {placeholders} ko actual values se replace karo
    
    # ─── STEP 3: GEMINI API CALL ─────────────────────────────────────────
    print("   🤖 Step 3: Calling Gemini AI for evaluation...")
    
    try:
        # Content parts banao (text + optional image)
        contents = [prompt]
        
        # Agar image hai toh use bhi bhejo
        if image_path and os.path.exists(image_path):
            print(f"   🖼️ Including image: {image_path}")
            # Image ko base64 encode karo
            # Base64 = binary data ko text mein convert karna (AI API ko bhejne ke liye)
            with open(image_path, "rb") as img_file:
                image_bytes = img_file.read()
            
            # Image ka MIME type detect karo
            mime_type = "image/jpeg"  # Default
            if image_path.lower().endswith(".png"):
                mime_type = "image/png"
            elif image_path.lower().endswith(".gif"):
                mime_type = "image/gif"
            elif image_path.lower().endswith(".webp"):
                mime_type = "image/webp"
            
            # Gemini ko image part bhejo
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type,
            )
            contents = [prompt, image_part]
        
        # Gemini API call karo
        response = client.models.generate_content(
            model="gemini-3.6-flash",   # Fast aur capable model
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.2,         # Low temperature = more consistent/factual output
                # Temperature: 0.0 = very deterministic, 1.0 = very creative
                # Evaluation ke liye low temperature chahiye kyunki hum consistent scores chahte
            ),
        )
        
        raw_response = response.text
        print(f"   ✅ Gemini response received ({len(raw_response)} chars)")
        
    except Exception as e:
        print(f"   ❌ Gemini API error: {e}")
        return {
            "status": "error",
            "message": f"AI evaluation failed: {str(e)}",
        }
    
    # ─── STEP 4: RESPONSE PARSE KARO ─────────────────────────────────────
    print("   📊 Step 4: Parsing AI response...")
    
    try:
        # JSON response ko parse karo
        # Kabhi kabhi AI extra text add kar deta hai JSON ke around
        # Isliye pehle JSON part dhundhte hain
        json_str = raw_response.strip()
        
        # Agar response ```json ... ``` mein wrapped hai toh unwrap karo
        if json_str.startswith("```"):
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
        json_str = json_str.strip()
        
        ai_result = json.loads(json_str)
        # json.loads() → JSON string ko Python dict mein convert karo
        
    except json.JSONDecodeError as e:
        print(f"   ⚠️ JSON parse error: {e}")
        print(f"   Raw response: {raw_response[:500]}")
        # Fallback: default scores use karo
        ai_result = {
            "scores": {
                "factual_accuracy": 50, "regulatory_compliance": 50,
                "brand_identity": 50, "visual_consistency": 50,
                "campaign_effectiveness": 50, "accessibility": 50,
                "overall_design": 50
            },
            "critical_flags": [],
            "category_feedback": {},
            "suggestions": [],
            "overall_summary": f"Evaluation parsing failed. Raw response: {raw_response[:200]}"
        }
    
    # ─── STEP 5: SCORING — Weighted score calculate karo ─────────────────
    print("   📈 Step 5: Calculating weighted scores...")
    
    category_scores = ai_result.get("scores", {})
    critical_flags = ai_result.get("critical_flags", [])
    # Khali strings filter karo critical flags se
    critical_flags = [f for f in critical_flags if f and f.strip()]
    
    # Overall feedback text combine karo (for critical keyword detection)
    feedback_text = ai_result.get("overall_summary", "")
    for cat, fb in ai_result.get("category_feedback", {}).items():
        feedback_text += " " + fb
    
    # Scoring engine se final result lo
    final_result = scoring.generate_final_result(
        category_scores=category_scores,
        feedback_text=feedback_text,
        critical_flags_from_ai=critical_flags,
    )
    
    # AI ke extra data bhi add karo result mein
    final_result["category_feedback"] = ai_result.get("category_feedback", {})
    final_result["suggestions"] = ai_result.get("suggestions", [])
    final_result["overall_summary"] = ai_result.get("overall_summary", "")
    final_result["guideline_sources"] = guideline_sources
    final_result["status"] = "success"
    
    print(f"   🎯 Overall Score: {final_result['overall_score']}/100")
    print(f"   📋 Decision: {final_result['decision']}")
    
    # ─── STEP 6: DB MEIN SAVE KARO ──────────────────────────────────────
    if submission_id:
        print(f"   💾 Step 6: Saving results to database...")
        eval_id = db.save_evaluation(
            submission_id=submission_id,
            scores={
                "overall_score": final_result["overall_score"],
                **category_scores,  # ** = dict unpack (merge all key-values)
            },
            critical_flags=final_result["critical_flags"],
            feedback={
                "category_feedback": final_result["category_feedback"],
                "overall_summary": final_result["overall_summary"],
            },
            suggestions=final_result["suggestions"],
            has_critical=final_result["has_critical_issues"],
        )
        final_result["evaluation_id"] = eval_id
        print(f"   ✅ Saved as evaluation ID: {eval_id}")
    
    # Score report print karo
    print(scoring.format_score_report(final_result))
    
    return final_result


def quick_evaluate(text, objective="brand_awareness"):
    """
    Quick evaluation — bina DB save kiye sirf scores aur feedback lo.
    Testing aur debugging ke liye useful hai.
    """
    return evaluate_post(
        text_content=text,
        campaign_objective=objective,
        submission_id=None,  # DB mein save nahi hoga
    )
