#!/usr/bin/env python3
"""
Database Verification Script for lit_law411-agent
Verifies data presence and accessibility across Airtable, Supabase, and Pinecone
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Dict, Any, List
import json
import traceback

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from db.clients.airtable_client import AirtableClient
from db.clients.supabase_client import SupabaseClient
from db.clients.pinecone_client import PineconeClient
from db.clients.sync_manager import ThreeDatabaseSyncManager
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class DatabaseVerificationReport:
    """Generate comprehensive database status report."""
    
    def __init__(self):
        self.report = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'pending',
            'databases': {
                'airtable': {'status': 'pending', 'details': {}},
                'supabase': {'status': 'pending', 'details': {}},
                'pinecone': {'status': 'pending', 'details': {}}
            },
            'sync_status': {'status': 'pending', 'details': {}},
            'lit_master_integration': {'status': 'pending', 'details': {}},
            'recommendations': []
        }
    
    async def run_verification(self):
        """Run complete database verification."""
        try:
            logger.info("Starting comprehensive database verification")
            
            # Test individual database connections
            await self._verify_airtable()
            await self._verify_supabase()
            await self._verify_pinecone()
            
            # Test sync functionality
            await self._verify_sync_manager()
            
            # Test LIT_MASTER-AGENT integration points
            await self._verify_lit_master_integration()
            
            # Generate overall status
            self._calculate_overall_status()
            
            # Generate recommendations
            self._generate_recommendations()
            
            logger.info("Database verification completed")
            return self.report
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            self.report['overall_status'] = 'failed'
            self.report['error'] = str(e)
            return self.report
    
    async def _verify_airtable(self):
        """Verify Airtable connection and content."""
        try:
            logger.info("Verifying Airtable connection and content")
            
            client = AirtableClient()
            await client.connect()
            
            # Test connection
            tables = await client.list_tables()
            self.report['databases']['airtable']['details']['tables_found'] = len(tables)
            
            # Check for content table
            content_exists = any('content' in table.lower() for table in tables)
            self.report['databases']['airtable']['details']['content_table_exists'] = content_exists
            
            if content_exists:
                # Get content count
                content_records = await client.get_all_records('Content')
                content_count = len(content_records)
                self.report['databases']['airtable']['details']['content_count'] = content_count
                
                # Sample record analysis
                if content_count > 0:
                    sample_record = content_records[0]
                    self.report['databases']['airtable']['details']['sample_fields'] = list(sample_record.keys())
                    
                    # Check for required fields
                    required_fields = ['Content ID', 'Title', 'Source Type', 'Legal Relevance Score']
                    missing_fields = [field for field in required_fields if field not in sample_record]
                    self.report['databases']['airtable']['details']['missing_required_fields'] = missing_fields
            
            # Test write capability
            test_record = {
                'Content ID': f'test-{datetime.now().timestamp()}',
                'Title': 'Database Verification Test',
                'Source Type': 'test',
                'Content': 'This is a test record for database verification',
                'Legal Relevance Score': 0.5
            }
            
            try:
                created_record = await client.create_record('Content', test_record)
                self.report['databases']['airtable']['details']['write_test'] = 'success'
                
                # Clean up test record
                if created_record and 'id' in created_record:
                    await client.delete_record('Content', created_record['id'])
                    self.report['databases']['airtable']['details']['cleanup_test'] = 'success'
                    
            except Exception as e:
                self.report['databases']['airtable']['details']['write_test'] = f'failed: {str(e)}'
            
            self.report['databases']['airtable']['status'] = 'connected'
            logger.info("Airtable verification completed successfully")
            
        except Exception as e:
            logger.error(f"Airtable verification failed: {e}")
            self.report['databases']['airtable']['status'] = 'failed'
            self.report['databases']['airtable']['error'] = str(e)
    
    async def _verify_supabase(self):
        """Verify Supabase connection and content."""
        try:
            logger.info("Verifying Supabase connection and content")
            
            client = SupabaseClient()
            await client.connect()
            
            # Test connection with simple query
            health_check = await client.execute_query("SELECT NOW() as current_time")
            self.report['databases']['supabase']['details']['connection_test'] = 'success'
            self.report['databases']['supabase']['details']['server_time'] = health_check[0]['current_time'] if health_check else None
            
            # Check for content table
            table_check = await client.execute_query("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'content'
                ) as table_exists
            """)
            
            table_exists = table_check[0]['table_exists'] if table_check else False
            self.report['databases']['supabase']['details']['content_table_exists'] = table_exists
            
            if table_exists:
                # Get content statistics
                stats = await client.execute_query("""
                    SELECT 
                        COUNT(*) as total_content,
                        COUNT(*) FILTER (WHERE source_type = 'youtube') as youtube_content,
                        COUNT(*) FILTER (WHERE source_type = 'website') as website_content,
                        AVG(legal_relevance_score) as avg_legal_relevance,
                        MIN(processed_at) as earliest_content,
                        MAX(processed_at) as latest_content
                    FROM content
                """)
                
                if stats:
                    self.report['databases']['supabase']['details']['content_statistics'] = stats[0]
                
                # Check for NLP results
                nlp_check = await client.execute_query("""
                    SELECT COUNT(*) as records_with_nlp
                    FROM content 
                    WHERE nlp_results IS NOT NULL 
                    AND jsonb_array_length(nlp_results->'entities'->'named_entities') > 0
                """)
                
                if nlp_check:
                    self.report['databases']['supabase']['details']['nlp_processed_count'] = nlp_check[0]['records_with_nlp']
                
                # Sample legal entities
                entities_sample = await client.execute_query("""
                    SELECT DISTINCT entity->>'entity_type' as entity_type, COUNT(*) as count
                    FROM content, jsonb_array_elements(nlp_results->'entities'->'named_entities') as entity
                    GROUP BY entity->>'entity_type'
                    ORDER BY count DESC
                    LIMIT 10
                """)
                
                if entities_sample:
                    self.report['databases']['supabase']['details']['entity_types'] = entities_sample
            
            # Test write capability
            test_query = """
                INSERT INTO content (
                    content_id, source_type, source_url, title, content, 
                    legal_relevance_score, processed_at
                ) VALUES (
                    %s, 'test', 'https://test.com', 'Database Verification Test', 
                    'This is a test record for database verification', 0.5, NOW()
                ) RETURNING content_id
            """
            
            test_id = f'test-{datetime.now().timestamp()}'
            try:
                result = await client.execute_query(test_query, [test_id])
                self.report['databases']['supabase']['details']['write_test'] = 'success'
                
                # Clean up test record
                cleanup_query = "DELETE FROM content WHERE content_id = %s"
                await client.execute_query(cleanup_query, [test_id])
                self.report['databases']['supabase']['details']['cleanup_test'] = 'success'
                
            except Exception as e:
                self.report['databases']['supabase']['details']['write_test'] = f'failed: {str(e)}'
            
            self.report['databases']['supabase']['status'] = 'connected'
            logger.info("Supabase verification completed successfully")
            
        except Exception as e:
            logger.error(f"Supabase verification failed: {e}")
            self.report['databases']['supabase']['status'] = 'failed'
            self.report['databases']['supabase']['error'] = str(e)
    
    async def _verify_pinecone(self):
        """Verify Pinecone connection and content."""
        try:
            logger.info("Verifying Pinecone connection and content")
            
            client = PineconeClient()
            await client.connect()
            
            # Test connection and get index info
            index_info = await client.get_index_info()
            self.report['databases']['pinecone']['details']['index_info'] = index_info
            
            # Get vector count
            stats = await client.get_index_stats()
            self.report['databases']['pinecone']['details']['vector_stats'] = stats
            
            if stats and 'total_vector_count' in stats:
                vector_count = stats['total_vector_count']
                self.report['databases']['pinecone']['details']['total_vectors'] = vector_count
                
                if vector_count > 0:
                    # Test search functionality
                    test_vector = [0.1] * 3072  # text-embedding-3-large dimension
                    search_results = await client.search_vectors(
                        vector=test_vector,
                        top_k=5,
                        include_metadata=True
                    )
                    
                    self.report['databases']['pinecone']['details']['search_test'] = 'success'
                    self.report['databases']['pinecone']['details']['sample_results_count'] = len(search_results.get('matches', []))
                    
                    # Analyze metadata
                    if search_results.get('matches'):
                        sample_metadata = search_results['matches'][0].get('metadata', {})
                        self.report['databases']['pinecone']['details']['sample_metadata_fields'] = list(sample_metadata.keys())
            
            # Test write capability
            test_vector_id = f'test-{datetime.now().timestamp()}'
            test_vector = [0.1] * 3072
            test_metadata = {
                'content_id': test_vector_id,
                'source_type': 'test',
                'title': 'Database Verification Test'
            }
            
            try:
                await client.upsert_vectors([{
                    'id': test_vector_id,
                    'values': test_vector,
                    'metadata': test_metadata
                }])
                self.report['databases']['pinecone']['details']['write_test'] = 'success'
                
                # Clean up test vector
                await client.delete_vectors([test_vector_id])
                self.report['databases']['pinecone']['details']['cleanup_test'] = 'success'
                
            except Exception as e:
                self.report['databases']['pinecone']['details']['write_test'] = f'failed: {str(e)}'
            
            self.report['databases']['pinecone']['status'] = 'connected'
            logger.info("Pinecone verification completed successfully")
            
        except Exception as e:
            logger.error(f"Pinecone verification failed: {e}")
            self.report['databases']['pinecone']['status'] = 'failed'
            self.report['databases']['pinecone']['error'] = str(e)
    
    async def _verify_sync_manager(self):
        """Verify three-database sync functionality."""
        try:
            logger.info("Verifying sync manager functionality")
            
            sync_manager = ThreeDatabaseSyncManager()
            
            # Test sync manager initialization
            self.report['sync_status']['details']['initialization'] = 'success'
            
            # Test health check across all databases
            health_status = await sync_manager.health_check()
            self.report['sync_status']['details']['health_check'] = health_status
            
            # Test consistency check if data exists
            try:
                consistency_report = await sync_manager.check_consistency()
                self.report['sync_status']['details']['consistency_check'] = consistency_report
            except Exception as e:
                self.report['sync_status']['details']['consistency_check'] = f'failed: {str(e)}'
            
            self.report['sync_status']['status'] = 'operational'
            logger.info("Sync manager verification completed successfully")
            
        except Exception as e:
            logger.error(f"Sync manager verification failed: {e}")
            self.report['sync_status']['status'] = 'failed'
            self.report['sync_status']['error'] = str(e)
    
    async def _verify_lit_master_integration(self):
        """Verify LIT_MASTER-AGENT integration readiness."""
        try:
            logger.info("Verifying LIT_MASTER-AGENT integration readiness")
            
            integration_details = {}
            
            # Check if we have processable content
            supabase_client = SupabaseClient()
            
            # Get content suitable for legal research
            legal_content_query = """
                SELECT 
                    COUNT(*) as total_legal_content,
                    COUNT(*) FILTER (WHERE legal_relevance_score > 0.5) as high_relevance_content,
                    COUNT(*) FILTER (WHERE nlp_results->'entities'->'virginia_statutes' IS NOT NULL) as virginia_statute_content,
                    COUNT(*) FILTER (WHERE nlp_results->'entities'->'case_citations' IS NOT NULL) as case_citation_content,
                    COUNT(*) FILTER (WHERE nlp_results->'classification'->>'practice_area' = 'family_law') as family_law_content
                FROM content
                WHERE legal_relevance_score > 0.1
            """
            
            try:
                legal_stats = await supabase_client.execute_query(legal_content_query)
                if legal_stats:
                    integration_details['legal_content_statistics'] = legal_stats[0]
            except Exception as e:
                integration_details['legal_content_query_error'] = str(e)
            
            # Check search functionality for LIT_MASTER-AGENT
            search_test_queries = [
                "Virginia Code family law",
                "custody procedures",
                "divorce motions",
                "child support guidelines"
            ]
            
            search_results = {}
            for query in search_test_queries:
                try:
                    # Test keyword search
                    keyword_query = """
                        SELECT COUNT(*) as result_count
                        FROM content 
                        WHERE to_tsvector('english', content || ' ' || COALESCE(title, '')) 
                              @@ plainto_tsquery('english', %s)
                        AND legal_relevance_score > 0.3
                    """
                    
                    result = await supabase_client.execute_query(keyword_query, [query])
                    if result:
                        search_results[query] = result[0]['result_count']
                except Exception as e:
                    search_results[query] = f'error: {str(e)}'
            
            integration_details['search_test_results'] = search_results
            
            # Check API endpoints availability
            api_endpoints = [
                '/api/v1/search/content',
                '/api/v1/search/entities/VIRGINIA_CODE',
                '/api/v1/search/entities/CASE_CITATION',
                '/api/v1/search/suggestions',
                '/api/v1/search/stats'
            ]
            
            integration_details['available_api_endpoints'] = api_endpoints
            
            # Check entity extraction capabilities
            entity_types_query = """
                SELECT DISTINCT entity->>'entity_type' as entity_type, COUNT(*) as count
                FROM content, jsonb_array_elements(nlp_results->'entities'->'named_entities') as entity
                WHERE entity->>'entity_type' IN ('VIRGINIA_CODE', 'CASE_CITATION', 'COURT', 'FAMILY_LAW')
                GROUP BY entity->>'entity_type'
                ORDER BY count DESC
            """
            
            try:
                entity_types = await supabase_client.execute_query(entity_types_query)
                integration_details['available_entity_types'] = entity_types
            except Exception as e:
                integration_details['entity_types_error'] = str(e)
            
            # Check Virginia-specific content
            virginia_content_query = """
                SELECT COUNT(*) as virginia_content_count
                FROM content 
                WHERE (
                    LOWER(content) LIKE '%virginia%' OR 
                    LOWER(title) LIKE '%virginia%' OR
                    nlp_results->'classification'->>'virginia_relevance' IS NOT NULL
                ) AND legal_relevance_score > 0.3
            """
            
            try:
                virginia_stats = await supabase_client.execute_query(virginia_content_query)
                if virginia_stats:
                    integration_details['virginia_specific_content'] = virginia_stats[0]['virginia_content_count']
            except Exception as e:
                integration_details['virginia_content_error'] = str(e)
            
            self.report['lit_master_integration']['details'] = integration_details
            self.report['lit_master_integration']['status'] = 'ready'
            
            logger.info("LIT_MASTER-AGENT integration verification completed")
            
        except Exception as e:
            logger.error(f"LIT_MASTER-AGENT integration verification failed: {e}")
            self.report['lit_master_integration']['status'] = 'failed'
            self.report['lit_master_integration']['error'] = str(e)
    
    def _calculate_overall_status(self):
        """Calculate overall system status."""
        database_statuses = [
            self.report['databases']['airtable']['status'],
            self.report['databases']['supabase']['status'],
            self.report['databases']['pinecone']['status']
        ]
        
        sync_status = self.report['sync_status']['status']
        integration_status = self.report['lit_master_integration']['status']
        
        if all(status == 'connected' for status in database_statuses) and \
           sync_status == 'operational' and integration_status == 'ready':
            self.report['overall_status'] = 'fully_operational'
        elif any(status == 'connected' for status in database_statuses):
            self.report['overall_status'] = 'partially_operational'
        else:
            self.report['overall_status'] = 'not_operational'
    
    def _generate_recommendations(self):
        """Generate recommendations based on verification results."""
        recommendations = []
        
        # Check database connections
        for db_name, db_info in self.report['databases'].items():
            if db_info['status'] != 'connected':
                recommendations.append({
                    'priority': 'high',
                    'category': 'database_connection',
                    'issue': f'{db_name.title()} database not connected',
                    'recommendation': f'Check {db_name} configuration and network connectivity'
                })
        
        # Check content availability
        supabase_details = self.report['databases']['supabase']['details']
        if 'content_statistics' in supabase_details:
            stats = supabase_details['content_statistics']
            if stats.get('total_content', 0) == 0:
                recommendations.append({
                    'priority': 'high',
                    'category': 'content_availability',
                    'issue': 'No content found in databases',
                    'recommendation': 'Run content ingestion pipeline to populate databases with Virginia legal content'
                })
            elif stats.get('total_content', 0) < 10:
                recommendations.append({
                    'priority': 'medium',
                    'category': 'content_volume',
                    'issue': 'Low content volume',
                    'recommendation': 'Consider running additional content ingestion to increase knowledge base size'
                })
        
        # Check LIT_MASTER integration readiness
        integration_details = self.report['lit_master_integration']['details']
        if 'legal_content_statistics' in integration_details:
            legal_stats = integration_details['legal_content_statistics']
            if legal_stats.get('high_relevance_content', 0) < 5:
                recommendations.append({
                    'priority': 'medium',
                    'category': 'content_quality',
                    'issue': 'Low high-relevance legal content',
                    'recommendation': 'Focus content ingestion on high-quality Virginia legal sources'
                })
        
        # Check search functionality
        if 'search_test_results' in integration_details:
            search_results = integration_details['search_test_results']
            failed_searches = [query for query, result in search_results.items() 
                             if isinstance(result, str) and 'error' in result]
            if failed_searches:
                recommendations.append({
                    'priority': 'high',
                    'category': 'search_functionality',
                    'issue': 'Search functionality errors detected',
                    'recommendation': 'Debug search indexing and query processing'
                })
        
        self.report['recommendations'] = recommendations


