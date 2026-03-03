"""
Unit tests for the Eligibility Engine
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import sys
import os

# Add the services directory to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'eligibility-engine', 'src'))

from evaluators.eligibility_evaluator import EligibilityEvaluator
from rules.rule_engine import RuleEngine


class TestEligibilityEvaluator(unittest.TestCase):
    """Test cases for Eligibility Evaluator."""

    def setUp(self):
        """Set up test fixtures."""
        self.evaluator = EligibilityEvaluator()

    @patch.object(EligibilityEvaluator, '_get_scheme_rules')
    def test_check_eligibility_fully_eligible(self, mock_get_rules):
        """Test eligibility check for fully eligible user."""
        # Mock rules for a scheme
        mock_rules = [
            {
                'field': 'age',
                'operator': 'gte',
                'value': 18,
                'weight': 1.0,
                'required': True
            },
            {
                'field': 'income',
                'operator': 'lte',
                'value': 300000,
                'weight': 2.0,
                'required': False
            },
            {
                'field': 'occupation',
                'operator': 'in',
                'value': ['farmer', 'laborer'],
                'weight': 1.5,
                'required': False
            }
        ]
        mock_get_rules.return_value = mock_rules
        
        # User profile that meets all criteria
        user_profile = {
            'age': 25,
            'income': 250000,
            'occupation': 'farmer'
        }
        
        result = self.evaluator.check_eligibility('test-scheme-123', user_profile)
        
        self.assertTrue(result['eligible'])
        self.assertEqual(result['eligibility_percentage'], 100.0)
        self.assertEqual(result['passed_criteria_count'], 3)
        self.assertEqual(result['total_criteria_count'], 3)

    @patch.object(EligibilityEvaluator, '_get_scheme_rules')
    def test_check_eligibility_not_eligible_required_field(self, mock_get_rules):
        """Test eligibility check when required field is not met."""
        # Mock rules for a scheme
        mock_rules = [
            {
                'field': 'age',
                'operator': 'gte',
                'value': 18,
                'weight': 1.0,
                'required': True  # This is required
            },
            {
                'field': 'income',
                'operator': 'lte',
                'value': 300000,
                'weight': 2.0,
                'required': False
            }
        ]
        mock_get_rules.return_value = mock_rules
        
        # User profile that doesn't meet required criteria
        user_profile = {
            'age': 16,  # Too young
            'income': 250000
        }
        
        result = self.evaluator.check_eligibility('test-scheme-123', user_profile)
        
        self.assertFalse(result['eligible'])
        self.assertIn('required', result['reason'])

    @patch.object(EligibilityEvaluator, '_get_scheme_rules')
    def test_check_eligibility_partial_eligible(self, mock_get_rules):
        """Test eligibility check for partially eligible user."""
        # Mock rules for a scheme
        mock_rules = [
            {
                'field': 'age',
                'operator': 'gte',
                'value': 18,
                'weight': 1.0,
                'required': False
            },
            {
                'field': 'income',
                'operator': 'lte',
                'value': 300000,
                'weight': 2.0,
                'required': False
            },
            {
                'field': 'occupation',
                'operator': 'in',
                'value': ['farmer', 'laborer'],
                'weight': 1.5,
                'required': False
            }
        ]
        mock_get_rules.return_value = mock_rules
        
        # User profile that meets some criteria
        user_profile = {
            'age': 25,
            'income': 400000,  # Above limit
            'occupation': 'farmer'
        }
        
        result = self.evaluator.check_eligibility('test-scheme-123', user_profile)
        
        # Should be eligible if more than 50% of weighted criteria are met
        # age: 1.0 weight, income: 0 weight, occupation: 1.5 weight
        # Total: 2.5/3.5 = 71.4% > 50%, so eligible
        self.assertTrue(result['eligible'])
        self.assertGreater(result['eligibility_percentage'], 50.0)

    def test_evaluate_rule_equal_operator(self):
        """Test rule evaluation with equal operator."""
        user_profile = {'age': 25}
        result, _ = self.evaluator._evaluate_rule(user_profile, 'age', 'eq', 25)
        self.assertTrue(result)

    def test_evaluate_rule_in_operator(self):
        """Test rule evaluation with in operator."""
        user_profile = {'occupation': 'farmer'}
        result, _ = self.evaluator._evaluate_rule(user_profile, 'occupation', 'in', ['farmer', 'teacher', 'doctor'])
        self.assertTrue(result)

    def test_evaluate_rule_not_in_operator(self):
        """Test rule evaluation with not_in operator."""
        user_profile = {'occupation': 'engineer'}
        result, _ = self.evaluator._evaluate_rule(user_profile, 'occupation', 'not_in', ['farmer', 'teacher', 'doctor'])
        self.assertTrue(result)

    def test_evaluate_rule_comparison_operators(self):
        """Test rule evaluation with comparison operators."""
        user_profile = {'age': 25}
        
        # Greater than or equal
        result, _ = self.evaluator._evaluate_rule(user_profile, 'age', 'gte', 20)
        self.assertTrue(result)
        
        # Less than
        result, _ = self.evaluator._evaluate_rule(user_profile, 'age', 'lt', 30)
        self.assertTrue(result)
        
        # Between
        result, _ = self.evaluator._evaluate_rule(user_profile, 'age', 'between', [20, 30])
        self.assertTrue(result)

    def test_generate_recommendations(self):
        """Test recommendation generation."""
        failed_rules = [
            {
                'field': 'age',
                'operator': 'gte',
                'value': 60
            },
            {
                'field': 'income',
                'operator': 'lte',
                'value': 200000
            }
        ]
        user_profile = {'age': 30, 'income': 300000}
        
        recommendations = self.evaluator._generate_recommendations(failed_rules, user_profile)
        
        # Should have recommendations for both failed criteria
        self.assertGreaterEqual(len(recommendations), 1)


class TestRuleEngine(unittest.TestCase):
    """Test cases for Rule Engine."""

    def setUp(self):
        """Set up test fixtures."""
        self.rule_engine = RuleEngine()

    @patch('boto3.resource')
    def test_get_rules_success(self, mock_dynamodb_resource):
        """Test successful retrieval of rules."""
        # Mock the DynamoDB table
        mock_table = Mock()
        mock_dynamodb_resource.return_value.Table.return_value = mock_table
        
        mock_table.query.return_value = {
            'Items': [{
                'scheme_id': 'test-scheme-123',
                'sk': 'RULES#latest',
                'criteria': [
                    {
                        'field': 'age',
                        'operator': 'gte',
                        'value': 18,
                        'weight': 1.0,
                        'required': True
                    }
                ]
            }]
        }
        
        rules = self.rule_engine.get_rules('test-scheme-123')
        
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]['field'], 'age')

    @patch('boto3.resource')
    def test_get_rules_not_found(self, mock_dynamodb_resource):
        """Test retrieval of rules when none exist."""
        # Mock the DynamoDB table
        mock_table = Mock()
        mock_dynamodb_resource.return_value.Table.return_value = mock_table
        
        mock_table.query.return_value = {'Items': []}
        
        rules = self.rule_engine.get_rules('nonexistent-scheme')
        
        self.assertEqual(len(rules), 0)

    @patch('boto3.resource')
    def test_update_rules_success(self, mock_dynamodb_resource):
        """Test successful update of rules."""
        # Mock the DynamoDB table
        mock_table = Mock()
        mock_dynamodb_resource.return_value.Table.return_value = mock_table
        
        mock_table.put_item.return_value = {}
        
        rules = [
            {
                'field': 'age',
                'operator': 'gte',
                'value': 18,
                'weight': 1.0,
                'required': True
            }
        ]
        
        result = self.rule_engine.update_rules('test-scheme-123', rules)
        
        self.assertTrue(result)
        mock_table.put_item.assert_called_once()

    @patch('boto3.resource')
    def test_validate_rules_structure(self, mock_dynamodb_resource):
        """Test validation of rule structure."""
        # Valid rule
        valid_rule = {
            'field': 'age',
            'operator': 'gte',
            'value': 18,
            'weight': 1.0,
            'required': True
        }
        
        is_valid, message = self.rule_engine.validate_rule(valid_rule)
        self.assertTrue(is_valid)
        
        # Invalid rule (missing required field)
        invalid_rule = {
            'field': 'age',
            'operator': 'gte',
            'value': 18
            # Missing 'weight' and 'required'
        }
        
        is_valid, message = self.rule_engine.validate_rule(invalid_rule)
        self.assertFalse(is_valid)


if __name__ == '__main__':
    unittest.main()