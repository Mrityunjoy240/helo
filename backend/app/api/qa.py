from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Request
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import asyncio
import json
import logging
import os
from pathlib import Path
import time
import re

from app.services.tools.bcrec_tool import BCRECTool
from app.services.tools.registry import ToolRegistry
from app.services.router.intent_router import IntentRouter, get_intent_router
from app.services.llm import OllamaLLM
from app.services.hybrid_service import get_hybrid_service, HybridQueryService
from app.config import settings
from app.services.tts import TTSService

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize unified BCREC tool with combined knowledge base
bcrec_tool = BCRECTool()
tool_registry = ToolRegistry()
tool_registry.register(bcrec_tool)

# Initialize intent router with Ollama
llm = OllamaLLM(model="qwen3.5:latest")
intent_router = IntentRouter(llm=llm)

# Initialize TTS service
tts_service = TTSService()


def format_currency(amount: float) -> str:
    """Format amount as Indian currency: 598300 -> 5,98,300"""
    if amount >= 100000:
        lakhs = amount / 100000
        return f"Rs. {lakhs:.2f} Lakhs"
    elif amount >= 1000:
        return f"Rs. {amount:,.0f}"
    else:
        return f"Rs. {amount}"


def _is_follow_up(query: str) -> bool:
    """Check if query is a follow-up question"""
    follow_up_indicators = [
        "it", "that", "this", "what about", "and", "also", 
        "tell me more", "what if", "but", "however", 
        "same", "as well", "too", "else", "another"
    ]
    query_lower = query.lower()
    return any(indicator in query_lower for indicator in follow_up_indicators)


def _is_garbage_input(query: str) -> bool:
    """Detect if query is gibberish/random text"""
    if not query or len(query.strip()) < 3:
        return True
    
    query_clean = query.lower().strip()
    
    # Check for only symbols/numbers (no letters at all)
    if not any(c.isalpha() for c in query_clean):
        return True
    
    # Check for repeated characters (asdfghjkl, asdasd, etc.)
    if len(set(query_clean)) <= 3 and len(query_clean) > 5:
        return True
    
    # Check for keyboard patterns
    keyboard_patterns = ['asdf', 'dfgh', 'zxcv', 'qwerty', 'hjkl', 'jkl;', 'l;']
    for pattern in keyboard_patterns:
        if pattern in query_clean:
            return True
    
    # Check for very low vowel ratio (English words need vowels)
    vowels = set('aeiouAEIOU')
    vowel_count = sum(1 for c in query_clean if c in vowels)
    consonant_count = sum(1 for c in query_clean if c.isalpha())
    if consonant_count > 0 and vowel_count / consonant_count < 0.1:
        return True
    
    # Check for too many consecutive same characters
    if re.search(r'(.)\1{3,}', query_clean):
        return True
    
    return False


def _generate_title(query: str) -> str:
    """Generate a short title from the first query"""
    stop_words = ["what", "is", "the", "a", "an", "about", "can", "you", "tell", "me", "i", "my", "with", "for", "of", "and", "in", "on", "at", "to", "from"]
    words = query.lower().split()
    title_words = [w for w in words if w not in stop_words][:5]
    title = " ".join(title_words)
    return title.capitalize() if title else "New Chat"


def _handle_salary_query(query_lower: str, placement_result: Dict) -> Dict[str, Any]:
    """Handle salary-related queries"""
    placement_data = {
        "CSE": {"package": 30, "avg": 7.5, "rate": "93%"},
        "IT": {"package": 12, "avg": 5.5, "rate": "85%"},
        "ECE": {"package": 15, "avg": 6.0, "rate": "80%"},
        "EE": {"package": 10, "avg": 5.0, "rate": "78%"},
        "AIML": {"package": 20, "avg": 8.0, "rate": "85%"},
        "DS": {"package": 18, "avg": 7.0, "rate": "82%"},
    }
    
    # Extract specific branch if mentioned
    branch = None
    for b in placement_data:
        if b.lower() in query_lower:
            branch = b
            break
    
    if branch:
        data = placement_data[branch]
        answer = f"{branch} Salary: Highest Rs. {data['package']} LPA, Average Rs. {data['avg']} LPA, Placement: {data['rate']}"
    else:
        # Return all branch comparison
        lines = ["Branch-wise Salary Comparison:"]
        for b, d in sorted(placement_data.items(), key=lambda x: x[1]['package'], reverse=True):
            lines.append(f"- {b}: Highest Rs. {d['package']} LPA, Avg Rs. {d['avg']} LPA")
        answer = ". ".join(lines)
    
    return {
        "answer": answer,
        "source": "rule_based",
        "intent": "salary",
        "confidence": 0.9
    }


def _handle_comparison_query(query: str, placement_result: Dict) -> Dict[str, Any]:
    """Handle comparison queries between branches"""
    placement_data = {
        "CSE": {"package": 30, "avg": 7.5, "rate": "93%", "cutoff": 67761},
        "IT": {"package": 12, "avg": 5.5, "rate": "85%", "cutoff": 93450},
        "ECE": {"package": 15, "avg": 6.0, "rate": "80%", "cutoff": 93045},
        "EE": {"package": 10, "avg": 5.0, "rate": "78%", "cutoff": 93045},
        "AIML": {"package": 20, "avg": 8.0, "rate": "85%", "cutoff": 85000},
        "DS": {"package": 18, "avg": 7.0, "rate": "82%", "cutoff": 80000},
    }
    
    # Extract branches to compare
    import re
    query_lower = query.lower()
    branches_found = []
    for b in placement_data:
        if b.lower() in query_lower:
            branches_found.append(b)
    
    if len(branches_found) >= 2:
        b1, b2 = branches_found[0], branches_found[1]
        d1, d2 = placement_data[b1], placement_data[b2]
        comparison = f"{b1} vs {b2}: "
        comparison += f"{b1} offers Rs. {d1['package']} LPA max vs {b2} Rs. {d2['package']} LPA. "
        comparison += f"Avg: {b1} Rs. {d1['avg']} LPA vs {b2} Rs. {d2['avg']} LPA. "
        comparison += f"Placement: {b1} {d1['rate']} vs {b2} {d2['rate']}."
        
        if d1['package'] > d2['package']:
            comparison += f" Winner: {b1} for salary."
        else:
            comparison += f" Winner: {b2} for salary."
    else:
        comparison = "Please specify two branches to compare (e.g., 'Compare CSE vs ECE')."
    
    return {
        "answer": comparison,
        "source": "rule_based",
        "intent": "comparison",
        "confidence": 0.85
    }


def _handle_easiest_query() -> Dict[str, Any]:
    """Handle 'easiest branch' queries"""
    return {
        "answer": "Easiest branches (based on difficulty and workload): ME (Mechanical), CE (Civil) are generally considered easier with good placement. ECE and EE have more circuit/maths. CSE/IT have programming but good job prospects.",
        "source": "rule_based",
        "intent": "easiest",
        "confidence": 0.8
    }


def _handle_general_info_query() -> Dict[str, Any]:
    """Handle 'everything about college' queries"""
    try:
        college_result = tool_registry.execute("get_bcrec_info", query_type="college")
        if college_result and college_result.get("success"):
            name = college_result.get("name", "B.C. Roy Engineering College")
            location = college_result.get("location", "Durgapur, West Bengal")
            
            parts = [
                f"{name} is located in {location}.",
                "It offers B.Tech, M.Tech, MBA, and MCA programs.",
                "Fees: B.Tech Rs. 5.98 Lakhs total.",
                "Highest placement: Rs. 30 LPA (CSE).",
                "Overall placement: 80%+.",
                "Contact: 0343-2501353, www.bcrec.ac.in"
            ]
            return {
                "answer": " ".join(parts),
                "source": "bcrec_tool",
                "intent": "general",
                "confidence": 0.9
            }
    except Exception:
        pass
    
    return {
        "answer": "B.C. Roy Engineering College (BCREC), Durgapur offers B.Tech, M.Tech, MBA, MCA programs. B.Tech fees: Rs. 5.98 Lakhs. Highest placement: Rs. 30 LPA. For more details, contact 0343-2501353 or visit www.bcrec.ac.in.",
        "source": "rule_based",
        "intent": "general",
        "confidence": 0.8
    }


