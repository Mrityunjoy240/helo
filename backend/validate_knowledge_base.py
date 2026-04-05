"""
Knowledge Base Validator
Validates the completeness and quality of the extracted knowledge base
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KnowledgeValidator:
    """Validate knowledge base completeness and quality"""
    
    def __init__(self, kb_path: Path):
        self.kb_path = kb_path
        self.kb = self.load_knowledge_base()
        self.issues = []
        self.warnings = []
        self.suggestions = []
    
    def load_knowledge_base(self) -> Dict:
        """Load knowledge base from JSON"""
        try:
            with open(self.kb_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load knowledge base: {e}")
            return {}
    
    def check_required_sections(self) -> bool:
        """Check if all required sections exist"""
        required_sections = [
            "courses", "fees", "admissions", "contact", 
            "eligibility", "faqs"
        ]
        
        missing = []
        for section in required_sections:
            if section not in self.kb or not self.kb[section]:
                missing.append(section)
        
        if missing:
            self.issues.append(f"❌ Missing required sections: {', '.join(missing)}")
            return False
        else:
            logger.info("✅ All required sections present")
            return True
    
    def check_courses(self) -> Tuple[bool, List[str]]:
        """Validate courses section"""
        issues = []
        
        if not self.kb.get("courses"):
            issues.append("No courses found")
            return False, issues
        
        courses = self.kb["courses"]
        logger.info(f"Found {len(courses)} courses")
        
        # Check each course has required fields
        required_fields = ["department", "course_name", "duration", "intake"]
        
        for idx, course in enumerate(courses):
            missing_fields = [f for f in required_fields if not course.get(f)]
            if missing_fields:
                issues.append(f"Course {idx+1} missing: {', '.join(missing_fields)}")
        
        if not issues:
            logger.info("✅ All courses have required information")
            return True, []
        else:
            return False, issues
    
    def check_fees(self) -> Tuple[bool, List[str]]:
        """Validate fees section"""
        issues = []
        
        if not self.kb.get("fees"):
            issues.append("No fee information found")
            return False, issues
        
        fees = self.kb["fees"]
        
        # Check for common degree types
        degree_types = ["btech", "mtech", "mba"]
        found_degrees = [d for d in degree_types if fees.get(d)]
        
        if not found_degrees:
            issues.append("No fee information for any degree program")
            return False, issues
        
        logger.info(f"✅ Fee information found for: {', '.join(found_degrees)}")
        
        # Check if hostel fees are present
        if not fees.get("hostel"):
            self.warnings.append("⚠️ No hostel fee information found")
        
        return True, issues
    
    def check_eligibility(self) -> Tuple[bool, List[str]]:
        """Validate eligibility criteria"""
        issues = []
        
        if not self.kb.get("eligibility"):
            issues.append("No eligibility criteria found")
            return False, issues
        
        eligibility = self.kb["eligibility"]
        
        # Check for common programs
        if not eligibility.get("btech"):
            self.warnings.append("⚠️ No BTech eligibility criteria")
        
        logger.info("✅ Eligibility criteria present")
        return True, issues
    
    def check_contact_info(self) -> Tuple[bool, List[str]]:
        """Validate contact information"""
        issues = []
        
        contact = self.kb.get("contact", {})
        
        if not contact.get("phone") and not contact.get("email"):
            issues.append("No contact phone or email found")
            return False, issues
        
        if not contact.get("phone"):
            self.warnings.append("⚠️ No phone number found")
        
        if not contact.get("email"):
            self.warnings.append("⚠️ No email address found")
        
        if not contact.get("address"):
            self.warnings.append("⚠️ No physical address found")
        
        logger.info("✅ Contact information present")
        return True, issues
    
    def check_faqs(self) -> Tuple[bool, List[str]]:
        """Validate FAQs"""
        issues = []
        
        faqs = self.kb.get("faqs", [])
        
        if len(faqs) < 5:
            self.warnings.append(f"⚠️ Only {len(faqs)} FAQs found. Recommend at least 10-15 FAQs")
        else:
            logger.info(f"✅ {len(faqs)} FAQs generated")
        
        # Check FAQ categories
        categories = set(faq.get("category") for faq in faqs if faq.get("category"))
        logger.info(f"FAQ categories: {', '.join(categories)}")
        
        return True, issues
    
    def suggest_improvements(self):
        """Suggest improvements to knowledge base"""
        
        # Check for missing common sections
        optional_sections = {
            "facilities": "Campus facilities information",
            "placements": "Placement statistics and companies",
            "scholarships": "Scholarship opportunities",
            "hostel": "Hostel facilities and rules",
            "important_dates": "Academic calendar and deadlines"
        }
        
        for section, description in optional_sections.items():
            if not self.kb.get(section) or not self.kb[section]:
                self.suggestions.append(f"💡 Add {section}: {description}")
        
        # Check FAQ coverage
        faq_categories = set(faq.get("category") for faq in self.kb.get("faqs", []))
        recommended_categories = {"fees", "courses", "eligibility", "admission", "hostel", "placements"}
        missing_categories = recommended_categories - faq_categories
        
        if missing_categories:
            self.suggestions.append(f"💡 Add FAQs for: {', '.join(missing_categories)}")
    
    def validate(self) -> bool:
        """Run all validation checks"""
        print("\n" + "="*60)
        print("KNOWLEDGE BASE VALIDATION REPORT")
        print("="*60)
        
        all_valid = True
        
        # Run checks
        print("\n📋 Checking required sections...")
        if not self.check_required_sections():
            all_valid = False
        
        print("\n📚 Validating courses...")
        courses_valid, course_issues = self.check_courses()
        if not courses_valid:
            all_valid = False
            self.issues.extend(course_issues)
        
        print("\n💰 Validating fees...")
        fees_valid, fee_issues = self.check_fees()
        if not fees_valid:
            all_valid = False
            self.issues.extend(fee_issues)
        
        print("\n📝 Validating eligibility...")
        elig_valid, elig_issues = self.check_eligibility()
        if not elig_valid:
            all_valid = False
            self.issues.extend(elig_issues)
        
        print("\n📞 Validating contact info...")
        contact_valid, contact_issues = self.check_contact_info()
        if not contact_valid:
            all_valid = False
            self.issues.extend(contact_issues)
        
        print("\n❓ Validating FAQs...")
        self.check_faqs()
        
        print("\n💡 Generating improvement suggestions...")
        self.suggest_improvements()
        
        # Print results
        self.print_report()
        
        return all_valid
    
    def print_report(self):
        """Print validation report"""
        print("\n" + "="*60)
        print("VALIDATION RESULTS")
        print("="*60)
        
        if self.issues:
            print("\n❌ CRITICAL ISSUES:")
            for issue in self.issues:
                print(f"  {issue}")
        
        if self.warnings:
            print("\n⚠️ WARNINGS:")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if self.suggestions:
            print("\n💡 SUGGESTIONS FOR IMPROVEMENT:")
            for suggestion in self.suggestions:
                print(f"  {suggestion}")
        
        if not self.issues and not self.warnings:
            print("\n✅ Knowledge base is complete and well-structured!")
        elif not self.issues:
            print("\n✅ Knowledge base is valid with minor warnings")
        else:
            print("\n❌ Knowledge base has critical issues that need to be addressed")
        
        print("="*60)
    
    def generate_coverage_report(self):
        """Generate detailed coverage report"""
        print("\n" + "="*60)
        print("KNOWLEDGE COVERAGE REPORT")
        print("="*60)
        
        coverage = {
            "Courses": len(self.kb.get("courses", [])),
            "Faculty": len(self.kb.get("faculty", [])),
            "FAQs": len(self.kb.get("faqs", [])),
            "Important Dates": len(self.kb.get("important_dates", [])),
            "Scholarships": len(self.kb.get("scholarships", [])),
            "Fee Categories": len([k for k, v in self.kb.get("fees", {}).items() if v]),
            "Contact Methods": len(self.kb.get("contact", {}).get("phone", [])) + len(self.kb.get("contact", {}).get("email", []))
        }
        
        for category, count in coverage.items():
            status = "✅" if count > 0 else "❌"
            print(f"{status} {category}: {count}")
        
        print("="*60)


def main():
    """Main validation function"""
    kb_path = Path("backend/data/knowledge_base.json")
    
    if not kb_path.exists():
        print(f"❌ Knowledge base not found at {kb_path}")
        print("Please run knowledge_extractor_advanced.py first")
        return
    
    validator = KnowledgeValidator(kb_path)
    is_valid = validator.validate()
    validator.generate_coverage_report()
    
    if is_valid:
        print("\n✅ Knowledge base is ready for use!")
    else:
        print("\n⚠️ Please address the issues before using the knowledge base")


if __name__ == "__main__":
    main()
