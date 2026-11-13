# ============================================================================
# evaluate.py — AI Evaluation Engine (Groq API + RAG + Scoring)
# ============================================================================

import os
import json
import base64
import time
import re
from dotenv import load_dotenv
from groq import Groq

import retrive
import scoring
import db

# ─── GROQ API SETUP ─────────────────────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), "data", ".env"))
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    try:
        import streamlit as st
        GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
    except Exception:
        pass

if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY not found! Check data/.env or Streamlit Secrets.")

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)


def _get_available_groq_models(needs_vision=False):
    """Fetch active models directly from your Groq account."""
    try:
        models_resp = client.models.list()
        available_ids = [
            m.id for m in models_resp.data
            if "whisper" not in m.id.lower()
            and "guard" not in m.id.lower()
            and "tts" not in m.id.lower()
            and "embed" not in m.id.lower()
        ]
        if needs_vision:
            vision = [m for m in available_ids if "vision" in m.id.lower() or "llama-4" in m.id.lower()]
            return vision if vision else available_ids

        # Prioritize larger general-purpose chat models first
        preferred = sorted(
            available_ids,
            key=lambda x: (
                0 if "70b" in x.lower() else
                1 if "llama-4" in x.lower() else
                2 if "qwen" in x.lower() or "deepseek" in x.lower() or "gpt" in x.lower() else
                3
            )
        )
        return preferred
    except Exception as e:
        print(f"   WARNING: Could not list Groq models ({e}), using fallback list.")
        return ["llama-3.3-70b-versatile", "meta-llama/llama-4-scout-17b-16e-instruct"]


# ─── EVALUATION PROMPT ──────────────────────────────────────────────────────

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
You MUST respond in this exact JSON format (no markdown, no extra text, just valid JSON):
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
        "<critical issue 1 if any>"
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


def _parse_json_response(raw_response):
    """Extract JSON from AI response with fallback strategies."""
    text = raw_response.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    return None


def _encode_image_to_data_url(image_path):
    """Encode local image file to base64 data URI for Groq Vision models."""
    with open(image_path, "rb") as img_file:
        b64_data = base64.b64encode(img_file.read()).decode("utf-8")

    ext = image_path.lower().rsplit(".", 1)[-1]
    mime_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    mime_type = mime_map.get(ext, "image/jpeg")
    return f"data:{mime_type};base64,{b64_data}"