async def main():
    """Main verification function."""
    print("🔍 Starting Database Verification for lit_law411-agent")
    print("=" * 60)
    
    verifier = DatabaseVerificationReport()
    report = await verifier.run_verification()
    
    # Print summary
    print(f"\n📊 VERIFICATION SUMMARY")
    print(f"Timestamp: {report['timestamp']}")
    print(f"Overall Status: {report['overall_status'].upper()}")
    print()
    
    # Database status
    print("📁 DATABASE STATUS:")
    for db_name, db_info in report['databases'].items():
        status_emoji = "✅" if db_info['status'] == 'connected' else "❌"
        print(f"  {status_emoji} {db_name.title()}: {db_info['status']}")
        
        if 'error' in db_info:
            print(f"      Error: {db_info['error']}")
        
        # Key details
        details = db_info.get('details', {})
        if db_name == 'supabase' and 'content_statistics' in details:
            stats = details['content_statistics']
            print(f"      Content: {stats.get('total_content', 0)} total records")
            print(f"      YouTube: {stats.get('youtube_content', 0)} videos")
            print(f"      Websites: {stats.get('website_content', 0)} pages")
        
        if db_name == 'pinecone' and 'total_vectors' in details:
            print(f"      Vectors: {details['total_vectors']} embeddings")
        
        if db_name == 'airtable' and 'content_count' in details:
            print(f"      Records: {details['content_count']} in Airtable")
    
    print()
    
    # Sync status
    sync_emoji = "✅" if report['sync_status']['status'] == 'operational' else "❌"
    print(f"🔄 SYNC STATUS: {sync_emoji} {report['sync_status']['status']}")
    
    # LIT_MASTER integration
    integration_emoji = "✅" if report['lit_master_integration']['status'] == 'ready' else "❌"
    print(f"🤖 LIT_MASTER INTEGRATION: {integration_emoji} {report['lit_master_integration']['status']}")
    
    # Integration details
    if 'legal_content_statistics' in report['lit_master_integration']['details']:
        legal_stats = report['lit_master_integration']['details']['legal_content_statistics']
        print(f"      Legal Content: {legal_stats.get('total_legal_content', 0)} documents")
        print(f"      High Relevance: {legal_stats.get('high_relevance_content', 0)} documents")
        print(f"      Virginia Statutes: {legal_stats.get('virginia_statute_content', 0)} references")
        print(f"      Family Law: {legal_stats.get('family_law_content', 0)} documents")
    
    print()
    
    # Recommendations
    if report['recommendations']:
        print("💡 RECOMMENDATIONS:")
        for rec in report['recommendations']:
            priority_emoji = "🔴" if rec['priority'] == 'high' else "🟡"
            print(f"  {priority_emoji} {rec['issue']}")
            print(f"      → {rec['recommendation']}")
        print()
    
    # Save detailed report
    report_file = f"/Users/branchechols/dev/lit_law411-agent/database_verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"📄 Detailed report saved to: {report_file}")
    
    # Return status for script
    if report['overall_status'] == 'fully_operational':
        print("\n🎉 ALL SYSTEMS OPERATIONAL - Ready for LIT_MASTER-AGENT integration!")
        return 0
    elif report['overall_status'] == 'partially_operational':
        print("\n⚠️  PARTIAL FUNCTIONALITY - Some issues need attention")
        return 1
    else:
        print("\n❌ SYSTEM NOT OPERATIONAL - Critical issues need resolution")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)