def _handle_document_query() -> Dict[str, Any]:
    """Handle admission documents queries"""
    try:
        docs_result = tool_registry.execute("get_bcrec_info", query_type="documents")
        if docs_result and docs_result.get("success"):
            docs = docs_result.get("admission_documents", {})
            parts = ["Required documents for admission:"]
            
            if docs.get("entrance"):
                parts.append(f"Entrance: {', '.join(docs['entrance'])}")
            if docs.get("academic"):
                parts.append(f"Academic: {', '.join(docs['academic'])}")
            if docs.get("counseling"):
                parts.append(f"Counseling: {', '.join(docs['counseling'])}")
            if docs.get("other"):
                parts.append(f"Others: {', '.join(docs['other'])}")
            
            parts.append("Contact BCREC: 0343-2501353 for complete list.")
            return {
                "answer": " ".join(parts),
                "source": "bcrec_tool",
                "intent": "admission",
                "confidence": 0.9
            }
    except Exception:
        pass
    
    return {
        "answer": "Required documents: WBJEE/JEE-Main Rank Card, Class 10 & 12 marksheets, Allotment Letter from WBJEEB, Character Certificate, Migration Certificate (if applicable), Aadhar Card, 6-8 passport photos. For scholarship (TFW): Income Certificate. Contact BCREC: 0343-2501353.",
        "source": "rule_based",
        "intent": "admission",
        "confidence": 0.85
    }


def _handle_semester_fee_query() -> Dict[str, Any]:
    """Handle semester-wise fee queries"""
    try:
        fees_result = tool_registry.execute("get_bcrec_info", query_type="fees")
        if fees_result and fees_result.get("success"):
            sem_fees = fees_result.get("fees_summary", {}).get("semester_wise", {})
            if sem_fees:
                parts = [
                    f"1st Semester: Rs. {sem_fees.get('first', 97525):,} (includes admission, caution money, library fees)",
                    f"Semesters 2-7: Rs. {sem_fees.get('semesters_2_to_7', '72,425-74,425')} per semester",
                    f"8th Semester: Rs. {sem_fees.get('eighth', 73425):,}",
                    f"Total B.Tech: {sem_fees.get('total_description', 'Approx. Rs. 6.08 Lakhs')}"
                ]
                return {
                    "answer": ". ".join(parts),
                    "source": "bcrec_tool",
                    "intent": "fee",
                    "confidence": 0.9
                }
    except Exception:
        pass
    
    return {
        "answer": "Semester fees: 1st semester ~Rs. 97,525 (includes admission fee). Semesters 2-7: ~Rs. 72,000-74,000. Total B.Tech: ~Rs. 6.08 Lakhs. Payment modes: Demand Draft, Debit/Credit Card. Contact: 0343-2501353.",
        "source": "rule_based",
        "intent": "fee",
        "confidence": 0.85
    }


def _handle_refund_query() -> Dict[str, Any]:
    """Handle fee refund queries"""
    try:
        fees_result = tool_registry.execute("get_bcrec_info", query_type="fees")
        if fees_result and fees_result.get("success"):
            refund = fees_result.get("fees_summary", {}).get("refund_policy")
            if refund:
                return {
                    "answer": f"Fee Refund Policy: {refund} Contact BCREC: 0343-2501353 for details.",
                    "source": "bcrec_tool",
                    "intent": "fee",
                    "confidence": 0.9
                }
    except Exception:
        pass
    
    return {
        "answer": "Fee refund: Full refund before session starts (Rs. 1000 processing fee deducted). Post-commencement: significantly reduced as per AICTE/WBJEEB norms. Contact BCREC: 0343-2501353 for details.",
        "source": "rule_based",
        "intent": "fee",
        "confidence": 0.85
    }


def _handle_installment_query() -> Dict[str, Any]:
    """Handle installment payment queries"""
    try:
        fees_result = tool_registry.execute("get_bcrec_info", query_type="fees")
        if fees_result and fees_result.get("success"):
            installment = fees_result.get("fees_summary", {}).get("installments")
            if installment:
                return {
                    "answer": f"Payment Options: {installment} Contact BCREC: 0343-2501353.",
                    "source": "bcrec_tool",
                    "intent": "fee",
                    "confidence": 0.9
                }
    except Exception:
        pass
    
    return {
        "answer": "Fees are collected semester-wise. Custom payment schedule may be available for hardship cases on appeal to management. Contact BCREC admission office: 0343-2501353.",
        "source": "rule_based",
        "intent": "fee",
        "confidence": 0.85
    }


def _handle_scholarship_eligibility_query() -> Dict[str, Any]:
    """Handle scholarship eligibility queries"""
    try:
        scholar_result = tool_registry.execute("get_bcrec_info", query_type="scholarships")
        if scholar_result and scholar_result.get("success"):
            sch = scholar_result.get("scholarships", {})
            elig = sch.get("eligibility", {})
            schemes = sch.get("schemes", {})
            
            parts = ["Scholarship Eligibility:"]
            parts.append(f"Merit-based: {elig.get('merit', 'Based on WBJEE/JEE Main rank')}")
            parts.append(f"Means-based: {elig.get('means', 'Family income below Rs. 2.5-6 Lakhs')}")
            parts.append("Available Scholarships:")
            
            if schemes.get("tfw"):
                t = schemes["tfw"]
                parts.append(f"- TFW (Tuition Fee Waiver): {t.get('seats', '5% seats')} via WBJEE, {t.get('benefit', 'full tuition waiver')}")
            if schemes.get("svmcm"):
                s = schemes["svmcm"]
                parts.append(f"- SVMCM: Rs. {s.get('amount', '60,000')}/year for {s.get('eligible', 'WB residents')}")
            if schemes.get("oasis_aikyashree"):
                parts.append("- OASIS/Aikyashree: For SC/ST/OBC and Minority students")
            
            return {
                "answer": ". ".join(parts),
                "source": "bcrec_tool",
                "intent": "scholarship",
                "confidence": 0.9
            }
    except Exception:
        pass
    
    return {
        "answer": "Scholarship eligibility: Merit-based (WBJEE/JEE rank) or Means-based (family income < Rs. 2.5-6 Lakhs). Available: TFW (5% seats, full waiver), SVMCM (Rs. 60k/year for WB residents), OASIS/Aikyashree (SC/ST/OBC/Minority). Contact BCREC: 0343-2501353.",
        "source": "rule_based",
        "intent": "scholarship",
        "confidence": 0.85
    }


def _handle_food_quality_query() -> Dict[str, Any]:
    """Handle hostel food quality queries"""
    try:
        hostel_result = tool_registry.execute("get_bcrec_info", query_type="hostel")
        if hostel_result and hostel_result.get("success"):
            mess = hostel_result.get("hostel", {}).get("mess", {})
            if mess:
                parts = [
                    f"Food served {mess.get('meals_per_day', 4)} times/day (Breakfast, Lunch, Snacks, Dinner)",
                    f"Quality: {mess.get('quality', 'Average to decent')}",
                    f"Non-veg: {mess.get('non_veg', 'Available 3-4 days/week')}",
                    f"Veg options: {mess.get('veg_options', 'Paneer and Soybean available daily')}",
                    f"Mess charge: Rs. {mess.get('monthly_charge', 5000)}/month"
                ]
                return {
                    "answer": ". ".join(parts),
                    "source": "bcrec_tool",
                    "intent": "hostel",
                    "confidence": 0.9
                }
    except Exception:
        pass
    
    return {
        "answer": "Mess provides 4 meals/day (Breakfast, Lunch, Snacks, Dinner). Quality is average to decent. Non-veg (Chicken/Fish/Egg) served 3-4 days/week. Veg options (Paneer/Soybean) available daily. Mess charge: Rs. 5,000/month.",
        "source": "rule_based",
        "intent": "hostel",
        "confidence": 0.85
    }


