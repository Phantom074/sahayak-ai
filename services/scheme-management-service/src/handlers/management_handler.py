"""
Scheme Management Handler
API endpoints for scheme administration, ingestion, and updates.
"""

import json
import logging
import os
from typing import Dict, Any, Optional

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent

from ..ingestion.document_ingester import DocumentIngester
from ..admin.scheme_admin import SchemeAdmin

logger = Logger()
tracer = Tracer()

class SchemeManagementHandler:
    """Handles scheme management operations."""
    
    def __init__(self):
        self.admin = SchemeAdmin()
        self.ingester = DocumentIngester()
    
    @tracer.capture_method
    def create_scheme(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new government scheme."""
        try:
            body = json.loads(event.get('body', '{}')) if event.get('body') else {}
            
            # Validate required fields
            required_fields = ['scheme_name', 'description', 'benefits']
            for field in required_fields:
                if field not in body:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({
                            'error': f'Missing required field: {field}',
                            'message_hi': f'आवश्यक फ़ील्ड गुम: {field}'
                        })
                    }
            
            # Create scheme
            scheme_id = self.admin.create_scheme(body)
            
            return {
                'statusCode': 201,
                'body': json.dumps({
                    'scheme_id': scheme_id,
                    'message': 'Scheme created successfully',
                    'message_hi': 'योजना सफलतापूर्वक बनाई गई'
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
            logger.exception(f"Error creating scheme: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Internal server error',
                    'message': str(e),
                    'message_hi': 'आंतरिक सर्वर त्रुटि'
                })
            }
    
    @tracer.capture_method
    def update_scheme(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing government scheme."""
        try:
            scheme_id = event['pathParameters']['scheme_id']
            body = json.loads(event.get('body', '{}')) if event.get('body') else {}
            
            # Update scheme
            success = self.admin.update_scheme(scheme_id, body)
            
            if not success:
                return {
                    'statusCode': 404,
                    'body': json.dumps({
                        'error': 'Scheme not found',
                        'message_hi': 'योजना नहीं मिली'
                    })
                }
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'scheme_id': scheme_id,
                    'message': 'Scheme updated successfully',
                    'message_hi': 'योजना सफलतापूर्वक अपडेट की गई'
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
                    'error': 'Missing scheme_id in path',
                    'message_hi': 'पथ में scheme_id गुम'
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
            logger.exception(f"Error updating scheme: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Internal server error',
                    'message': str(e),
                    'message_hi': 'आंतरिक सर्वर त्रुटि'
                })
            }
    
    @tracer.capture_method
    def delete_scheme(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a government scheme."""
        try:
            scheme_id = event['pathParameters']['scheme_id']
            
            # Delete scheme
            success = self.admin.delete_scheme(scheme_id)
            
            if not success:
                return {
                    'statusCode': 404,
                    'body': json.dumps({
                        'error': 'Scheme not found',
                        'message_hi': 'योजना नहीं मिली'
                    })
                }
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'scheme_id': scheme_id,
                    'message': 'Scheme deleted successfully',
                    'message_hi': 'योजना सफलतापूर्वक हटा दी गई'
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
                    'error': 'Missing scheme_id in path',
                    'message_hi': 'पथ में scheme_id गुम'
                })
            }
        except Exception as e:
            logger.exception(f"Error deleting scheme: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Internal server error',
                    'message': str(e),
                    'message_hi': 'आंतरिक सर्वर त्रुटि'
                })
            }
    
    @tracer.capture_method
    def ingest_documents(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Ingest scheme documents for search/indexing."""
        try:
            body = json.loads(event.get('body', '{}')) if event.get('body') else {}
            scheme_id = body.get('scheme_id')
            document_urls = body.get('document_urls', [])
            
            if not scheme_id:
                return {
                    'statusCode': 400,
                    'body': json.dumps({
                        'error': 'Missing scheme_id',
                        'message_hi': 'scheme_id गुम'
                    })
                }
            
            if not document_urls:
                return {
                    'statusCode': 400,
                    'body': json.dumps({
                        'error': 'Missing document_urls',
                        'message_hi': 'document_urls गुम'
                    })
                }
            
            # Process documents
            results = self.ingester.ingest_documents(scheme_id, document_urls)
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'scheme_id': scheme_id,
                    'documents_processed': len(document_urls),
                    'results': results,
                    'message': 'Documents ingested successfully',
                    'message_hi': 'दस्तावेज़ सफलतापूर्वक संसाधित'
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
            logger.exception(f"Error ingesting documents: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Internal server error during document ingestion',
                    'message': str(e),
                    'message_hi': 'दस्तावेज़ संसाधन के दौरान आंतरिक त्रुटि'
                })
            }


def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda entry point for scheme management."""
    handler = SchemeManagementHandler()
    
    # Extract HTTP method and path
    http_method = event.get('httpMethod', '').upper()
    resource_path = event.get('resource', '')
    
    try:
        if resource_path == '/schemes' and http_method == 'POST':
            return handler.create_scheme(event)
        elif resource_path == '/schemes/{scheme_id}' and http_method == 'PUT':
            return handler.update_scheme(event)
        elif resource_path == '/schemes/{scheme_id}' and http_method == 'DELETE':
            return handler.delete_scheme(event)
        elif resource_path == '/schemes/ingest' and http_method == 'POST':
            return handler.ingest_documents(event)
        else:
            return {
                'statusCode': 404,
                'body': json.dumps({
                    'error': 'Resource not found',
                    'message_hi': 'संसाधन नहीं मिला'
                })
            }
    except Exception as e:
        logger.exception(f"Unhandled error in scheme management handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e),
                'message_hi': 'आंतरिक सर्वर त्रुटि'
            })
        }