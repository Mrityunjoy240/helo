from typing import Dict, List, Optional, Any
import json
import os
import re
import logging

logger = logging.getLogger(__name__)


class StructuredLookup:
    """
    Fast structured data lookup service for BCREC chatbot.
    Handles simple factual queries with instant responses.
    """
    
    def __init__(self, data_path: str = None):
        if data_path is None:
            data_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "structured_data.json")
        self.data = self._load_data(data_path)
        self._build_index()
    
    def _load_data(self, path: str) -> Dict:
        """Load structured data from JSON file"""
        try:
            if not os.path.exists(path):
                path = os.path.join(os.getcwd(), path)
            
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            logger.warning(f"Structured data file not found: {path}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load structured data: {e}")
            return {}
    
    def _build_index(self) -> None:
        """Build search index for fast lookups"""
        self.intent_handlers = {
            "fee": self._handle_fee,
            "contact": self._handle_contact,
            "admission": self._handle_admission,
            "course": self._handle_course,
            "placement": self._handle_placement,
            "facility": self._handle_facility,
            "scholarship": self._handle_scholarship,
            "general": self._handle_general,
        }
    
    def lookup(self, query: str, intent: str) -> Optional[Dict[str, Any]]:
        """
        Main lookup function.
        
        Args:
            query: User's question
            intent: Classified intent from QueryRouter
            
        Returns:
            Dictionary with answer, confidence, and metadata
        """
        # Get handler for intent
        handler = self.intent_handlers.get(intent, self._handle_general)
        
        try:
            result = handler(query)
            if result:
                result["intent"] = intent
                result["source"] = "structured"
                return result
        except Exception as e:
            logger.error(f"Error in structured lookup: {e}")
        
        return None
    
    def _handle_fee(self, query: str) -> Optional[Dict[str, Any]]:
        """Handle fee-related queries"""
        q = query.lower()
        
        # MBA fee
        if "mba" in q:
            mba = self.data.get("fees", {}).get("mba", {})
            return {
                "answer": f" MBA total fees are {mba.get('total', 'Contact college for details')} for the entire 2-year program. "
                          f"Per semester fees are approximately {mba.get('per_semester', 'Contact college')}.",
                "confidence": 0.95,
                "topics": ["mba_fees"]
            }
        
        # MCA fee
        if "mca" in q:
            mca_fees = self.data.get("courses", {}).get("mca", {}).get("total_fees", "Contact college for details")
            return {
                "answer": f"MCA total fees are approximately {mca_fees} for the 3-year program.",
                "confidence": 0.95,
                "topics": ["mca_fees"]
            }
        
        # B.Tech fee (default)
        btech = self.data.get("fees", {}).get("btech", {})
        courses = self.data.get("courses", {}).get("btech", {})
        
        # Check for hostel fee
        if "hostel" in q or "hostel" in q:
            hostel = self.data.get("fees", {}).get("hostel", {})
            return {
                "answer": f"Hostel fees at BCREC: Boarding approximately {hostel.get('boarding_per_sem', 'Contact college')} per semester, "
                          f"Mess charges about {hostel.get('mess_per_month', 'Contact college')} per month, "
                          f"and security deposit of {hostel.get('security_deposit', 'Contact college')}.",
                "confidence": 0.95,
                "topics": ["hostel_fees"]
            }
        
        # General B.Tech fee
        return {
            "answer": f"B.Tech total fees at BCREC range from {btech.get('total', '₹4.49 Lakhs - ₹6.1 Lakhs')} depending on the branch. "
                      f"First year fees are between {btech.get('per_year', '₹1.09 Lakhs - ₹1.69 Lakhs')}. "
                      f"Per semester fees are approximately {btech.get('per_semester', '₹63,250')}.",
            "confidence": 0.95,
            "topics": ["btech_fees"]
        }
    
    def _handle_contact(self, query: str) -> Optional[Dict[str, Any]]:
        """Handle contact-related queries"""
        q = query.lower()
        contacts = self.data.get("contacts", {})
        
        # Admission contact
        if "admission" in q or "apply" in q:
            admission = contacts.get("admissions", {})
            return {
                "answer": f"For admission queries, call: {', '.join(admission.get('phone', ['Contact main office']))}. "
                          f"Email: {admission.get('email', 'admissions@bcrec.ac.in')}",
                "confidence": 0.95,
                "topics": ["admission_contact"]
            }
        
        # Placement contact
        if "placement" in q or "tpo" in q or "recruit" in q:
            placement = contacts.get("placement", {})
            return {
                "answer": f"For placement queries, email: {placement.get('email', 'tpo.kol@bcrec.ac.in')} "
                          f"or call: {', '.join(placement.get('phone', ['033-2355 4412']))}.",
                "confidence": 0.95,
                "topics": ["placement_contact"]
            }
        
        # CSE HOD
        if "cse" in q or ("hod" in q and "head" in q):
            cse = contacts.get("departments", {}).get("cse", {})
            return {
                "answer": f"CSE Department Head: {cse.get('name', 'Dr. Bappaditya Das')}. "
                          f"Email: {cse.get('email', 'bappaditya.das@bcrec.ac.in')}. "
                          f"Phone: {cse.get('phone', '+91-9051218105')}",
                "confidence": 0.9,
                "topics": ["department_contact"]
            }
        
        # Principal
        if "principal" in q:
            principal = contacts.get("principal", {})
            return {
                "answer": f"Principal: Email {principal.get('email', 'principal@bcrec.ac.in')}, "
                          f"Phone: {principal.get('phone', '0343-2501353')}",
                "confidence": 0.9,
                "topics": ["principal"]
            }
        
        # Default - main office
        main = contacts.get("main_office", {})
        return {
            "answer": f"BCREC Main Office: Phone: {', '.join(main.get('phone', ['0343-2501353']))}. "
                      f"Email: {main.get('email', 'info@bcrec.ac.in')}. "
                      f"Website: {main.get('website', 'www.bcrec.ac.in')}. "
                      f"Office hours: {main.get('hours', 'Mon-Fri: 10:00 AM - 5:30 PM')}",
            "confidence": 0.9,
            "topics": ["main_contact"]
        }
    
    def _handle_admission(self, query: str) -> Optional[Dict[str, Any]]:
        """Handle admission-related queries"""
        q = query.lower()
        admission = self.data.get("admission", {})
        
        # Eligibility
        if "eligibility" in q or "eligible" in q or "criteria" in q:
            elig = admission.get("eligibility", {})
            return {
                "answer": f"B.Tech Eligibility: {elig.get('btech', '10+2 with Physics, Chemistry, Mathematics (minimum 50% marks)')}. "
                          f"Required entrance exams: WBJEE or JEE Main. "
                          f"MBA Eligibility: {elig.get('mba', 'Bachelor degree with 50% marks')}. "
                          f"MCA Eligibility: {elig.get('mca', 'Bachelor degree with Mathematics at 10+2')}",
                "confidence": 0.9,
                "topics": ["eligibility"]
            }
        
        # Documents
        if "document" in q or "required" in q:
            docs = admission.get("documents_required", [])
            if docs:
                docs_text = ", ".join(docs[:5]) + "..."
                return {
                    "answer": f"Required documents for admission: {docs_text}. Plus more as applicable.",
                    "confidence": 0.9,
                    "topics": ["documents"]
                }
        
        # Process
        if "process" in q or "how to apply" in q:
            steps = admission.get("process", [])
            if steps:
                process_text = ". ".join([f"Step {i+1}: {s}" for i, s in enumerate(steps[:4])])
                return {
                    "answer": f"Admission process: {process_text}. For detailed guidance, contact admissions.",
                    "confidence": 0.9,
                    "topics": ["process"]
                }
        
        # Entrance exams
        if "entrance" in q or "exam" in q or "wbjee" in q or "jee" in q:
            exams = admission.get("entrance_exams", {})
            exams_text = ", ".join([f"{k}: {', '.join(v)}" for k, v in exams.items()])
            return {
                "answer": f"Entrance exams accepted: {exams_text}. "
                          f"WBJEE registration: {admission.get('important_dates', {}).get('wbjee_2026_registration', 'Mar-Apr 2026')}.",
                "confidence": 0.9,
                "topics": ["entrance_exams"]
            }
        
        # Cutoff
        if "cutoff" in q or "rank" in q:
            courses = self.data.get("courses", {}).get("btech", {}).get("branches", {})
            cutoff_text = ". ".join([f"{k.upper()}: {v.get('cutoff_general', 'Contact college')}" for k, v in courses.items()][:5])
            return {
                "answer": f"WBJEE 2025 Cutoff (General Category): {cutoff_text}. "
                          f"Note: Cutoffs vary by round and category.",
                "confidence": 0.85,
                "topics": ["cutoff"]
            }
        
        return None
    
    def _handle_course(self, query: str) -> Optional[Dict[str, Any]]:
        """Handle course/department queries"""
        q = query.lower()
        courses = self.data.get("courses", {})
        
        # All courses overview
        if "all" in q or "list" in q or "available" in q:
            btech_branches = list(courses.get("btech", {}).get("branches", {}).keys())
            other_courses = [k for k in courses.keys() if k != "btech"]
            return {
                "answer": f"BCREC offers B.Tech in: {', '.join([b.upper() for b in btech_branches])}. "
                          f"Also available: {', '.join([m.upper() for m in other_courses])}. "
                          f"Total B.Tech intake: 720+ seats across all branches.",
                "confidence": 0.9,
                "topics": ["all_courses"]
            }
        
        # Specific branch queries
        branch_map = {
            "cse": "cse",
            "computer science": "cse",
            "aiml": "cse_aiml",
            "ai ml": "cse_aiml",
            "ai/ml": "cse_aiml",
            "artificial intelligence": "cse_aiml",
            "it": "it",
            "information technology": "it",
            "ds": "ds",
            "data science": "ds",
            "csd": "csd",
            "computer science design": "csd",
            "ece": "ece",
            "electronics": "ece",
            "communication": "ece",
            "ee": "ee",
            "electrical": "ee",
            "me": "me",
            "mechanical": "me",
            "ce": "ce",
            "civil": "ce",
        }
        
        for key, branch_key in branch_map.items():
            if key in q:
                branch_data = courses.get("btech", {}).get("branches", {}).get(branch_key)
                if branch_data:
                    return {
                        "answer": f"{branch_data.get('full_name', 'B.Tech')}: "
                                  f"Seats: {branch_data.get('seats', 'Contact college')}, "
                                  f"WBJEE Cutoff: {branch_data.get('cutoff_general', 'Contact college')}, "
                                  f"Placement: {branch_data.get('placement_rate', 'Contact college')}, "
                                  f"Avg Salary: {branch_data.get('avg_salary', 'Contact college')}.",
                        "confidence": 0.95,
                        "topics": [branch_key]
                    }
        
        # MBA/MCA
        if "mba" in q:
            mba = courses.get("mba", {})
            return {
                "answer": f"MBA at BCREC: Duration {mba.get('duration', '2 years')}, "
                          f"Fees {mba.get('total_fees', 'Contact college')}, "
                          f"Seats: {mba.get('seats', '60')}, "
                          f"Entrance: {', '.join(mba.get('entrance_exams', ['MAT', 'CMAT', 'CAT']))}.",
                "confidence": 0.95,
                "topics": ["mba"]
            }
        
        if "mca" in q:
            mca = courses.get("mca", {})
            return {
                "answer": f"MCA at BCREC: Duration {mca.get('duration', '3 years')}, "
                          f"Fees {mca.get('total_fees', 'Contact college')}, "
                          f"Seats: {mca.get('seats', '60')}, "
                          f"Entrance: WB-JECA. "
                          f"Placement: {mca.get('placement_rate', 'Contact college')}.",
                "confidence": 0.95,
                "topics": ["mca"]
            }
        
        return None
    
    def _handle_placement(self, query: str) -> Optional[Dict[str, Any]]:
        """Handle placement-related queries"""
        q = query.lower()
        placements = self.data.get("placements", {})
        stats = placements.get("overall_stats", {})
        
        # Specific stats
        if "highest" in q and "package" in q:
            return {
                "answer": f"The highest placement package at BCREC is {stats.get('highest_package', '₹6.1 LPA')}.",
                "confidence": 0.95,
                "topics": ["highest_package"]
            }
        
        if "average" in q or "avg" in q:
            return {
                "answer": f"The average placement package at BCREC is approximately {stats.get('average_package', '₹3.93 LPA')}.",
                "confidence": 0.95,
                "topics": ["average_package"]
            }
        
        if "rate" in q or "percentage" in q or "placed" in q:
            return {
                "answer": f"BCREC placement rate: {stats.get('placement_rate', '80.62%')}. "
                          f"{stats.get('total_placed_2024', '550+')} students placed in 2024. "
                          f"{stats.get('total_placed_2025', '212+ (ongoing)')} in 2025.",
                "confidence": 0.95,
                "topics": ["placement_rate"]
            }
        
        if "recruiter" in q or "company" in q:
            recruiters = placements.get("top_recruiters", [])
            return {
                "answer": f"Top recruiters at BCREC: {', '.join(recruiters[:6])}. "
                          f"Companies like Wipro, HSBC, Godrej, Genpact regularly visit campus.",
                "confidence": 0.9,
                "topics": ["recruiters"]
            }
        
        # General placement
        return {
            "answer": f"BCREC Placements: {stats.get('placement_rate', '80.62%')} placement rate with "
                      f"highest package {stats.get('highest_package', '₹6.1 LPA')} and "
                      f"average package {stats.get('average_package', '₹3.93 LPA')}. "
                      f"Top recruiters: Wipro, HSBC, Godrej, Genpact.",
            "confidence": 0.95,
            "topics": ["placement_stats"]
        }
    
    def _handle_facility(self, query: str) -> Optional[Dict[str, Any]]:
        """Handle facility-related queries"""
        q = query.lower()
        facilities = self.data.get("facilities", {})
        
        # Infrastructure
        if "infrastructure" in q or "classroom" in q:
            infra = facilities.get("infrastructure", {})
            return {
                "answer": f"BCREC Infrastructure: {infra.get('classrooms', 48)} classrooms, "
                          f"well-equipped labs, library with extensive collection, "
                          f"indoor and outdoor sports facilities.",
                "confidence": 0.9,
                "topics": ["infrastructure"]
            }
        
        # Hostel
        if "hostel" in q or "accommodation" in q or "room" in q:
            return {
                "answer": "BCREC has separate hostels for boys and girls. "
                          "Hostel fees: approximately ₹35,000 per semester for boarding, "
                          "₹4,000 per month for mess. "
                          "Contact hostel office for details.",
                "confidence": 0.9,
                "topics": ["hostel"]
            }
        
        # Clubs
        if "club" in q:
            return {
                "answer": f"BCREC has {facilities.get('student_clubs', '20+')} student clubs including "
                          "dance, art, music, coding, and recitation clubs for overall development.",
                "confidence": 0.85,
                "topics": ["clubs"]
            }
        
        # Events
        if "event" in q or "fest" in q:
            events = facilities.get("events", {})
            return {
                "answer": f"BCREC major events: {events.get('zeal', 'ZEAL')} (annual cultural fest) "
                          f"and {events.get('horizon', 'HORIZON')} (technical fest). "
                          "Various sports events held annually.",
                "confidence": 0.9,
                "topics": ["events"]
            }
        
        return None
    
    def _handle_scholarship(self, query: str) -> Optional[Dict[str, Any]]:
        """Handle scholarship-related queries"""
        q = query.lower()
        scholarships = self.data.get("scholarships", {})
        
        # TFW
        if "tfw" in q or "tuition fee waiver" in q:
            return {
                "answer": f"Tuition Fee Waiver (TFW): {scholarships.get('tfw', 'Available for meritorious students from economically weaker sections. Contact college for details.')}",
                "confidence": 0.9,
                "topics": ["tfw"]
            }
        
        # General scholarships
        return {
            "answer": "BCREC Scholarships: 1) TFW scheme for economically weaker students. "
                      "2) Various state and central government scholarships available. "
                      "3) Merit-based scholarships for GATE qualified M.Tech students. "
                      "Contact accounts department for details.",
            "confidence": 0.9,
            "topics": ["scholarships"]
        }
    
    def _handle_general(self, query: str) -> Optional[Dict[str, Any]]:
        """Handle general queries about the college"""
        q = query.lower()
        college = self.data.get("college", {})
        
        # Location
        if "location" in q or "where" in q or "address" in q:
            return {
                "answer": f"BCREC is located in Durgapur, West Bengal at {college.get('address', 'Jemua Road, Fuljhore, Durgapur - 713206')}. "
                          f"Main office: 0343-2501353.",
                "confidence": 0.95,
                "topics": ["location"]
            }
        
        # Established
        if "established" in q or "history" in q or "when" in q:
            return {
                "answer": f"Dr. B.C. Roy Engineering College (BCREC) was established in {college.get('established', 2000)}. "
                          f"It is affiliated with {college.get('affiliation', 'MAKAUT')} and accredited by {', '.join(college.get('accreditation', ['NAAC', 'NBA', 'AICTE']))}.",
                "confidence": 0.95,
                "topics": ["overview"]
            }
        
        # Accreditation
        if "accreditation" in q or "accredited" in q or "naac" in q or "nba" in q or "aicte" in q:
            return {
                "answer": f"BCREC is accredited by {', '.join(college.get('accreditation', ['NAAC Grade B+', 'NBA', 'AICTE']))}. "
                          f"Affiliated with {college.get('affiliation', 'MAKAUT')}. "
                          f"NAAC Ranking: {college.get('ranking', {}).get('collegedunia_2025', '440th')}",
                "confidence": 0.95,
                "topics": ["accreditation"]
            }
        
        # Ranking
        if "ranking" in q or "ranked" in q:
            ranking = college.get("ranking", {})
            return {
                "answer": f"BCREC Rankings: Collegedunia 2025 - {ranking.get('collegedunia_2025', '440th')}, "
                          f"NIRF 2025 - {ranking.get('nirf_2025', '201-250')}. "
                          f"Campus area: {college.get('campus_area', '25 acres')}.",
                "confidence": 0.9,
                "topics": ["ranking"]
            }
        
        return None


# Singleton instance
lookup = StructuredLookup()


def structured_lookup(query: str, intent: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function for structured lookup.
    
    Args:
        query: User's question
        intent: Classified intent
        
    Returns:
        Lookup result dictionary or None
    """
    return lookup.lookup(query, intent)
