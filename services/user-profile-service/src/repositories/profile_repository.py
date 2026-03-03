"""
Profile Repository
Data access layer for user profile management.
"""

import json
import boto3
import uuid
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from decimal import Decimal

from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

class ProfileRepository:
    """Manages user profile data in DynamoDB."""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        self.table_name = os.environ.get('USERS_TABLE', 'sahayak-users-dev')
        self.table = self.dynamodb.Table(self.table_name)
        
    def create_profile(self, profile_data: Dict[str, Any]) -> str:
        """Create a new user profile."""
        profile_id = f"profile_{uuid.uuid4().hex}"
        
        # Prepare profile record
        profile_record = {
            'profile_id': profile_id,
            'pk': f"USER#{profile_id}",
            'sk': "PROFILE#latest",
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'version': 1,
            **profile_data
        }
        
        # Add default fields if not present
        if 'status' not in profile_record:
            profile_record['status'] = 'active'
        if 'language_preference' not in profile_record:
            profile_record['language_preference'] = 'hi'
        if 'consent_status' not in profile_record:
            profile_record['consent_status'] = {}
        if 'preferences' not in profile_record:
            profile_record['preferences'] = {}
        
        # Encrypt sensitive data
        profile_record = self._encrypt_sensitive_fields(profile_record)
        
        # Insert into DynamoDB
        self.table.put_item(Item=profile_record)
        
        logger.info(f"Created profile: {profile_id}")
        return profile_id
    
    def get_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a user profile by ID."""
        try:
            response = self.table.get_item(
                Key={
                    'pk': f"USER#{profile_id}",
                    'sk': "PROFILE#latest"
                }
            )
            item = response.get('Item')
            
            if item:
                # Decrypt sensitive data
                item = self._decrypt_sensitive_fields(item)
            
            return item
        except Exception as e:
            logger.error(f"Error retrieving profile {profile_id}: {str(e)}")
            return None
    
    def update_profile(self, profile_id: str, update_data: Dict[str, Any]) -> bool:
        """Update an existing user profile."""
        try:
            # First check if profile exists
            existing = self.get_profile(profile_id)
            if not existing:
                return False
            
            # Prepare update expression
            update_expression = "SET updated_at = :updated_at"
            expression_values = {
                ':updated_at': datetime.utcnow().isoformat()
            }
            
            # Add each field to update expression
            for key, value in update_data.items():
                if key not in ['profile_id', 'pk', 'sk', 'created_at']:
                    update_expression += f", {key} = :{key}"
                    
                    # Encrypt sensitive fields before storing
                    if self._is_sensitive_field(key):
                        expression_values[f':{key}'] = self._encrypt_value(value)
                    else:
                        expression_values[f':{key}'] = value
            
            # Perform update
            self.table.update_item(
                Key={
                    'pk': f"USER#{profile_id}",
                    'sk': "PROFILE#latest"
                },
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
            
            logger.info(f"Updated profile: {profile_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating profile {profile_id}: {str(e)}")
            return False
    
    def delete_profile(self, profile_id: str) -> bool:
        """Soft delete a user profile."""
        try:
            # Instead of hard deleting, update status to 'deleted'
            self.table.update_item(
                Key={
                    'pk': f"USER#{profile_id}",
                    'sk': "PROFILE#latest"
                },
                UpdateExpression="SET #status = :status, #updated_at = :updated_at",
                ExpressionAttributeNames={
                    '#status': 'status',
                    '#updated_at': 'updated_at'
                },
                ExpressionAttributeValues={
                    ':status': 'deleted',
                    ':updated_at': datetime.utcnow().isoformat()
                }
            )
            
            logger.info(f"Soft deleted profile: {profile_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting profile {profile_id}: {str(e)}")
            return False
    
    def get_profiles_by_phone(self, phone_number: str) -> List[Dict[str, Any]]:
        """Find profiles by phone number."""
        try:
            # Encrypt phone number for search
            encrypted_phone = self._encrypt_value(phone_number)
            
            # Scan table for matching phone numbers
            # In production, use GSI for better performance
            response = self.table.scan(
                FilterExpression=Attr('encrypted_phone_number').eq(encrypted_phone)
            )
            
            profiles = []
            for item in response['Items']:
                # Decrypt sensitive data
                decrypted_item = self._decrypt_sensitive_fields(item)
                profiles.append(decrypted_item)
            
            return profiles
        except Exception as e:
            logger.error(f"Error finding profiles by phone: {str(e)}")
            return []
    
    def list_profiles(self, limit: int = 50, last_evaluated_key: Optional[Dict] = None) -> Dict[str, Any]:
        """List all user profiles with pagination."""
        try:
            query_kwargs = {
                'IndexName': 'gsi1',  # Assuming we have a GSI on status
                'KeyConditionExpression': Key('sk').eq('PROFILE#latest'),
                'FilterExpression': Attr('status').eq('active'),
                'Limit': limit
            }
            
            if last_evaluated_key:
                query_kwargs['ExclusiveStartKey'] = last_evaluated_key
            
            response = self.table.query(**query_kwargs)
            
            profiles = []
            for item in response['Items']:
                # Decrypt sensitive data
                decrypted_item = self._decrypt_sensitive_fields(item)
                profiles.append(decrypted_item)
            
            result = {
                'profiles': profiles,
                'count': len(profiles)
            }
            
            if 'LastEvaluatedKey' in response:
                result['last_evaluated_key'] = response['LastEvaluatedKey']
            
            return result
        except Exception as e:
            logger.error(f"Error listing profiles: {str(e)}")
            return {'profiles': [], 'count': 0}
    
    def _is_sensitive_field(self, field_name: str) -> bool:
        """Check if a field contains sensitive information."""
        sensitive_fields = [
            'phone_number', 'email', 'aadhaar_hash', 'address', 
            'pan_number', 'bank_account', 'income', 'dob'
        ]
        return field_name in sensitive_fields
    
    def _encrypt_sensitive_fields(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive fields in profile data."""
        encrypted_data = profile_data.copy()
        
        for field, value in profile_data.items():
            if self._is_sensitive_field(field):
                encrypted_data[f'encrypted_{field}'] = self._encrypt_value(value)
                # Remove original field to avoid storing unencrypted data
                del encrypted_data[field]
        
        return encrypted_data
    
    def _decrypt_sensitive_fields(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt sensitive fields in profile data."""
        decrypted_data = profile_data.copy()
        
        # Find encrypted fields and decrypt them
        encrypted_fields = [key for key in profile_data.keys() if key.startswith('encrypted_')]
        
        for encrypted_field in encrypted_fields:
            original_field = encrypted_field.replace('encrypted_', '', 1)
            decrypted_data[original_field] = self._decrypt_value(profile_data[encrypted_field])
            # Remove encrypted field from result
            del decrypted_data[encrypted_field]
        
        return decrypted_data
    
    def _encrypt_value(self, value: Any) -> str:
        """Encrypt a value using KMS or similar."""
        # Placeholder for actual encryption
        # In a real implementation, this would use AWS KMS or similar
        import base64
        import json
        
        # Convert value to string and encode
        value_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        encoded = base64.b64encode(value_str.encode()).decode()
        
        # In production, encrypt with KMS:
        # encrypted = kms_client.encrypt(KeyId='alias/sahayak-pii-key', Plaintext=value_str)
        # return base64.b64encode(encrypted['CiphertextBlob']).decode()
        
        return f"encrypted_{encoded}"
    
    def _decrypt_value(self, encrypted_value: str) -> Any:
        """Decrypt an encrypted value."""
        # Placeholder for actual decryption
        # In a real implementation, this would use AWS KMS or similar
        
        if encrypted_value.startswith('encrypted_'):
            encoded = encrypted_value[10:]  # Remove 'encrypted_' prefix
            decoded = base64.b64decode(encoded.encode()).decode()
            
            # Try to parse as JSON, otherwise return as string
            try:
                return json.loads(decoded)
            except json.JSONDecodeError:
                return decoded
        
        # If not encrypted, return as-is
        return encrypted_value
    
    def get_profile_stats(self) -> Dict[str, Any]:
        """Get statistics about user profiles."""
        try:
            response = self.table.scan(
                Select='COUNT',
                FilterExpression=Attr('sk').eq('PROFILE#latest')
            )
            
            total_count = response['Count']
            
            # Count by status
            status_response = self.table.scan(
                ProjectionExpression='status',
                FilterExpression=Attr('sk').eq('PROFILE#latest')
            )
            
            status_counts = {}
            for item in status_response.get('Items', []):
                status = item.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Count by language preference
            lang_response = self.table.scan(
                ProjectionExpression='language_preference',
                FilterExpression=Attr('sk').eq('PROFILE#latest') &
                               Attr('language_preference').exists()
            )
            
            lang_counts = {}
            for item in lang_response.get('Items', []):
                lang = item.get('language_preference', 'unknown')
                lang_counts[lang] = lang_counts.get(lang, 0) + 1
            
            return {
                'total_profiles': total_count,
                'by_status': status_counts,
                'by_language': lang_counts
            }
        except Exception as e:
            logger.error(f"Error getting profile stats: {str(e)}")
            return {
                'total_profiles': 0,
                'by_status': {},
                'by_language': {}
            }
    
    def update_last_accessed(self, profile_id: str):
        """Update the last accessed timestamp for a profile."""
        try:
            self.table.update_item(
                Key={
                    'pk': f"USER#{profile_id}",
                    'sk': "PROFILE#latest"
                },
                UpdateExpression="SET last_accessed = :last_accessed",
                ExpressionAttributeValues={
                    ':last_accessed': datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Error updating last accessed for profile {profile_id}: {str(e)}")