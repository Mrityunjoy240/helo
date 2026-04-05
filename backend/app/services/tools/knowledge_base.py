import json
import logging
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)


class BCRECKnowledgeBase:
    """
    Unified BCREC Knowledge Base for fast, accurate answers.
    Uses the combined_kb.json for all college information.
    """

    def __init__(self, data_path: str = None):
        if data_path is None:
            data_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "data", "knowledge_base", "combined_kb.json"
            )
        self.data = self._load(data_path)
        self._build_indexes()

    def _load(self, path: str) -> Dict[str, Any]:
        """Load the combined knowledge base"""
        try:
            module_dir = os.path.dirname(os.path.abspath(__file__))
            abs_path = os.path.normpath(os.path.join(module_dir, "..", "..", "data", "knowledge_base", "combined_kb.json"))
            
            if os.path.exists(abs_path):
                with open(abs_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"BCREC Knowledge Base loaded from {abs_path}")
                    return data
            else:
                logger.warning(f"Knowledge base not found at {abs_path}")
                return {}
        except Exception as e:
            logger.error(f"Failed to load knowledge base: {e}")
            return {}

    def _build_indexes(self):
        """Build quick lookup indexes"""
        self.courses_index = {}
        self.dept_hod_index = {}
        self.quick_answers = {}

        if not self.data:
            return

        # Index courses by code
        courses = self.data.get("courses", {})
        for course_type, course_data in courses.items():
            if isinstance(course_data, dict):
                for code, info in course_data.items():
                    if isinstance(info, dict):
                        info["course_type"] = course_type
                        self.courses_index[code] = info
                        self.courses_index[code.lower()] = info

        # Index HODs
        depts = self.data.get("departments", {})
        for dept_code, dept_info in depts.items():
            self.dept_hod_index[dept_code] = dept_info
            self.dept_hod_index[dept_code.lower()] = dept_info

        # Quick answers
        self.quick_answers = self.data.get("quick_answers", {})

    def get_course_info(self, course_code: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific course"""
        code = course_code.upper().replace("-", "").replace(" ", "")
        
        # Direct code mapping
        code_map = {
            "CSE": "CSE",
            "IT": "IT", 
            "ECE": "ECE",
            "EE": "EE",
            "ME": "ME",
            "CE": "CE",
            "CSD": "CSD",
            "AIML": "AIML",
            "DS": "DS",
            "CY": "CY",
            "MBA": "MBA",
            "MCA": "MCA",
            "MTECH": "M.Tech"
        }
        
        mapped_code = code_map.get(code)
        if mapped_code and mapped_code in self.courses_index:
            return self.courses_index[mapped_code]
        
        # Fallback to partial match
        for key, value in self.courses_index.items():
            if code.lower() in key.lower() or key.lower() in code.lower():
                return value
        
        return None

    def get_course_fees(self, course_code: str) -> str:
        """Get fee for a course"""
        course = self.get_course_info(course_code)
        if not course:
            return None
        
        if course.get("fees"):
            total = course["fees"].get("total", "N/A")
            admission = course["fees"].get("admission", "N/A")
            return f"Total fees: Rs. {total:,}. Admission fee: Rs. {admission:,}."
        
        return None

    def get_placement_info(self, course_code: str = None) -> Dict[str, Any]:
        """Get placement information"""
        if course_code:
            course = self.get_course_info(course_code)
            if course and course.get("placement"):
                return {
                    "course": course.get("full_name", course_code),
                    "placement": course["placement"]
                }
        
        # Return overall placement
        placements = self.data.get("placements", {})
        return {
            "overall_rate": placements.get("overall_rate_2025", "N/A"),
            "highest_package": placements.get("highest_package", {}),
            "top_companies": placements.get("top_companies_2026", [])
        }

    def get_hostel_info(self) -> Dict[str, Any]:
        """Get hostel information"""
        return self.data.get("hostel", {})

    def get_admission_info(self, info_type: str = "all") -> Dict[str, Any]:
        """Get admission information"""
        admission = self.data.get("admission", {})
        
        if info_type == "eligibility":
            return admission.get("eligibility", {})
        elif info_type == "scholarship":
            return admission.get("scholarships", {})
        elif info_type == "spot":
            return admission.get("spot_round", {})
        elif info_type == "nri":
            return admission.get("nri_quota", {})
        
        return admission

    def get_hod_info(self, department: str) -> Optional[Dict[str, Any]]:
        """Get HOD information for a department"""
        dept = department.upper().replace("-", "").replace(" ", "")
        
        dept_map = {
            "CSE": "CSE", "COMPUTER": "CSE", "IT": "IT",
            "ECE": "ECE", "ELECTRONICS": "ECE",
            "EE": "EE", "ELECTRICAL": "EE",
            "ME": "ME", "MECHANICAL": "ME",
            "CE": "CE", "CIVIL": "CE",
            "CSD": "CSD", "DESIGN": "CSD",
            "AIML": "AIML", "AI": "AIML", "ML": "AIML",
            "DS": "DS", "DATASCIENCE": "DS",
            "CY": "CY", "CYBER": "CY", "SECURITY": "CY",
            "MBA": "MBA", "MANAGEMENT": "MBA",
            "MCA": "MCA", "COMPUTERAPPLICATIONS": "MCA"
        }
        
        mapped_dept = dept_map.get(dept)
        if mapped_dept:
            return self.dept_hod_index.get(mapped_dept)
        
        return None

    def get_cutoff(self, course_code: str = None) -> Dict[str, Any]:
        """Get WBJEE cutoff information"""
        if course_code:
            course = self.get_course_info(course_code)
            if course and course.get("cutoff"):
                return {
                    "course": course.get("full_name", course_code),
                    "cutoff": course["cutoff"]
                }
        
        # Return all cutoffs
        cutoffs = {}
        for code, course in self.courses_index.items():
            if course.get("course_type") == "btech" and course.get("cutoff"):
                cutoffs[code] = course["cutoff"]
        return cutoffs

    def get_infrastructure_info(self) -> Dict[str, Any]:
        """Get infrastructure information"""
        return self.data.get("infrastructure", {})

    def get_student_life_info(self) -> Dict[str, Any]:
        """Get student life information"""
        return self.data.get("student_life", {})

    def get_college_overview(self) -> Dict[str, Any]:
        """Get basic college information"""
        return self.data.get("college", {})

    def get_principal_info(self) -> Dict[str, Any]:
        """Get principal information"""
        return self.data.get("principal", {})

    def format_response(self, query_type: str, data: Dict[str, Any]) -> str:
        """Format data into a conversational response"""
        if not data:
            return "Information not available. Please contact the college directly."
        
        if query_type == "course":
            course = data
            parts = [
                f"{course.get('full_name', 'Course')} ({course.get('course_type', '').upper()})",
                f"Intake: {course.get('intake', 'N/A')} students",
                f"Duration: {course.get('duration', 'N/A')}",
            ]
            if course.get("fees"):
                parts.append(f"Total Fee: Rs. {course['fees'].get('total', 'N/A'):,}")
            if course.get("nba"):
                parts.append("NBA Accredited")
            if course.get("placement"):
                p = course["placement"]
                parts.append(f"Placement: {p.get('2024-25', 'N/A')} (2024-25)")
            return ". ".join(str(p) for p in parts if p)
        
        elif query_type == "hod":
            hod = data.get("hod", {})
            parts = [
                f"HOD of {data.get('course', 'Department')}: {hod.get('name', 'N/A')}",
            ]
            if hod.get("email"):
                parts.append(f"Email: {hod['email']}")
            if hod.get("mobile"):
                parts.append(f"Phone: {hod['mobile']}")
            return ". ".join(str(p) for p in parts if p)
        
        elif query_type == "placement":
            if "overall_rate" in data:
                return f"BCREC placement rate: {data.get('overall_rate', 'N/A')}. Highest package: Rs. {data.get('highest_package', {}).get('amount', 'N/A')} LPA from {data.get('highest_package', {}).get('company', 'N/A')}."
            return str(data)
        
        return str(data)


_kb_instance = None

def get_knowledge_base() -> BCRECKnowledgeBase:
    """Get singleton knowledge base instance"""
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = BCRECKnowledgeBase()
    return _kb_instance