def _handle_ragging_query() -> Dict[str, Any]:
    """Handle ragging-related queries"""
    try:
        anti_ragging_result = tool_registry.execute("get_bcrec_info", query_type="anti_ragging")
        if anti_ragging_result and anti_ragging_result.get("success"):
            ar = anti_ragging_result.get("anti_ragging", {})
            policy = ar.get("policy", "Zero Tolerance")
            measures = ar.get("measures", [])
            
            parts = [f"BCREC has a {policy} policy for ragging."]
            if measures:
                parts.append("Measures: " + ", ".join(measures[:3]))
            parts.append("Contact: 0343-2501353 for any concerns.")
            
            return {
                "answer": " ".join(parts),
                "source": "bcrec_tool",
                "intent": "general",
                "confidence": 0.95
            }
    except Exception:
        pass
    
    return {
        "answer": "BCREC has Zero Tolerance for ragging. Anti-Ragging Committee and Squad are active. All students and parents sign legal affidavit at admission. Separate fresher hostels ensure safety. Contact: 0343-2501353.",
        "source": "rule_based",
        "intent": "general",
        "confidence": 0.9
    }


def _handle_placement_training_query() -> Dict[str, Any]:
    """Handle placement training queries"""
    try:
        placement_result = tool_registry.execute("get_bcrec_info", query_type="placement")
        if placement_result and placement_result.get("success"):
            training = placement_result.get("placements", {}).get("training_cell", {})
            if training:
                programs = ", ".join(training.get("programs", ["Aptitude", "Soft Skills", "Mock Interviews"]))
                starts = training.get("starts_from", "3rd year")
                return {
                    "answer": f"T&P Cell provides: {programs}. Training starts from {starts} onwards. Contact T&P Cell: 0343-2501353.",
                    "source": "bcrec_tool",
                    "intent": "placement",
                    "confidence": 0.9
                }
    except Exception:
        pass
    
    return {
        "answer": "Training & Placement (T&P) Cell provides Aptitude training, Soft Skills development, Mock Interviews, and Resume building. Programs start from 3rd year. Contact T&P Cell: 0343-2501353.",
        "source": "rule_based",
        "intent": "placement",
        "confidence": 0.85
    }


def _handle_faculty_query() -> Dict[str, Any]:
    """Handle faculty quality queries"""
    try:
        academics_result = tool_registry.execute("get_bcrec_info", query_type="academics")
        if academics_result and academics_result.get("success"):
            faculty = academics_result.get("academics", {}).get("faculty", {})
            ratio = academics_result.get("academics", {}).get("student_teacher_ratio", "15:1 to 20:1")
            
            parts = [
                f"Total faculty: {faculty.get('total', '150+')}",
                f"Description: {faculty.get('description', 'Experienced professors with PhDs')}",
                f"Student-Teacher ratio: {ratio}"
            ]
            return {
                "answer": ". ".join(parts),
                "source": "bcrec_tool",
                "intent": "general",
                "confidence": 0.9
            }
    except Exception:
        pass
    
    return {
        "answer": "BCREC has 150+ faculty members. Core branches have experienced professors with PhDs. Newer CSE specializations (AI/ML) have mix of experienced and young tech-savvy faculty. Student-Teacher ratio: 15:1 to 20:1.",
        "source": "rule_based",
        "intent": "general",
        "confidence": 0.85
    }


def _handle_exam_pattern_query() -> Dict[str, Any]:
    """Handle exam pattern queries"""
    try:
        academics_result = tool_registry.execute("get_bcrec_info", query_type="academics")
        if academics_result and academics_result.get("success"):
            exam = academics_result.get("academics", {}).get("exam_pattern", {})
            syllabus = academics_result.get("academics", {}).get("syllabus", "")
            
            parts = [
                f"Exam Structure: {exam.get('structure', 'CA + Mid-sem + Semester-end exams')}",
                f"CA Components: {', '.join(exam.get('ca_components', ['Class tests', 'Assignments']))}",
                f"Syllabus: {syllabus}"
            ]
            return {
                "answer": ". ".join(parts),
                "source": "bcrec_tool",
                "intent": "general",
                "confidence": 0.9
            }
    except Exception:
        pass
    
    return {
        "answer": "Exam pattern: Continuous Assessment (CA) + Mid-semesters + Semester-end theory/practical exams. CA includes class tests, assignments, presentations, viva voce. Syllabus updated for Autonomous batch (2024-25 onwards).",
        "source": "rule_based",
        "intent": "general",
        "confidence": 0.85
    }


def _handle_branch_change_query() -> Dict[str, Any]:
    """Handle branch change queries"""
    try:
        branch_result = tool_registry.execute("get_bcrec_info", query_type="branch_change")
        if branch_result and branch_result.get("success"):
            bc = branch_result.get("branch_change", {})
            return {
                "answer": f"Branch change: {bc.get('allowed', 'Allowed')}. Timing: {bc.get('timing', 'After 1st Year')}. Criteria: {bc.get('criteria', 'Merit-based (CGPA) + Seat vacancy')}. Process: {bc.get('process', 'Apply through academic section')}",
                "source": "bcrec_tool",
                "intent": "admission",
                "confidence": 0.9
            }
    except Exception:
        pass
    
    return {
        "answer": "Branch change is possible after 1st Year (2nd Semester). It is merit-based (CGPA) and depends on seat vacancy in target branch. Apply through academic section after declaring 1st year results.",
        "source": "rule_based",
        "intent": "admission",
        "confidence": 0.85
    }


def _handle_infrastructure_query() -> Dict[str, Any]:
    """Handle campus infrastructure queries"""
    try:
        infra_result = tool_registry.execute("get_bcrec_info", query_type="infrastructure")
        if infra_result and infra_result.get("success"):
            infra = infra_result.get("infrastructure", {})
            wifi = infra.get("wifi", {})
            lib = infra.get("library", {})
            labs = infra.get("computer_labs", {})
            
            parts = [
                f"WiFi: {wifi.get('speed', '28 Mbps')} speed, {wifi.get('coverage', 'Full campus including hostels')}",
                f"Library: {lib.get('books', '80,000+')} books, National/International journals, e-resources (IEEE, INDEST)",
                f"Labs: {labs.get('config', 'Intel Core i5/i7, 8-16GB RAM')}. Software: MATLAB, Python, TensorFlow, ANSYS, AutoCAD, etc.",
                f"Sports: Outdoor (Cricket, Football, Basketball) and Indoor (TT, Carrom, Chess, Gym)",
                f"Other facilities: ATM, Medical (Mission Hospital), Cafeteria, 24x7 CCTV Security"
            ]
            return {
                "answer": " ".join(parts),
                "source": "bcrec_tool",
                "intent": "facility",
                "confidence": 0.9
            }
    except Exception:
        pass
    
    return {
        "answer": "BCREC infrastructure: WiFi 28 Mbps (full campus + hostels), Library 80,000+ books with e-resources, well-equipped labs (MATLAB, Python, ANSYS, AutoCAD), sports facilities, ATM, medical support. AICTE IDEA Lab ranked #1 in India.",
        "source": "rule_based",
        "intent": "facility",
        "confidence": 0.85
    }


def _handle_student_life_query() -> Dict[str, Any]:
    """Handle student life queries"""
    try:
        sl_result = tool_registry.execute("get_bcrec_info", query_type="student_life")
        if sl_result and sl_result.get("success"):
            sl = sl_result.get("student_life", {})
            clubs = sl.get("clubs", [])
            fest = sl.get("tech_fest", {})
            cultural = sl.get("cultural_fest", {})
            events = sl.get("events", [])
            
            parts = [
                f"Tech Fest: {fest.get('name', 'HORIZON')} (February)",
                f"Cultural Fest: {cultural.get('name', 'ZEAL')} (January)",
                f"Clubs: {', '.join(clubs[:5])}" if clubs else "Clubs available: NSS, Coding, Photography, Literary, Sports",
                "Events: Moksha (Freshers), Agomoni (Pre-Durga Puja), Sports Meet"
            ]
            return {
                "answer": ". ".join(parts),
                "source": "bcrec_tool",
                "intent": "general",
                "confidence": 0.9
            }
    except Exception:
        pass
    
    return {
        "answer": "Student life at BCREC: Tech Fest HORIZON (Feb), Cultural Fest ZEAL (Jan), Events: Moksha (Freshers Welcome), Agomoni (Pre-Durga Puja), Sports Meet. Clubs: NSS, IIC (Innovation), Coding, Photography, Literary & Debate, Sports.",
        "source": "rule_based",
        "intent": "general",
        "confidence": 0.85
    }


