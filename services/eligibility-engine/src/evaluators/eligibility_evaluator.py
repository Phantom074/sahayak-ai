"""
Eligibility Evaluator
Business logic for determining if a user qualifies for a government scheme.
"""

import json
import boto3
import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from decimal import Decimal

from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

class EligibilityEvaluator:
    """Evaluates user eligibility against scheme rules."""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        self.rules_table_name = os.environ.get('RULES_TABLE', 'sahayak-eligibility-rules-dev')
        self.rules_table = self.dynamodb.Table(self.rules_table_name)
        
    def check_eligibility(self, scheme_id: str, user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Check if user meets eligibility criteria for a scheme."""
        # Get rules for the scheme
        rules = self._get_scheme_rules(scheme_id)
        
        if not rules:
            return {
                'scheme_id': scheme_id,
                'eligible': False,
                'reason': 'No eligibility rules found for this scheme',
                'reason_hi': 'इस योजना के लिए कोई पात्रता नियम नहीं मिले',
                'details': []
            }
        
        # Evaluate each rule
        evaluation_results = []
        total_weight = 0
        passed_weight = 0
        failed_criteria = []
        
        for rule in rules:
            field = rule.get('field')
            operator = rule.get('operator')
            value = rule.get('value')
            weight = rule.get('weight', 1.0)
            required = rule.get('required', False)
            
            # Evaluate the rule
            is_met, reason = self._evaluate_rule(user_profile, field, operator, value)
            
            evaluation_results.append({
                'field': field,
                'operator': operator,
                'value': value,
                'required': required,
                'weight': weight,
                'met': is_met,
                'reason': reason
            })
            
            total_weight += weight
            
            if is_met:
                passed_weight += weight
            else:
                failed_criteria.append({
                    'field': field,
                    'operator': operator,
                    'value': value,
                    'reason': reason
                })
                
                # If it's a required field and not met, user is not eligible
                if required:
                    return {
                        'scheme_id': scheme_id,
                        'eligible': False,
                        'reason': f'Required criterion not met: {field}',
                        'reason_hi': f'आवश्यक मानदंड पूरा नहीं हुआ: {field}',
                        'details': evaluation_results,
                        'failed_criteria': failed_criteria
                    }
        
        # Calculate eligibility percentage
        eligibility_percentage = (passed_weight / total_weight) * 100 if total_weight > 0 else 0
        
        # Determine final eligibility
        # For now, if more than 50% of weighted criteria are met, user is eligible
        is_eligible = eligibility_percentage >= 50.0
        
        return {
            'scheme_id': scheme_id,
            'eligible': is_eligible,
            'eligibility_percentage': round(eligibility_percentage, 2),
            'reason': 'Eligibility determined based on criteria evaluation' if is_eligible else 'Does not meet minimum criteria',
            'reason_hi': 'मानदंड मूल्यांकन के आधार पर पात्रता निर्धारित' if is_eligible else 'न्यूनतम मानदंड पूरा नहीं करता',
            'details': evaluation_results,
            'failed_criteria': failed_criteria if not is_eligible else [],
            'passed_criteria_count': len([r for r in evaluation_results if r['met']]),
            'total_criteria_count': len(evaluation_results)
        }
    
    def analyze_eligibility(self, scheme_id: str, user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Provide detailed analysis of eligibility criteria."""
        # Get rules for the scheme
        rules = self._get_scheme_rules(scheme_id)
        
        if not rules:
            return {
                'scheme_id': scheme_id,
                'analysis': 'No eligibility rules found for this scheme',
                'analysis_hi': 'इस योजना के लिए कोई पात्रता नियम नहीं मिले',
                'recommendations': [],
                'missing_info': []
            }
        
        # Identify missing information in user profile
        missing_fields = []
        for rule in rules:
            field = rule.get('field')
            if field not in user_profile:
                missing_fields.append(field)
        
        # Evaluate rules
        passed_rules = []
        failed_rules = []
        
        for rule in rules:
            field = rule.get('field')
            operator = rule.get('operator')
            value = rule.get('value')
            
            is_met, reason = self._evaluate_rule(user_profile, field, operator, value)
            
            rule_analysis = {
                'field': field,
                'operator': operator,
                'value': value,
                'met': is_met,
                'reason': reason
            }
            
            if is_met:
                passed_rules.append(rule_analysis)
            else:
                failed_rules.append(rule_analysis)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(failed_rules, user_profile)
        
        return {
            'scheme_id': scheme_id,
            'analysis': f'Analyzed {len(rules)} criteria. {len(passed_rules)} passed, {len(failed_rules)} failed.',
            'analysis_hi': f'{len(rules)} मानदंडों का विश्लेषण किया गया। {len(passed_rules)} पारित, {len(failed_rules)} असफल।',
            'passed_count': len(passed_rules),
            'failed_count': len(failed_rules),
            'total_count': len(rules),
            'passed_criteria': passed_rules,
            'failed_criteria': failed_rules,
            'missing_info': missing_fields,
            'recommendations': recommendations
        }
    
    def _get_scheme_rules(self, scheme_id: str) -> List[Dict[str, Any]]:
        """Get eligibility rules for a scheme."""
        try:
            response = self.rules_table.query(
                KeyConditionExpression=Key('scheme_id').eq(scheme_id) & Key('sk').eq('RULES#latest')
            )
            
            items = response.get('Items', [])
            
            if items:
                # Return the rules array from the first item
                return items[0].get('criteria', [])
            else:
                return []
        except Exception as e:
            logger.error(f"Error retrieving rules for scheme {scheme_id}: {str(e)}")
            return []
    
    def _evaluate_rule(self, user_profile: Dict[str, Any], field: str, operator: str, value: Any) -> tuple:
        """Evaluate a single rule against user profile."""
        user_value = user_profile.get(field)
        
        if user_value is None:
            return False, f"Field '{field}' not provided in user profile"
        
        # Convert values to appropriate types for comparison
        if isinstance(value, list):
            # Convert all values in the list to the same type as user_value
            typed_value = [self._convert_type(v, user_value) for v in value]
        else:
            typed_value = self._convert_type(value, user_value)
        
        # Apply the operator
        if operator == 'eq':
            result = user_value == typed_value
        elif operator == 'in':
            result = user_value in typed_value if isinstance(typed_value, list) else user_value == typed_value
        elif operator == 'not_in':
            result = user_value not in typed_value if isinstance(typed_value, list) else user_value != typed_value
        elif operator == 'lt':
            result = user_value < typed_value
        elif operator == 'lte':
            result = user_value <= typed_value
        elif operator == 'gt':
            result = user_value > typed_value
        elif operator == 'gte':
            result = user_value >= typed_value
        elif operator == 'between':
            if isinstance(typed_value, list) and len(typed_value) == 2:
                result = typed_value[0] <= user_value <= typed_value[1]
            else:
                result = False
        elif operator == 'exists':
            result = user_value is not None
        elif operator == 'bool':
            result = bool(user_value) == bool(typed_value)
        elif operator == 'contains':
            if isinstance(user_value, list):
                result = typed_value in user_value
            elif isinstance(user_value, str):
                result = str(typed_value) in user_value
            else:
                result = False
        else:
            # Unknown operator
            return False, f"Unknown operator: {operator}"
        
        if result:
            return True, "Criteria met"
        else:
            return False, f"Field '{field}' does not meet criteria ({operator} {typed_value})"
    
    def _convert_type(self, value: Any, reference_value: Any) -> Any:
        """Convert value to match the type of reference value."""
        if isinstance(reference_value, int):
            try:
                return int(float(value))  # Convert float string to int
            except (ValueError, TypeError):
                return value
        elif isinstance(reference_value, float):
            try:
                return float(value)
            except (ValueError, TypeError):
                return value
        elif isinstance(reference_value, str):
            return str(value)
        elif isinstance(reference_value, bool):
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)
        else:
            return value
    
    def _generate_recommendations(self, failed_rules: List[Dict], user_profile: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on failed criteria."""
        recommendations = []
        
        for rule in failed_rules:
            field = rule['field']
            operator = rule['operator']
            value = rule['value']
            
            if field == 'age':
                if operator in ['gte', 'between']:
                    recommendations.append(f"Consider schemes for younger applicants if available")
                elif operator == 'lte':
                    recommendations.append(f"Consider senior citizen schemes")
            elif field == 'income':
                if operator == 'lte':
                    recommendations.append(f"Look for schemes with higher income limits")
            elif field == 'occupation':
                if operator == 'in':
                    recommendations.append(f"Consider updating your occupation to one of: {', '.join(value)}")
            elif field == 'state':
                if operator == 'in':
                    recommendations.append(f"Check if this scheme is available in other states")
            elif field == 'category':
                if operator == 'in':
                    recommendations.append(f"Verify if you qualify under other categories like OBC, SC, ST, etc.")
        
        return recommendations
    
    def get_eligibility_summary(self, user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Get summary of all schemes user is eligible for."""
        # This would involve checking against all available schemes
        # For performance, this would likely be implemented differently in production
        # Perhaps using a precomputed matrix or separate service
        
        # Placeholder implementation
        return {
            'summary': 'Eligibility summary across all schemes',
            'total_schemes': 0,
            'eligible_schemes': [],
            'ineligible_schemes': [],
            'partially_eligible_schemes': []
        }