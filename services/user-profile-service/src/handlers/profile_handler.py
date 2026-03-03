"""
User Profile Handler
API endpoints for user profile management and privacy controls.
"""

import json
import logging
import os
import uuid
from typing import Dict, Any, Optional

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent

from ..repositories.profile_repository import ProfileRepository
from ..privacy.consent_manager import ConsentManager
from ..privacy.data_masker import DataMasker

logger = Logger()
tracer = Tracer()

class UserProfileHandler:
    """Handles user profile operations."""
    
    def __init__(self):
        self.repo = ProfileRepository()
        self.consent_manager = ConsentManager()
        self.masker = DataMasker()
    
    @tracer.capture_method
    def create_profile(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user profile."""
        try:
            body = json.loads(event.get('body', '{}')) if event.get('body') else {}
            
            # Validate required fields
            required_fields = ['phone_number', 'language_preference']
            for field in required_fields:
                if field not in body:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({
                            'error': f'Missing required field: {field}',
                            'message_hi': f'आवश्यक फ़ील्ड गुम: {field}'
                        })
                    }
            
            # Create profile
            profile_id = self.repo.create_profile(body)
            
            return {
                'statusCode': 201,
                'body': json.dumps({
                    'profile_id': profile_id,
                    'message': 'Profile created successfully',
                    'message_hi': 'प्रोफ़ाइल सफलतापूर्वक बनाया गया'
                }),
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                }
            }
            
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Invalid JSON in request body',
                    'message_hi': 'अनुरोध शरीर में अमान्य JSON'
                })
            }
        except Exception as e:
            logger.exception(f"Error creating profile: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Internal server error',
                    'message': str(e),
                    'message_hi': 'आंतरिक सर्वर त्रुटि'
                })
            }
    
    @tracer.capture_method
    def get_profile(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Get user profile by ID."""
        try:
            profile_id = event['pathParameters']['profile_id']
            
            # Get profile
            profile = self.repo.get_profile(profile_id)
            
            if not profile:
                return {
                    'statusCode': 404,
                    'body': json.dumps({
                        'error': 'Profile not found',
                        'message_hi': 'प्रोफ़ाइल नहीं मिला'
                    })
                }
            
            # Apply data masking based on consent
            masked_profile = self.masker.apply_masking(profile, profile_id)
            
            return {
                'statusCode': 200,
                'body': json.dumps(masked_profile),
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                }
            }
            
        except KeyError:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing profile_id in path',
                    'message_hi': 'पथ में profile_id गुम'
                })
            }
        except Exception as e:
            logger.exception(f"Error getting profile: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Internal server error',
                    'message': str(e),
                    'message_hi': 'आंतरिक सर्वर त्रुटि'
                })
            }
    
    @tracer.capture_method
    def update_profile(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Update user profile."""
        try:
            profile_id = event['pathParameters']['profile_id']
            body = json.loads(event.get('body', '{}')) if event.get('body') else {}
            
            # Update profile
            success = self.repo.update_profile(profile_id, body)
            
            if not success:
                return {
                    'statusCode': 404,
                    'body': json.dumps({
                        'error': 'Profile not found',
                        'message_hi': 'प्रोफ़ाइल नहीं मिला'
                    })
                }
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'profile_id': profile_id,
                    'message': 'Profile updated successfully',
                    'message_hi': 'प्रोफ़ाइल सफलतापूर्वक अपडेट किया गया'
                }),
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                }
            }
            
        except KeyError:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing profile_id in path',
                    'message_hi': 'पथ में profile_id गुम'
                })
            }
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Invalid JSON in request body',
                    'message_hi': 'अनुरोध शरीर में अमान्य JSON'
                })
            }
        except Exception as e:
            logger.exception(f"Error updating profile: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Internal server error',
                    'message': str(e),
                    'message_hi': 'आंतरिक सर्वर त्रुटि'
                })
            }
    
    @tracer.capture_method
    def get_consent_status(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Get user's consent status."""
        try:
            profile_id = event['pathParameters']['profile_id']
            
            # Get consent status
            consent_status = self.consent_manager.get_consent_status(profile_id)
            
            return {
                'statusCode': 200,
                'body': json.dumps(consent_status),
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                }
            }
            
        except KeyError:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing profile_id in path',
                    'message_hi': 'पथ में profile_id गुम'
                })
            }
        except Exception as e:
            logger.exception(f"Error getting consent status: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Internal server error',
                    'message': str(e),
                    'message_hi': 'आंतरिक सर्वर त्रुटि'
                })
            }
    
    @tracer.capture_method
    def update_consent(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Update user's consent preferences."""
        try:
            profile_id = event['pathParameters']['profile_id']
            body = json.loads(event.get('body', '{}')) if event.get('body') else {}
            
            granted_purposes = body.get('granted_purposes', [])
            revoked_purposes = body.get('revoked_purposes', [])
            
            # Update consent
            consent_result = self.consent_manager.update_consent(
                profile_id, granted_purposes, revoked_purposes
            )
            
            return {
                'statusCode': 200,
                'body': json.dumps(consent_result),
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                }
            }
            
        except KeyError:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing profile_id in path',
                    'message_hi': 'पथ में profile_id गुम'
                })
            }
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Invalid JSON in request body',
                    'message_hi': 'अनुरोध शरीर में अमान्य JSON'
                })
            }
        except Exception as e:
            logger.exception(f"Error updating consent: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Internal server error',
                    'message': str(e),
                    'message_hi': 'आंतरिक सर्वर त्रुटि'
                })
            }


def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda entry point for user profile management."""
    handler = UserProfileHandler()
    
    # Extract HTTP method and path
    http_method = event.get('httpMethod', '').upper()
    resource_path = event.get('resource', '')
    
    try:
        if resource_path == '/profiles' and http_method == 'POST':
            return handler.create_profile(event)
        elif resource_path == '/profiles/{profile_id}' and http_method == 'GET':
            return handler.get_profile(event)
        elif resource_path == '/profiles/{profile_id}' and http_method == 'PUT':
            return handler.update_profile(event)
        elif resource_path == '/profiles/{profile_id}/consent' and http_method == 'GET':
            return handler.get_consent_status(event)
        elif resource_path == '/profiles/{profile_id}/consent' and http_method == 'POST':
            return handler.update_consent(event)
        else:
            return {
                'statusCode': 404,
                'body': json.dumps({
                    'error': 'Resource not found',
                    'message_hi': 'संसाधन नहीं मिला'
                })
            }
    except Exception as e:
        logger.exception(f"Unhandled error in profile handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e),
                'message_hi': 'आंतरिक सर्वर त्रुटि'
            })
        }