async def _handle_complex_query(query: str, intent: str, conversation_context: Optional[List[Dict]] = None, entities: Dict[str, Any] = None) -> Dict[str, Any]:
    """Handle complex queries requiring reasoning - rule-based approach"""
    
    query_lower = query.lower()
    intent_detail = entities.get("intent_detail", "") if entities else ""
    
    # Get data for analysis
    cutoff_result = tool_registry.execute("get_bcrec_info", query_type="cutoff")
    placement_result = tool_registry.execute("get_bcrec_info", query_type="placement")
    course_result = tool_registry.execute("get_bcrec_info", query_type="course")
    
    # Extract rank from query (handles 27K, 27000, 27,000, 500, 5000 formats)
    rank_patterns = [
        r'(\d{1,2})[kK](?:\s|$|,)',  # 27K, 18k
        r'rank\s*(\d{1,2})[kK](?:\s|$|,)',  # rank 5k
        r'rank\s*(\d+)',  # rank 500 or rank 50000
    ]
    
    user_rank = None
    for pattern in rank_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            matched_text = match.group(0)
            # Check if the matched text has 'k' as part of the NUMBER (not 'rank')
            # Pattern: digit(s) followed by K/k at word boundary or end
            k_match = re.search(r'(\d+)[kK](?:\s|$|,)', matched_text, re.IGNORECASE)
            if k_match:
                user_rank = int(k_match.group(1)) * 1000
            else:
                val = int(match.group(1))
                if val < 1000:  # Likely just a number, not rank
                    if val > 100:  # Probably a rank like 500
                        user_rank = val
                else:
                    user_rank = val
            break
    
    # Fallback simple pattern for 4-5 digit numbers
    if not user_rank:
        rank_match = re.search(r'(\d{4,5})', query)
        if rank_match:
            user_rank = int(rank_match.group(1))
    
    # Extract PCM/marks from query
    pcm_match = re.search(r'(\d+)\s*%?\s*(?:in\s+)?(?:pcm|physics|chemistry|maths|mathematics)', query_lower)
    user_marks = int(pcm_match.group(1)) if pcm_match else None
    
    # Estimate rank from PCM marks (rough heuristic)
    # 90%+ PCM usually means good rank (<10k), 75% might be moderate (15k-30k)
    estimated_rank = None
    if user_marks and not user_rank:
        if user_marks >= 90:
            estimated_rank = 5000
        elif user_marks >= 85:
            estimated_rank = 10000
        elif user_marks >= 80:
            estimated_rank = 15000
        elif user_marks >= 75:
            estimated_rank = 25000
        elif user_marks >= 70:
            estimated_rank = 40000
        else:
            estimated_rank = 60000
    
    # Extract interests - check for negation (hate, don't, not, etc.)
    negative_patterns = ['hate', 'dont', "don't", 'not ', 'no ', 'never', 'dislike', 'avoid']
    is_negative = any(neg in query_lower for neg in negative_patterns)
    
    # Positive interests
    interests_ai = any(w in query_lower for w in ['ai', 'ml', 'machine learning', 'artificial', 'data science', 'programming', 'coding', 'software', 'computer science'])
    interests_electronics = any(w in query_lower for w in ['electronics', 'circuit', 'embedded', 'communication', 'signal', 'vlsi'])
    interests_core = any(w in query_lower for w in ['mechanical', 'mech', 'civil', 'construction', 'structural', 'automobile'])
    interests_management = any(w in query_lower for w in ['business', 'management', 'finance', 'marketing', 'hr'])
    
    # Handle special queries
    if intent_detail == "salary":
        return _handle_salary_query(query_lower, placement_result)
    
    if intent_detail == "comparison":
        return _handle_comparison_query(query, placement_result)
    
    if intent_detail == "easiest":
        return _handle_easiest_query()
    
    if intent_detail == "general_info":
        return _handle_general_info_query()
    
    if intent_detail == "documents":
        return _handle_document_query()
    
    if intent_detail == "refund":
        return _handle_refund_query()
    
    if intent_detail == "installment":
        return _handle_installment_query()
    
    if intent_detail == "scholarship_eligibility":
        return _handle_scholarship_eligibility_query()
    
    if intent_detail == "food":
        return _handle_food_quality_query()
    
    if intent_detail == "ragging":
        return _handle_ragging_query()
    
    if intent_detail == "placement_training":
        return _handle_placement_training_query()
    
    if intent_detail == "faculty":
        return _handle_faculty_query()
    
    if intent_detail == "exam_pattern":
        return _handle_exam_pattern_query()
    
    if intent_detail == "branch_change":
        return _handle_branch_change_query()
    
    if intent_detail == "infrastructure":
        return _handle_infrastructure_query()
    
    if intent_detail == "student_life":
        return _handle_student_life_query()
    
    # Use conversation context if this is a follow-up
    previous_rank = None
    previous_interests = []
    previous_department = None
    if conversation_context:
        for msg in conversation_context[-4:]:
            if msg.get("role") == "user":
                content = msg.get("content", "").lower()
                # Extract rank from context - handle all formats
                ctx_rank_patterns = [
                    r'(\d{1,2})[kK]',  # 27K
                    r'rank\s*(\d+)',  # rank 500 or rank 50000
                ]
                for ctx_pattern in ctx_rank_patterns:
                    ctx_rank_match = re.search(ctx_pattern, content, re.IGNORECASE)
                    if ctx_rank_match:
                        if ctx_rank_match.group(1):
                            matched_text = ctx_rank_match.group(0).lower()
                            if 'k' in matched_text:
                                previous_rank = int(ctx_rank_match.group(1)) * 1000
                            elif int(ctx_rank_match.group(1)) > 100:
                                previous_rank = int(ctx_rank_match.group(1))
                        elif ctx_rank_match.group(2):
                            val = int(ctx_rank_match.group(2))
                            if val > 100:
                                previous_rank = val
                        break
                # Extract department/branch mentioned
                dept_patterns = ["cse", "it", "ece", "ee", "me", "ce", "aiml", "ds", "csd"]
                for dept in dept_patterns:
                    if dept in content:
                        previous_department = dept.upper()
                        break
                # Extract interests
                if any(w in content for w in ['ai', 'coding', 'programming', 'software']):
                    previous_interests.append("ai")
                if any(w in content for w in ['electronics', 'circuit', 'embedded']):
                    previous_interests.append("electronics")
                if any(w in content for w in ['mechanical', 'civil', 'core']):
                    previous_interests.append("core")
                if any(w in content for w in ['management', 'business']):
                    previous_interests.append("management")
    
    # Use previous rank if no new rank provided, then estimated from PCM
    effective_rank = user_rank or previous_rank or estimated_rank
    
    # Build recommendation
    recommendations = []
    highest_package_branch = None
    eligible_branches = []
    borderline_branches = []
    
    if effective_rank:
        # Match rank against actual cutoffs
        
        branch_cutoffs = {
            "CSE": 67761,
            "IT": 93450,
            "ECE": 93045,
            "EE": 93045,
            "AIML": 85000,
            "DS": 80000,
            "ME": 100000,
            "CE": 100000,
        }
        
        for branch, cutoff_rank in branch_cutoffs.items():
            if effective_rank <= cutoff_rank * 0.8:
                eligible_branches.append(branch)
            elif effective_rank <= cutoff_rank * 1.1:
                borderline_branches.append(branch)
        
        # Determine if we're using estimated rank from PCM
        rank_source = ""
        if user_marks and not user_rank and not previous_rank:
            rank_source = f" (estimated from {user_marks}% PCM)"
        
        if eligible_branches:
            if effective_rank <= 20000:
                recommendations.append(f"With {effective_rank} rank{rank_source}, you can get: {', '.join(eligible_branches[:4])}.")
                if 'CSE' in eligible_branches:
                    recommendations.append("CSE is definitely possible with excellent placement (Highest: Rs. 30 LPA).")
            elif effective_rank <= 40000:
                recommendations.append(f"With {effective_rank} rank{rank_source}, eligible: {', '.join(eligible_branches[:4])}.")
            else:
                recommendations.append(f"With {effective_rank} rank{rank_source}, eligible: {', '.join(eligible_branches[:3])}.")
                if borderline_branches:
                    recommendations.append(f"Borderline: {', '.join(borderline_branches[:2])} may be possible.")
        else:
            recommendations.append(f"With {effective_rank} rank{rank_source}, core branches like ME, CE are more realistic.")
        
        # Find best package branch
        placement_data = {
            "CSE": {"package": 30, "rate": "93%"},
            "IT": {"package": 12, "rate": "85%"},
            "ECE": {"package": 15, "rate": "80%"},
            "EE": {"package": 10, "rate": "78%"},
            "AIML": {"package": 20, "rate": "85%"},
            "DS": {"package": 18, "rate": "82%"},
        }
        
        best_package = 0
        best_branch = ""
        for branch in eligible_branches:
            if branch in placement_data and placement_data[branch]["package"] > best_package:
                best_package = placement_data[branch]["package"]
                best_branch = branch
        
        if best_branch:
            highest_package_branch = f"Highest package for eligible: Rs. {best_package} LPA in {best_branch}"
    else:
        if not effective_rank and previous_rank:
            recommendations.append(f"Based on your previous rank ({previous_rank}): core branches like ME, CE are more realistic.")
        else:
            recommendations.append("Please provide your WBJEE rank for specific recommendations.")
    
    # Interest-based suggestions with negation handling
    positive_interests = interests_ai and not is_negative
    negative_interests = is_negative and (interests_ai or interests_core)
    
    # Use effective rank if available (includes context from previous messages)
    rank_for_context = effective_rank or previous_rank
    
    if positive_interests:
        if rank_for_context:
            recommendations.append("For AI/Programming: CSE (Rs. 5.98 Lakhs), AIML, DS, or IT are best choices.")
        else:
            recommendations.append("For AI/Programming: CSE (Rs. 5.98 Lakhs), AIML, DS, or IT are recommended.")
    elif negative_interests and interests_core:
        recommendations.append("For non-coding interest: ME (Mechanical), CE (Civil) or ECE (Electronics) are good choices.")
    elif negative_interests:
        recommendations.append("For non-coding interest: Consider ME (Mechanical), CE (Civil), ECE (Electronics), or EE (Electrical).")
    elif interests_electronics:
        recommendations.append("For Electronics interest: ECE is the best choice.")
    elif interests_core:
        recommendations.append("For Core Engineering: ME or CE are recommended.")
        recommendations.append("For Electronics interest: ECE is the best choice with good placement prospects.")
    elif interests_core:
        recommendations.append("For Core Engineering interest: ME or CE are recommended.")
    elif interests_management:
        recommendations.append("For Management interest: Consider MBA after B.Tech.")
    
    # Handle "what about X?" follow-up questions
    query_lower = query.lower()
    is_followup = any(w in query_lower for w in ["what about", "and", "also", "tell me more", "then", "so", "now what"])
    follow_up_topics = {
        "placement": ["placement", "job", "salary", "package", "company", "recruit"],
        "cutoff": ["cutoff", "closing", "wbjee"],
        "fee": ["fee", "cost", "payment", "money"],
        "hostel": ["hostel", "room", "accommodation", "mess"],
        "admission": ["admission", "eligible", "counseling", "seat"],
    }
    
    for topic, keywords in follow_up_topics.items():
        if any(kw in query_lower for kw in keywords):
            if conversation_context:
                # With conversation context - use previous info
                if topic == "placement" and rank_for_context and eligible_branches:
                    recommendations.insert(0, f"For your rank {rank_for_context}: {', '.join(eligible_branches[:3])} placements are good.")
                elif topic == "placement" and previous_department:
                    rec = f"{previous_department} has good placement: "
                    placement_data_local = {
                        "CSE": "93% placement, Rs. 30 LPA highest",
                        "IT": "85% placement, Rs. 12 LPA highest",
                        "ECE": "80% placement, Rs. 15 LPA highest",
                        "EE": "78% placement, Rs. 10 LPA highest",
                        "AIML": "85% placement, Rs. 20 LPA highest",
                        "DS": "82% placement, Rs. 18 LPA highest",
                    }
                    if previous_department in placement_data_local:
                        recommendations.insert(0, rec + placement_data_local[previous_department])
            elif is_followup:
                # Standalone follow-up without context - give general info
                if topic == "placement":
                    recommendations.insert(0, "BCREC has 80%+ overall placement. CSE highest: Rs. 30 LPA. Top recruiters: TCS, Infosys, Wipro. For details, contact 0343-2501353.")
                elif topic == "fee":
                    recommendations.insert(0, "B.Tech fees: Rs. 5.98 Lakhs total. Payment is semester-wise. Scholarships available for eligible students.")
                elif topic == "cutoff":
                    recommendations.insert(0, "WBJEE cutoffs: CSE ~68K, ECE ~93K, IT ~93K, EE ~93K. These vary each year.")
                elif topic == "hostel":
                    recommendations.insert(0, "Hostel available for 400+ students. Mess: Rs. 2500/month. Room rent: Rs. 3000-5000/semester.")
                elif topic == "admission":
                    recommendations.insert(0, "Admission via WBJEE counseling. Documents needed: Rank card, Marksheet, Aadhaar, Caste certificate if applicable.")
    
    if positive_interests:
        if user_rank:
            recommendations.append("For AI/Programming: CSE (Rs. 5.98 Lakhs), AIML, DS, or IT are best choices.")
        else:
            recommendations.append("For AI/Programming: CSE (Rs. 5.98 Lakhs), AIML, DS, or IT are recommended.")
    elif negative_interests and interests_core:
        recommendations.append("For non-coding interest: ME (Mechanical), CE (Civil) or ECE (Electronics) are good choices.")
    elif negative_interests:
        recommendations.append("For non-coding interest: Consider ME (Mechanical), CE (Civil), ECE (Electronics), or EE (Electrical).")
    elif interests_electronics:
        recommendations.append("For Electronics interest: ECE is the best choice.")
    elif interests_core:
        recommendations.append("For Core Engineering: ME or CE are recommended.")
        recommendations.append("For Electronics interest: ECE is the best choice with good placement prospects.")
    elif interests_core:
        recommendations.append("For Core Engineering interest: ME or CE are recommended.")
    elif interests_management:
        recommendations.append("For Management interest: Consider MBA after B.Tech.")
    
    # General placement info
    placement_info = f"Overall placement rate: {placement_result.get('overall_rate', '80%+')}."
    if placement_result.get("highest_package"):
        hp = placement_result["highest_package"]
        if isinstance(hp, dict):
            placement_info += f" Highest package: Rs. {int(hp.get('amount', 0))} LPA."
    
    answer_parts = []
    
    if recommendations:
        answer_parts.extend(recommendations[:4])
    
    if highest_package_branch:
        answer_parts.append(highest_package_branch)
    
    if not highest_package_branch and recommendations:
        answer_parts.append("")
        answer_parts.append(placement_info)
    
    answer_parts.append("For exact admission possibilities, contact BCREC: 0343-2501353 or visit www.bcrec.ac.in.")
    
    return {
        "answer": " ".join(answer_parts),
        "source": "rule_based",
        "intent": intent,
        "confidence": 0.85
    }


class QueryRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    use_voice: Optional[bool] = False


class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict]
    session_id: str
    conversation_id: Optional[str]
    source: str
    intent: str
    confidence: float


class TTSRequest(BaseModel):
    text: str
    session_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    message: str
    answer: str
    rating: str
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    status: str
    saved: bool


def format_result(result: Dict[str, Any], intent: str, confidence: float = 0.9, entities: Dict[str, Any] = None) -> Dict[str, Any]:
    """Format tool result into response format"""
    if not result:
        return {
            "answer": "Information not available. Please contact the college directly.",
            "source": "bcrec_tool",
            "intent": intent,
            "confidence": 0.0
        }
    
    if not result.get("success", True):
        return {
            "answer": result.get("error", "An error occurred"),
            "source": "bcrec_tool",
            "intent": intent,
            "confidence": 0.5
        }
    
    # Get detail level from entities
    detail_level = None
    if entities:
        detail_level = entities.get("detail_level")
    
    # Format the answer based on query type
    answer = _format_answer(result, intent, detail_level)
    
    return {
        "answer": answer,
        "source": "bcrec_tool",
        "intent": intent,
        "confidence": confidence,
        "metadata": result
    }


def _format_answer(result: Dict[str, Any], intent: str, detail_level: str = None) -> str:
    """Format the tool result into a readable answer"""
    
    # Fee query
    if result.get("total_fees") and result.get("course"):
        parts = []
        if result.get("course_name"):
            parts.append(f"{result['course_name']} ({result['course']})")
        else:
            parts.append(f"Course: {result['course']}")
        
        # Format fees properly
        fee = result.get("total_fees", "")
        if "598,300" in fee or 598300 in str(result.get("fees", {}).get("total", "")):
            parts.append(f"Total Fees: Rs. 5.98 Lakhs")
        else:
            parts.append(f"Total Fees: {fee}")
        
        if result.get("admission_fee"):
            adm_fee = result.get("admission_fee", "")
            if "97,125" in adm_fee:
                parts.append(f"Admission Fee: Rs. 97,125")
            else:
                parts.append(f"Admission Fee: {adm_fee}")
        if result.get("duration"):
            parts.append(f"Duration: {result['duration']}")
        return ". ".join(parts)
    
    # Course info
    if result.get("full_name"):
        course_code = result.get("course", "")
        parts = [f"{result['full_name']}"]
        if course_code:
            parts[0] = f"{result['full_name']} ({course_code})"
        if result.get("intake"):
            parts.append(f"Intake: {result['intake']} students")
        if result.get("nba_accredited"):
            parts.append("NBA Accredited")
        if result.get("fees"):
            if isinstance(result["fees"], dict):
                fee_total = result["fees"].get("total", "N/A")
                fee_str = str(fee_total)
                if "598300" in fee_str or "5,98,300" in fee_str or fee_total == 598300:
                    parts.append("Fees: Rs. 5.98 Lakhs")
                else:
                    parts.append(f"Fees: Rs. {fee_total}")
        if result.get("placement") and isinstance(result["placement"], dict):
            rate = result["placement"].get("2024-25") or result["placement"].get("2025-26")
            if rate:
                parts.append(f"Placement: {rate}")
        return ". ".join(parts)
    
    # Placement
    if result.get("overall_rate"):
        parts = [f"Placement rate: {result['overall_rate']}"]
        if result.get("highest_package"):
            hp = result["highest_package"]
            if isinstance(hp, dict):
                amount = hp.get("amount", 0)
                parts.append(f"Highest package: Rs. {int(amount)} LPA from {hp.get('company')}")
            else:
                parts.append(f"Highest package: {hp}")
        if result.get("top_companies"):
            top = result["top_companies"]
            if isinstance(top, list):
                companies = []
                for c in top[:3]:
                    if isinstance(c, dict):
                        companies.append(str(c.get("company", "")))
                    else:
                        companies.append(str(c))
                parts.append(f"Top recruiters: {', '.join([x for x in companies if x])}")
        return ". ".join(parts)
    
    # Hostel
    if result.get("hostel"):
        h = result["hostel"]
        if isinstance(h, dict):
            compulsory = h.get("compulsory", False)
            parts = [f"Hostel available{f' (Compulsory: No, optional)' if 'compulsory' in h else ''}. Capacity: {h.get('total_capacity', 'N/A')} students"]
            if h.get("mess") and isinstance(h["mess"], dict):
                mess = h["mess"]
                mess_fee = mess.get("monthly_charge", "N/A")
                meals = mess.get("meals_per_day", 4)
                quality = mess.get("quality", "Average to decent")
                parts.append(f"Mess: Rs. {mess_fee}/month, {meals} meals/day, Quality: {quality}")
            if h.get("room_types"):
                room_info = []
                for r in h["room_types"][:2]:
                    if isinstance(r, dict):
                        room_info.append(f"{r.get('type')} (Rs. {r.get('rent_per_sem')}/sem)")
                if room_info:
                    parts.append(f"Room types: {', '.join(room_info)}")
            if h.get("rules"):
                rules = h["rules"]
                if rules.get("boys_curfew"):
                    parts.append(f"Boys curfew: {rules['boys_curfew']}")
                if rules.get("girls_curfew"):
                    parts.append(f"Girls curfew: {rules['girls_curfew']}")
            return ". ".join(parts)
    
    # Contact
    if result.get("contact"):
        c = result["contact"]
        if isinstance(c, dict):
            parts = []
            if c.get("email"):
                parts.append(f"Email: {c['email']}")
            if c.get("phones"):
                phones = c["phones"] if isinstance(c["phones"], list) else [c["phones"]]
                parts.append(f"Phone: {', '.join(phones[:2])}")
            if c.get("website"):
                parts.append(f"Website: {c['website']}")
            if c.get("address"):
                parts.append(f"Address: {c['address']}")
            return ". ".join(parts)
    
    # Admission
    if result.get("admission"):
        a = result.get("admission")
        if isinstance(a, dict):
            parts = []
            elig = a.get("eligibility")
            if elig:
                if isinstance(elig, dict):
                    btech = elig.get("btech") or elig.get("B.Tech")
                    if btech:
                        parts.append(f"B.Tech: {btech}")
                else:
                    parts.append(str(elig))
            if a.get("counseling"):
                parts.append(f"Counseling: {a['counseling']}")
            if a.get("seat_distribution"):
                sd = a["seat_distribution"]
                if isinstance(sd, dict):
                    parts.append(f"Seats: WBJEE {sd.get('wbjee', 'N/A')}, JEE Main {sd.get('jee_main', 'N/A')}, Management {sd.get('management', 'N/A')}")
            if a.get("scholarships"):
                parts.append("Scholarships available")
            return ". ".join(parts)
    
    # Admission documents
    if result.get("admission_documents"):
        docs = result["admission_documents"]
        parts = ["Required Documents:"]
        for cat, items in docs.items():
            if isinstance(items, list) and items:
                parts.append(f"{cat.title()}: {', '.join(items[:4])}")
        return ". ".join(parts)
    
    # Scholarships
    if result.get("scholarships"):
        s = result["scholarships"]
        parts = ["Scholarships:"]
        elig = s.get("eligibility", {})
        if elig:
            parts.append(f"Merit: {elig.get('merit', 'WBJEE/JEE rank')}")
            parts.append(f"Means: {elig.get('means', 'Income < Rs. 2.5-6 Lakhs')}")
        schemes = s.get("schemes", {})
        if schemes:
            if schemes.get("tfw"):
                t = schemes["tfw"]
                parts.append(f"TFW: {t.get('seats', '5%')} seats, {t.get('benefit', 'Full tuition waiver')}")
            if schemes.get("svmcm"):
                sv = schemes["svmcm"]
                parts.append(f"SVMCM: Rs. {sv.get('amount', '60,000')}/year for {sv.get('eligible', 'WB residents')}")
        return ". ".join(parts)
    
    # Fees summary
    if result.get("fees_summary"):
        fs = result["fees_summary"]
        parts = []
        if fs.get("semester_wise"):
            sw = fs["semester_wise"]
            parts.append(f"1st Semester: Rs. {sw.get('first', 97525):,}")
            parts.append(f"Semesters 2-7: Rs. {sw.get('semesters_2_to_7', '72,425-74,425')}/sem")
            parts.append(f"8th Semester: Rs. {sw.get('eighth', 73425):,}")
            parts.append(f"Total: {sw.get('total_description', '~Rs. 6.08 Lakhs')}")
        if fs.get("hidden_charges"):
            parts.append(f"Extra: {', '.join(fs['hidden_charges'][:2])}")
        return ". ".join(parts)
    
    # Anti-ragging
    if result.get("anti_ragging"):
        ar = result["anti_ragging"]
        parts = [f"Ragging Policy: {ar.get('policy', 'Zero Tolerance')}"]
        measures = ar.get("measures", [])
        if measures:
            parts.append(f"Measures: {', '.join(measures[:2])}")
        return ". ".join(parts)
    
    # Academics
    if result.get("academics"):
        ac = result["academics"]
        parts = []
        if ac.get("faculty"):
            f = ac["faculty"]
            parts.append(f"Faculty: {f.get('total', '150+')}")
            parts.append(f"Student-Teacher Ratio: {ac.get('student_teacher_ratio', '15:1 to 20:1')}")
        if ac.get("exam_pattern"):
            ep = ac["exam_pattern"]
            parts.append(f"Exam: {ep.get('structure', 'CA + Mid-sem + Semester-end')}")
        return ". ".join(parts)
    
    # Infrastructure
    if result.get("infrastructure"):
        inf = result["infrastructure"]
        parts = []
        if inf.get("wifi"):
            w = inf["wifi"]
            parts.append(f"WiFi: {w.get('speed', '28 Mbps')}, {w.get('coverage', 'Full campus')}")
        if inf.get("library"):
            lib = inf["library"]
            parts.append(f"Library: {lib.get('books', '80,000+')} books")
        if inf.get("computer_labs"):
            labs = inf["computer_labs"]
            parts.append(f"Labs: {labs.get('config', 'Well-equipped')}")
        if inf.get("sports"):
            sp = inf["sports"]
            if sp.get("outdoor"):
                parts.append(f"Sports: {', '.join(sp['outdoor'][:3])}")
        return ". ".join(parts)
    
    # Student life
    if result.get("student_life"):
        sl = result["student_life"]
        parts = []
        if sl.get("tech_fest"):
            tf = sl["tech_fest"]
            parts.append(f"Tech Fest: {tf.get('name', 'HORIZON')} ({tf.get('month', 'February')})")
        if sl.get("cultural_fest"):
            cf = sl["cultural_fest"]
            parts.append(f"Cultural Fest: {cf.get('name', 'ZEAL')} ({cf.get('month', 'January')})")
        if sl.get("clubs"):
            parts.append(f"Clubs: {', '.join(sl['clubs'][:4])}")
        return ". ".join(parts)
    
    # Branch change
    if result.get("branch_change"):
        bc = result["branch_change"]
        parts = [f"Branch Change: {bc.get('allowed', 'Allowed') if bc.get('allowed') else 'Possible'}"]
        parts.append(f"Timing: {bc.get('timing', 'After 1st Year')}")
        parts.append(f"Criteria: {bc.get('criteria', 'Merit-based (CGPA) + vacancy')}")
        return ". ".join(parts)
    
    # Cutoff
    if result.get("cutoff"):
        c = result.get("cutoff")
        if isinstance(c, dict):
            course = result.get("course", "")
            parts = [f"{course} WBJEE Cutoff:"]
            for year, rank in c.items():
                parts.append(f"{year}: {rank}")
            return ", ".join(parts)
    
    # HOD info
    if result.get("info") and isinstance(result["info"], dict):
        info = result["info"]
        if info.get("hod") and isinstance(info["hod"], dict):
            hod = info["hod"]
            hod_name = hod.get("name", "N/A")
            
            # Format based on detail level
            if detail_level == "contact":
                parts = []
                if hod.get("email"):
                    parts.append(f"Email: {hod['email']}")
                if hod.get("mobile"):
                    parts.append(f"Phone: {hod['mobile']}")
                return ". ".join(parts) if parts else hod_name
            elif detail_level == "full":
                parts = [f"HOD: {hod_name}"]
                if hod.get("email"):
                    parts.append(f"Email: {hod['email']}")
                if hod.get("mobile"):
                    parts.append(f"Phone: {hod['mobile']}")
                return ". ".join(parts)
            else:
                # Default: just name
                return hod_name
    
    # Courses list
    if result.get("courses"):
        courses = result.get("courses", [])
        if courses and isinstance(courses[0], dict):
            parts = ["Available courses:"]
            for c in courses[:7]:
                parts.append(f"{c.get('code')}: {c.get('name')} (Intake: {c.get('intake')})")
            return ". ".join(parts)
        elif courses:
            return f"Available courses: {', '.join([str(c).upper() for c in courses])}"
    
    # All info
    if result.get("message"):
        return result["message"]
    
    return json.dumps(result, indent=2)