def evaluate_post(text_content, campaign_objective, image_path=None,
                  submission_id=None, max_retries=3):
    """Evaluate post using Groq API + RAG + Scoring Engine."""
    print("\nStarting evaluation with Groq...")
    print(f"   Text: {str(text_content)[:100]}...")
    print(f"   Objective: {campaign_objective}")

    # ── STEP 1: RAG — Retrieve relevant guidelines ───────────────────────────
    print("   Step 1: Retrieving relevant guidelines...")
    try:
        guidelines_text, raw_guidelines = retrive.retrieve_and_format(
            query_text=text_content or campaign_objective,
            n_results=5
        )
        guideline_sources = [g["source"] for g in raw_guidelines]
        print(f"   Found {len(raw_guidelines)} relevant guideline chunks")
    except Exception as e:
        print(f"   WARNING: RAG retrieval failed: {e}")
        guidelines_text = "No guidelines retrieved — evaluate based on general brand standards."
        raw_guidelines = []
        guideline_sources = []

    # ── STEP 2: Build Prompt & Message Payload ───────────────────────────────
    print("   Step 2: Building evaluation prompt...")
    prompt = EVALUATION_PROMPT_TEMPLATE.format(
        guidelines=guidelines_text,
        objective=campaign_objective,
        post_text=text_content if text_content else "(No text content provided)"
    )

    has_image = bool(image_path and os.path.exists(image_path))
    models_to_try = _get_available_groq_models(needs_vision=has_image)
    print(f"   Available models to try: {models_to_try}")

    if has_image:
        print(f"   Including image: {image_path}")
        data_url = _encode_image_to_data_url(image_path)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ]
    else:
        messages = [{"role": "user", "content": prompt}]

    # ── STEP 3: GROQ API CALL (with retry & fallback) ────────────────────────
    print("   Step 3: Calling Groq AI for evaluation...")

    raw_response = None
    last_error = None

    for model in models_to_try:
        print(f"   Trying model: {model}...")
        for attempt in range(1, max_retries + 1):
            try:
                chat_completion = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=4096,
                )

                raw_response = chat_completion.choices[0].message.content
                print(f"   Success with {model} ({len(raw_response)} chars)")
                break

            except Exception as e:
                last_error = str(e)
                err_str = str(e)
                if "429" in err_str or "503" in err_str or "rate_limit" in err_str.lower():
                    print(f"   {model} rate-limited/overloaded (attempt {attempt}/{max_retries})")
                    if attempt < max_retries:
                        wait_time = 3 * attempt
                        print(f"   Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                elif "404" in err_str or "model_not_found" in err_str.lower():
                    print(f"   {model} not available — skipping to next model...")
                    break
                else:
                    print(f"   Attempt {attempt}/{max_retries} failed: {e}")
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)

        if raw_response:
            break

    if raw_response is None:
        return {
            "status": "error",
            "message": (
                "⚠️ Groq API call failed across available models. "
                "Check your GROQ_API_KEY or rate limits and try again. "
                f"(Last error: {last_error})"
            ),
        }

    # ── STEP 4: Parse JSON Response ──────────────────────────────────────────
    print("   Step 4: Parsing AI response...")
    ai_result = _parse_json_response(raw_response)

    if ai_result is None:
        print(f"   WARNING: JSON parse failed. Raw: {raw_response[:300]}")
        ai_result = {
            "scores": {
                "factual_accuracy": 50, "regulatory_compliance": 50,
                "brand_identity": 50, "visual_consistency": 50,
                "campaign_effectiveness": 50, "accessibility": 50,
                "overall_design": 50
            },
            "critical_flags": [],
            "category_feedback": {
                "factual_accuracy": "Could not parse AI response properly.",
                "regulatory_compliance": "Could not parse AI response properly.",
                "brand_identity": "Could not parse AI response properly.",
                "visual_consistency": "Could not parse AI response properly.",
                "campaign_effectiveness": "Could not parse AI response properly.",
                "accessibility": "Could not parse AI response properly.",
                "overall_design": "Could not parse AI response properly.",
            },
            "suggestions": [],
            "overall_summary": f"Evaluation parsing failed. Raw response preview: {raw_response[:200]}"
        }

    # ── STEP 5: Calculate Weighted Scores ────────────────────────────────────
    print("   Step 5: Calculating weighted scores...")
    category_scores = ai_result.get("scores", {})
    critical_flags = [
        f for f in ai_result.get("critical_flags", []) if f and str(f).strip()
    ]

    feedback_text = ai_result.get("overall_summary", "")
    for cat, fb in ai_result.get("category_feedback", {}).items():
        feedback_text += " " + str(fb)

    final_result = scoring.generate_final_result(
        category_scores=category_scores,
        feedback_text=feedback_text,
        critical_flags_from_ai=critical_flags,
    )

    final_result["category_feedback"] = ai_result.get("category_feedback", {})
    final_result["suggestions"] = ai_result.get("suggestions", [])
    final_result["overall_summary"] = ai_result.get("overall_summary", "")
    final_result["guideline_sources"] = guideline_sources
    final_result["status"] = "success"

    print(f"   Overall Score: {final_result['overall_score']}/100")
    print(f"   Decision: {final_result['decision']}")

    # ── STEP 6: Save to Database ─────────────────────────────────────────────
    if submission_id:
        print("   Step 6: Saving results to database...")
        try:
            eval_id = db.save_evaluation(
                submission_id=submission_id,
                scores={
                    "overall_score": final_result["overall_score"],
                    **category_scores,
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
            print(f"   Saved as evaluation ID: {eval_id}")
        except Exception as e:
            print(f"   WARNING: Could not save to DB: {e}")

    return final_result


def quick_evaluate(text, objective="brand_awareness"):
    """Quick evaluation without saving to DB."""
    return evaluate_post(
        text_content=text,
        campaign_objective=objective,
        submission_id=None,
    )