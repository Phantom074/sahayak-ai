"""
Scheme Administration
Handles CRUD operations for government schemes in the database.
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

class SchemeAdmin:
    """Manages government scheme records in DynamoDB."""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        self.table_name = os.environ.get('SCHEMES_TABLE', 'sahayak-schemes-dev')
        self.table = self.dynamodb.Table(self.table_name)
        
    def create_scheme(self, scheme_data: Dict[str, Any]) -> str:
        """Create a new scheme record."""
        scheme_id = f"scheme_{uuid.uuid4().hex}"
        
        # Prepare scheme record
        scheme_record = {
            'scheme_id': scheme_id,
            'pk': f"SCHEME#{scheme_id}",
            'sk': "METADATA#latest",
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'version': 1,
            **scheme_data
        }
        
        # Add default fields if not present
        if 'status' not in scheme_record:
            scheme_record['status'] = 'active'
        if 'categories' not in scheme_record:
            scheme_record['categories'] = []
        if 'eligibility_criteria' not in scheme_record:
            scheme_record['eligibility_criteria'] = []
        if 'benefits' not in scheme_record:
            scheme_record['benefits'] = []
        if 'documents_required' not in scheme_record:
            scheme_record['documents_required'] = []
        
        # Insert into DynamoDB
        self.table.put_item(Item=scheme_record)
        
        logger.info(f"Created scheme: {scheme_id}")
        return scheme_id
    
    def get_scheme(self, scheme_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a scheme by ID."""
        try:
            response = self.table.get_item(
                Key={
                    'pk': f"SCHEME#{scheme_id}",
                    'sk': "METADATA#latest"
                }
            )
            return response.get('Item')
        except Exception as e:
            logger.error(f"Error retrieving scheme {scheme_id}: {str(e)}")
            return None
    
    def update_scheme(self, scheme_id: str, update_data: Dict[str, Any]) -> bool:
        """Update an existing scheme."""
        try:
            # First check if scheme exists
            existing = self.get_scheme(scheme_id)
            if not existing:
                return False
            
            # Prepare update expression
            update_expression = "SET updated_at = :updated_at"
            expression_values = {
                ':updated_at': datetime.utcnow().isoformat()
            }
            
            # Add each field to update expression
            for key, value in update_data.items():
                if key not in ['scheme_id', 'pk', 'sk', 'created_at']:
                    update_expression += f", {key} = :{key}"
                    expression_values[f':{key}'] = value
            
            # Perform update
            self.table.update_item(
                Key={
                    'pk': f"SCHEME#{scheme_id}",
                    'sk': "METADATA#latest"
                },
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
            
            logger.info(f"Updated scheme: {scheme_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating scheme {scheme_id}: {str(e)}")
            return False
    
    def delete_scheme(self, scheme_id: str) -> bool:
        """Delete a scheme record."""
        try:
            # Delete the scheme item
            self.table.delete_item(
                Key={
                    'pk': f"SCHEME#{scheme_id}",
                    'sk': "METADATA#latest"
                }
            )
            
            logger.info(f"Deleted scheme: {scheme_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting scheme {scheme_id}: {str(e)}")
            return False
    
    def list_schemes(self, limit: int = 50, last_evaluated_key: Optional[Dict] = None) -> Dict[str, Any]:
        """List all schemes with pagination."""
        try:
            query_kwargs = {
                'IndexName': 'gsi1',  # Assuming we have a GSI on status
                'KeyConditionExpression': Key('sk').eq('METADATA#latest'),
                'FilterExpression': Attr('status').eq('active'),
                'Limit': limit
            }
            
            if last_evaluated_key:
                query_kwargs['ExclusiveStartKey'] = last_evaluated_key
            
            response = self.table.query(**query_kwargs)
            
            schemes = [item for item in response['Items']]
            
            result = {
                'schemes': schemes,
                'count': len(schemes)
            }
            
            if 'LastEvaluatedKey' in response:
                result['last_evaluated_key'] = response['LastEvaluatedKey']
            
            return result
        except Exception as e:
            logger.error(f"Error listing schemes: {str(e)}")
            return {'schemes': [], 'count': 0}
    
    def search_schemes(self, query: str, category: Optional[str] = None, 
                      state: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Search schemes by text, category, or state."""
        try:
            # For full-text search, we'd typically use OpenSearch
            # This is a simplified version using DynamoDB scan
            # In production, use OpenSearch for better performance
            
            filter_expression = Attr('status').eq('active')
            
            if category:
                filter_expression &= Attr('categories').contains(category)
            
            if state:
                filter_expression &= (Attr('eligible_states').contains(state) | 
                                    Attr('eligible_states').contains('all'))
            
            response = self.table.scan(
                FilterExpression=filter_expression,
                Limit=limit
            )
            
            # Filter results by query text (case-insensitive)
            results = []
            query_lower = query.lower() if query else ""
            
            for item in response['Items']:
                # Check if query matches in relevant fields
                if not query or (
                    query_lower in item.get('scheme_name', '').lower() or
                    query_lower in item.get('description', '').lower() or
                    query_lower in ' '.join(item.get('benefits', [])).lower()
                ):
                    results.append(item)
            
            return results
        except Exception as e:
            logger.error(f"Error searching schemes: {str(e)}")
            return []
    
    def get_scheme_stats(self) -> Dict[str, Any]:
        """Get statistics about schemes."""
        try:
            response = self.table.scan(
                Select='COUNT',
                FilterExpression=Attr('sk').eq('METADATA#latest')
            )
            
            total_count = response['Count']
            
            # Count by status
            status_response = self.table.scan(
                ProjectionExpression='status',
                FilterExpression=Attr('sk').eq('METADATA#latest')
            )
            
            status_counts = {}
            for item in status_response.get('Items', []):
                status = item.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Count by category
            category_response = self.table.scan(
                ProjectionExpression='categories',
                FilterExpression=Attr('sk').eq('METADATA#latest') & 
                                Attr('categories').exists()
            )
            
            category_counts = {}
            for item in category_response.get('Items', []):
                for category in item.get('categories', []):
                    category_counts[category] = category_counts.get(category, 0) + 1
            
            return {
                'total_schemes': total_count,
                'by_status': status_counts,
                'by_category': category_counts
            }
        except Exception as e:
            logger.error(f"Error getting scheme stats: {str(e)}")
            return {
                'total_schemes': 0,
                'by_status': {},
                'by_category': {}
            }