def _get_principal_info() -> Dict[str, Any]:
    """Get principal information from knowledge base"""
    try:
        result = tool_registry.execute("get_bcrec_info", query_type="college")
        return result
    except Exception as e:
        logger.error(f"Error getting principal info: {e}")
        return {"success": False, "error": str(e)}


def _format_principal_response(result: Dict[str, Any], detail_level: str = "name") -> Dict[str, Any]:
    """Format principal response based on detail level"""
    if not result or not result.get("success"):
        return {
            "answer": "Principal information not available. Please contact the college.",
            "source": "bcrec_tool",
            "intent": "principal",
            "confidence": 0.5
        }
    
    principal = result.get("principal", {})
    if not principal:
        return {
            "answer": "Principal information not available.",
            "source": "bcrec_tool",
            "intent": "principal",
            "confidence": 0.5
        }
    
    name = principal.get("name", "Dr. Dilip Kumar Chowdhury")
    answer = name
    
    if detail_level == "full":
        parts = [name]
        if principal.get("qualification"):
            parts.append(f"Qualification: {principal['qualification']}")
        if principal.get("email"):
            parts.append(f"Email: {principal['email']}")
        if principal.get("mobile"):
            parts.append(f"Phone: {principal['mobile']}")
        answer = ". ".join(parts)
    elif detail_level == "contact":
        parts = []
        if principal.get("email"):
            parts.append(f"Email: {principal['email']}")
        if principal.get("mobile"):
            parts.append(f"Phone: {principal['mobile']}")
        if not parts:
            parts.append(f"Phone: 0343-2501353")
        answer = ". ".join(parts)
    
    return {
        "answer": answer,
        "source": "bcrec_tool",
        "intent": "principal",
        "confidence": 0.9
    }


async def _get_conversation_messages(conversation_id: str, limit: int = 6) -> List[Dict]:
    """Get recent messages from a conversation"""
    try:
        import sqlite3
        DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "conversations.db")
        DB_PATH = os.path.normpath(DB_PATH)
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            """SELECT role, content FROM messages 
               WHERE conversation_id = ? 
               ORDER BY created_at DESC 
               LIMIT ?""",
            (conversation_id, limit)
        )
        messages = cursor.fetchall()
        conn.close()
        
        return [{"role": m["role"], "content": m["content"]} for m in reversed(messages)]
    except Exception as e:
        logger.error(f"Error fetching conversation messages: {e}")
        return []


async def _save_message(conversation_id: str, role: str, content: str) -> bool:
    """Save a message to conversation"""
    try:
        import sqlite3
        from datetime import datetime
        import uuid
        
        DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "conversations.db")
        DB_PATH = os.path.normpath(DB_PATH)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        msg_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        cursor.execute(
            "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (msg_id, conversation_id, role, content, now)
        )
        
        # Update conversation timestamp
        cursor.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id)
        )
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving message: {e}")
        return False


async def _update_conversation_title(conversation_id: str, title: str) -> bool:
    """Update conversation title"""
    try:
        import sqlite3
        from datetime import datetime
        
        DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "conversations.db")
        DB_PATH = os.path.normpath(DB_PATH)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE conversations SET title = ? WHERE id = ?",
            (title, conversation_id)
        )
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error updating title: {e}")
        return False


async def process_with_unified_tool(query: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Process query using the unified BCREC tool with intent routing.
    Memory is ONLY used if:
    1. conversation_id is provided
    2. Query is a follow-up question
    """
    try:
        # Classify intent
        intent_result = await intent_router.classify(query)
        intent = intent_result.intent
        confidence = intent_result.confidence
        entities = intent_result.entities
        
        logger.info(f"Intent: {intent}, confidence: {confidence}, entities: {entities}")
        
        # Handle greeting
        if intent == "greeting":
            return {
                "answer": "Hello! How can I help you today? I can provide information about admissions, fees, courses, placements, hostel, cutoff, and more.",
                "source": "unified_tool",
                "intent": "greeting",
                "confidence": 1.0
            }
        
        # Handle garbage input
        if _is_garbage_input(query):
            return {
                "answer": "I didn't understand that. Could you please rephrase your question about BCREC? I can help with admissions, fees, courses, placements, hostel, cutoff, and more.",
                "source": "unified_tool",
                "intent": "invalid",
                "confidence": 0.0
            }
        
        # Check if this is a follow-up in an existing conversation
        conversation_context = None
        if conversation_id and _is_follow_up(query):
            conversation_context = await _get_conversation_messages(conversation_id, limit=4)
            logger.info(f"Using conversation context: {len(conversation_context)} messages")
        
        # Map intent to query type
        query_type = None
        course_param = None
        dept_param = None
        
        query_lower = query.lower()
        intent_detail = entities.get("intent_detail", "")
        
        # Determine query type
        if intent == "fee" or "hostel" in intent_detail:
            if "hostel" in query_lower or "room" in query_lower or "accommodation" in query_lower:
                query_type = "hostel"
            else:
                query_type = "fee"
                course_param = entities.get("course") or entities.get("department") or "CSE"
        
        elif intent == "admission":
            query_type = "admission"
        
        elif intent == "contact":
            query_type = "contact"
        
        elif intent == "course":
            query_type = "course"
            course_param = entities.get("department") or entities.get("course")
        
        elif intent == "placement" or intent_detail in ["salary", "comparison", "easiest"]:
            # Handle special placement queries
            if intent_detail == "salary":
                return _handle_salary_query(query_lower, {})
            elif intent_detail == "comparison":
                return _handle_comparison_query(query, {})
            elif intent_detail == "easiest":
                return _handle_easiest_query()
            query_type = "placement"
            course_param = entities.get("course")
        
        elif intent == "cutoff" or "cutoff" in intent_detail:
            query_type = "cutoff"
            course_param = entities.get("course") or entities.get("department") or "CSE"
        
        elif intent == "hod" or "hod" in intent_detail or "faculty" in query_lower or "professor" in query_lower:
            query_type = "department"
            dept_param = entities.get("department") or entities.get("course") or "CSE"
            # Store detail level for formatting
            entities["detail_level"] = entities.get("detail_level", "name")
        
        elif intent == "principal":
            result = _get_principal_info()
            return _format_principal_response(result, entities.get("detail_level", "name"))
        
        elif intent == "facility":
            if "hostel" in query_lower or "room" in query_lower:
                query_type = "hostel"
            else:
                query_type = "infrastructure"
        
        elif intent == "scholarship":
            query_type = "scholarship"
        
        elif intent == "recommendation" or intent == "eligibility" or intent_detail == "eligibility":
            # Check for special query types first
            if intent_detail == "salary":
                return _handle_salary_query(query_lower, {})
            elif intent_detail == "comparison":
                return _handle_comparison_query(query, {})
            elif intent_detail == "easiest":
                return _handle_easiest_query()
            # Complex queries needing reasoning - pass context if available
            return await _handle_complex_query(query, intent, conversation_context, entities)
        
        else:
            # Complex query - use reasoning
            return await _handle_complex_query(query, intent, conversation_context, entities)
        
        # Execute tool
        result = tool_registry.execute(
            "get_bcrec_info",
            query_type=query_type,
            course=course_param,
            department=dept_param
        )
        
        return format_result(result, intent, confidence, entities)
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return {
            "answer": f"I encountered an error processing your query. Please contact BCREC directly at 0343-2501353.",
            "source": "error",
            "intent": "error",
            "confidence": 0.0
        }


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(request: Request, query_data: QueryRequest):
    """Handle text-based queries with unified tool"""
    start_time = time.time()
    session_id = query_data.session_id or getattr(request.state, 'session_id', 'default')
    logger.info(f"[{session_id}] Query: '{query_data.message[:60]}...'")
    
    try:
        # Process using unified tool
        result = await process_with_unified_tool(
            query_data.message, 
            conversation_id=query_data.conversation_id
        )
        
        # Save user message to conversation if conversation_id provided
        if query_data.conversation_id:
            await _save_message(query_data.conversation_id, "user", query_data.message)
            
            # Update title if this is the first message
            messages = await _get_conversation_messages(query_data.conversation_id, limit=10)
            if len(messages) == 1:  # First message
                title = _generate_title(query_data.message)
                await _update_conversation_title(query_data.conversation_id, title)
        
        elapsed = time.time() - start_time
        logger.info(f"[{session_id}] Processed in {elapsed:.2f}s (source: {result.get('source')})")
        
        return QueryResponse(
            answer=result["answer"],
            sources=[],
            session_id=session_id,
            conversation_id=query_data.conversation_id,
            source=result.get("source", "unified_tool"),
            intent=result.get("intent", "unknown"),
            confidence=result.get("confidence", 0.5)
        )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class HybridQueryRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None


@router.post("/hybrid-query")
async def hybrid_query_endpoint(request: Request, query_data: HybridQueryRequest):
    """
    NEW Hybrid Query Endpoint using LLM-based intent classification.
    This replaces the keyword-based routing for better query understanding.
    """
    start_time = time.time()
    session_id = query_data.session_id or getattr(request.state, 'session_id', 'default')
    logger.info(f"[{session_id}] Hybrid Query: '{query_data.message[:60]}...'")
    
    try:
        # Get conversation history if available
        conversation_history = None
        if query_data.conversation_id:
            conversation_history = await _get_conversation_messages(query_data.conversation_id, limit=6)
        
        # Process using hybrid service
        hybrid_service = get_hybrid_service()
        result = await hybrid_service.process_query(
            query_data.message,
            conversation_id=query_data.conversation_id,
            conversation_history=conversation_history
        )
        
        # Save user message to conversation if conversation_id provided
        if query_data.conversation_id:
            await _save_message(query_data.conversation_id, "user", query_data.message)
        
        elapsed = time.time() - start_time
        logger.info(f"[{session_id}] Hybrid processed in {elapsed:.2f}s (source: {result.get('source')}, intent: {result.get('intent')})")
        
        return QueryResponse(
            answer=result["answer"],
            sources=[],
            session_id=session_id,
            conversation_id=query_data.conversation_id,
            source=result.get("source", "hybrid"),
            intent=result.get("intent", "unknown"),
            confidence=result.get("confidence", 0.5)
        )
        
    except Exception as e:
        logger.error(f"Hybrid query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query-response")
async def save_response_endpoint(conversation_id: str, answer: str):
    """Save the assistant's response to conversation (called after query returns)"""
    if conversation_id:
        await _save_message(conversation_id, "assistant", answer)
    return {"status": "ok"}


@router.post("/tts")
async def tts_endpoint(tts_data: TTSRequest, request: Request):
    """Convert text to speech"""
    try:
        audio_content = await tts_service.text_to_speech(tts_data.text)
        
        session_id = tts_data.session_id or "default"
        filename = f"tts_{session_id}_{hash(tts_data.text)}.wav"
        filepath = os.path.join(settings.temp_audio_dir, filename)
        
        os.makedirs(settings.temp_audio_dir, exist_ok=True)
        
        with open(filepath, "wb") as f:
            f.write(audio_content)
        
        return {"audio_url": f"/audio/{filename}", "session_id": session_id}
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    ollama_ok = llm.is_available()
    
    return {
        'status': 'healthy' if ollama_ok else 'degraded',
        'ollama_connected': ollama_ok,
        'unified_tool': True,
        'knowledge_base': 'combined_kb.json',
        'conversations_enabled': True
    }


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(feedback: FeedbackRequest):
    """Collect user feedback"""
    storage_file = os.path.join(settings.chroma_persist_dir, 'feedback.json')
    os.makedirs(os.path.dirname(storage_file), exist_ok=True)
    data = []
    try:
        if os.path.exists(storage_file):
            with open(storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f) or []
    except Exception:
        data = []

    entry = {
        'message': feedback.message,
        'answer': feedback.answer,
        'rating': feedback.rating,
        'comment': feedback.comment or "",
    }
    try:
        data.append(entry)
        with open(storage_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return FeedbackResponse(status='ok', saved=True)
    except Exception:
        return FeedbackResponse(status='error', saved=False)


# WebSocket for voice interactions
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    session_id = f"session_{hash(websocket) % 10000}"
    conversation_id = None
    
    await websocket.send_text(json.dumps({
        "type": "ready",
        "session_id": session_id
    }))
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "transcribe":
                transcript = message_data.get("text", "")
                conversation_id = message_data.get("conversation_id")
                
                if transcript:
                    await websocket.send_text(json.dumps({
                        "type": "transcript",
                        "text": transcript
                    }))
                    
                    # Process query using unified tool
                    result = await process_with_unified_tool(transcript, conversation_id)
                    answer = result.get("answer", "")
                    
                    # Save messages if conversation_id provided
                    if conversation_id:
                        await _save_message(conversation_id, "user", transcript)
                        await _save_message(conversation_id, "assistant", answer)
                    
                    await websocket.send_text(json.dumps({
                        "type": "answer",
                        "text": answer,
                        "session_id": session_id,
                        "conversation_id": conversation_id
                    }))
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()
