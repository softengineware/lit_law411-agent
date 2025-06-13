"""Search API endpoints for legal knowledge base."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
import structlog

from src.core.auth import get_current_active_user
from src.models.pydantic.auth import User
from src.db.clients.sync_manager import ThreeDatabaseSyncManager
from src.db.clients.pinecone_client import PineconeClient
from src.db.clients.supabase_client import SupabaseClient
from src.processors.embeddings import LegalEmbeddingService

logger = structlog.get_logger()

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    """Request model for content search."""
    query: str = Field(..., min_length=1, max_length=500)
    search_type: str = Field(default="hybrid", pattern="^(keyword|semantic|hybrid|entity)$")
    content_types: Optional[List[str]] = Field(default=None, description="Filter by content type: youtube, website")
    sources: Optional[List[str]] = Field(default=None, description="Filter by specific sources")
    date_from: Optional[str] = Field(default=None, description="ISO format date")
    date_to: Optional[str] = Field(default=None, description="ISO format date")
    legal_topics: Optional[List[str]] = Field(default=None, description="Filter by legal topics")
    min_relevance_score: Optional[float] = Field(default=0.1, ge=0.0, le=1.0)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SearchResult(BaseModel):
    """Individual search result."""
    content_id: str
    title: Optional[str]
    source_type: str
    source_url: str
    content_snippet: str
    relevance_score: float
    legal_relevance_score: float
    legal_entities: List[Dict[str, Any]]
    topics: List[str]
    published_date: Optional[str]
    processed_date: str


class SearchResponse(BaseModel):
    """Search response with results and metadata."""
    query: str
    search_type: str
    total_results: int
    results: List[SearchResult]
    search_time_ms: int
    filters_applied: Dict[str, Any]
    aggregations: Optional[Dict[str, Any]] = None


class EntitySearchRequest(BaseModel):
    """Request model for legal entity search."""
    entity_type: str = Field(..., description="Type of legal entity to search for")
    entity_text: str = Field(..., min_length=1, description="Entity text to search")
    context_required: bool = Field(default=True, description="Include context around entity")


class LegalSearchService:
    """Service for searching legal content across databases."""
    
    def __init__(self):
        self.sync_manager = ThreeDatabaseSyncManager()
        self.pinecone_client = PineconeClient()
        self.supabase_client = SupabaseClient()
        self.embedding_service = LegalEmbeddingService()
    
    async def search_content(self, request: SearchRequest, user_id: str) -> SearchResponse:
        """Search content using specified method."""
        import time
        start_time = time.time()
        
        try:
            if request.search_type == "keyword":
                results = await self._keyword_search(request)
            elif request.search_type == "semantic":
                results = await self._semantic_search(request)
            elif request.search_type == "hybrid":
                results = await self._hybrid_search(request)
            elif request.search_type == "entity":
                results = await self._entity_search(request)
            else:
                raise ValueError(f"Unsupported search type: {request.search_type}")
            
            # Apply filters
            filtered_results = self._apply_filters(results, request)
            
            # Apply pagination
            paginated_results = filtered_results[request.offset:request.offset + request.limit]
            
            search_time = int((time.time() - start_time) * 1000)
            
            return SearchResponse(
                query=request.query,
                search_type=request.search_type,
                total_results=len(filtered_results),
                results=paginated_results,
                search_time_ms=search_time,
                filters_applied=self._get_applied_filters(request)
            )
            
        except Exception as e:
            logger.error("Search failed", query=request.query, error=str(e))
            raise
    
    async def _keyword_search(self, request: SearchRequest) -> List[SearchResult]:
        """Perform keyword-based search using Supabase."""
        # Use Supabase full-text search
        search_query = f"""
        SELECT 
            content_id, title, source_type, source_url, content,
            legal_relevance_score, nlp_results, processed_at
        FROM content 
        WHERE to_tsvector('english', content || ' ' || COALESCE(title, '')) 
              @@ plainto_tsquery('english', %s)
        ORDER BY ts_rank(to_tsvector('english', content), plainto_tsquery('english', %s)) DESC
        """
        
        results = await self.supabase_client.execute_query(search_query, [request.query, request.query])
        return self._format_search_results(results)
    
    async def _semantic_search(self, request: SearchRequest) -> List[SearchResult]:
        """Perform semantic search using Pinecone."""
        # Generate query embedding
        embedding_result = await self.embedding_service.generate_embedding(request.query)
        query_vector = embedding_result.embedding
        
        # Search in Pinecone
        search_results = await self.pinecone_client.search_vectors(
            vector=query_vector,
            top_k=request.limit * 2,  # Get more results for filtering
            include_metadata=True
        )
        
        # Get full content from Supabase for matching IDs
        content_ids = [match["id"] for match in search_results["matches"]]
        if not content_ids:
            return []
        
        content_query = """
        SELECT content_id, title, source_type, source_url, content,
               legal_relevance_score, nlp_results, processed_at
        FROM content 
        WHERE content_id = ANY(%s)
        """
        
        content_results = await self.supabase_client.execute_query(content_query, [content_ids])
        
        # Merge with semantic scores
        results_with_scores = []
        score_map = {match["id"]: match["score"] for match in search_results["matches"]}
        
        for content in content_results:
            content["semantic_score"] = score_map.get(content["content_id"], 0.0)
            results_with_scores.append(content)
        
        # Sort by semantic score
        results_with_scores.sort(key=lambda x: x["semantic_score"], reverse=True)
        
        return self._format_search_results(results_with_scores)
    
    async def _hybrid_search(self, request: SearchRequest) -> List[SearchResult]:
        """Combine keyword and semantic search with weighted scoring."""
        # Get both keyword and semantic results
        keyword_results = await self._keyword_search(request)
        semantic_results = await self._semantic_search(request)
        
        # Combine and weight scores
        combined_results = {}
        
        # Add keyword results (weight: 0.4)
        for result in keyword_results:
            content_id = result.content_id
            combined_results[content_id] = result
            combined_results[content_id].relevance_score = result.relevance_score * 0.4
        
        # Add semantic results (weight: 0.6)
        for result in semantic_results:
            content_id = result.content_id
            if content_id in combined_results:
                # Combine scores
                combined_results[content_id].relevance_score += result.relevance_score * 0.6
            else:
                combined_results[content_id] = result
                combined_results[content_id].relevance_score = result.relevance_score * 0.6
        
        # Sort by combined score
        final_results = list(combined_results.values())
        final_results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return final_results
    
    async def _entity_search(self, request: SearchRequest) -> List[SearchResult]:
        """Search for specific legal entities."""
        # Search for content containing specific legal entities
        entity_query = """
        SELECT DISTINCT c.content_id, c.title, c.source_type, c.source_url, c.content,
               c.legal_relevance_score, c.nlp_results, c.processed_at
        FROM content c, jsonb_array_elements(c.nlp_results->'entities'->'named_entities') as entity
        WHERE LOWER(entity->>'text') LIKE LOWER(%s)
           OR LOWER(entity->>'normalized_form') LIKE LOWER(%s)
        ORDER BY c.legal_relevance_score DESC
        """
        
        search_pattern = f"%{request.query}%"
        results = await self.supabase_client.execute_query(
            entity_query, [search_pattern, search_pattern]
        )
        
        return self._format_search_results(results)
    
    def _format_search_results(self, db_results: List[Dict]) -> List[SearchResult]:
        """Format database results into SearchResult objects."""
        search_results = []
        
        for result in db_results:
            # Extract content snippet
            content = result.get("content", "")
            snippet = content[:300] + "..." if len(content) > 300 else content
            
            # Extract legal entities
            nlp_results = result.get("nlp_results", {})
            entities = nlp_results.get("entities", {}).get("named_entities", [])
            
            # Extract topics
            topics = nlp_results.get("topics", [])
            
            search_result = SearchResult(
                content_id=result["content_id"],
                title=result.get("title"),
                source_type=result["source_type"],
                source_url=result["source_url"],
                content_snippet=snippet,
                relevance_score=result.get("semantic_score", result.get("legal_relevance_score", 0.0)),
                legal_relevance_score=result.get("legal_relevance_score", 0.0),
                legal_entities=entities,
                topics=topics,
                published_date=result.get("published_date"),
                processed_date=result["processed_at"]
            )
            
            search_results.append(search_result)
        
        return search_results
    
    def _apply_filters(self, results: List[SearchResult], request: SearchRequest) -> List[SearchResult]:
        """Apply filters to search results."""
        filtered = results
        
        # Filter by content types
        if request.content_types:
            filtered = [r for r in filtered if r.source_type in request.content_types]
        
        # Filter by minimum relevance score
        if request.min_relevance_score:
            filtered = [r for r in filtered if r.legal_relevance_score >= request.min_relevance_score]
        
        # Filter by legal topics
        if request.legal_topics:
            filtered = [r for r in filtered if any(topic in r.topics for topic in request.legal_topics)]
        
        # Filter by date range (if provided)
        if request.date_from or request.date_to:
            # Implementation would filter by published_date or processed_date
            pass
        
        return filtered
    
    def _get_applied_filters(self, request: SearchRequest) -> Dict[str, Any]:
        """Get summary of applied filters."""
        filters = {}
        
        if request.content_types:
            filters["content_types"] = request.content_types
        if request.min_relevance_score:
            filters["min_relevance_score"] = request.min_relevance_score
        if request.legal_topics:
            filters["legal_topics"] = request.legal_topics
        if request.date_from:
            filters["date_from"] = request.date_from
        if request.date_to:
            filters["date_to"] = request.date_to
        
        return filters


# Initialize search service
search_service = LegalSearchService()


@router.post("/content", response_model=SearchResponse)
async def search_content(
    request: SearchRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Search legal content across the knowledge base.
    
    Supports multiple search types:
    - keyword: Traditional text search
    - semantic: AI-powered semantic search
    - hybrid: Combination of keyword and semantic (recommended)
    - entity: Search for specific legal entities
    """
    try:
        logger.info("Content search requested", 
                   query=request.query, 
                   search_type=request.search_type,
                   user_id=current_user.id)
        
        results = await search_service.search_content(request, current_user.id)
        
        logger.info("Content search completed",
                   query=request.query,
                   results_count=results.total_results,
                   search_time=results.search_time_ms)
        
        return results
        
    except Exception as e:
        logger.error("Content search failed", query=request.query, error=str(e))
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/entities/{entity_type}")
async def search_by_entity_type(
    entity_type: str,
    query: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user)
):
    """Search for content containing specific types of legal entities."""
    try:
        search_request = SearchRequest(
            query=query,
            search_type="entity",
            limit=limit
        )
        
        results = await search_service.search_content(search_request, current_user.id)
        
        # Filter results to only include the specified entity type
        filtered_results = []
        for result in results.results:
            matching_entities = [
                entity for entity in result.legal_entities 
                if entity.get("entity_type", "").lower() == entity_type.lower()
            ]
            if matching_entities:
                result.legal_entities = matching_entities
                filtered_results.append(result)
        
        results.results = filtered_results
        results.total_results = len(filtered_results)
        
        return results
        
    except Exception as e:
        logger.error("Entity search failed", entity_type=entity_type, query=query, error=str(e))
        raise HTTPException(status_code=500, detail=f"Entity search failed: {str(e)}")


@router.get("/suggestions")
async def get_search_suggestions(
    query: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=20),
    current_user: User = Depends(get_current_active_user)
):
    """Get search suggestions based on legal entities and common terms."""
    try:
        # Get common legal entities that match the query
        entity_query = """
        SELECT DISTINCT entity->>'text' as entity_text, 
               entity->>'entity_type' as entity_type,
               COUNT(*) as frequency
        FROM content, jsonb_array_elements(nlp_results->'entities'->'named_entities') as entity
        WHERE LOWER(entity->>'text') LIKE LOWER(%s)
        GROUP BY entity->>'text', entity->>'entity_type'
        ORDER BY frequency DESC, entity->>'text'
        LIMIT %s
        """
        
        supabase_client = SupabaseClient()
        suggestions = await supabase_client.execute_query(
            entity_query, [f"%{query}%", limit]
        )
        
        return {
            "query": query,
            "suggestions": [
                {
                    "text": suggestion["entity_text"],
                    "type": suggestion["entity_type"],
                    "frequency": suggestion["frequency"]
                }
                for suggestion in suggestions
            ]
        }
        
    except Exception as e:
        logger.error("Search suggestions failed", query=query, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get suggestions: {str(e)}")


@router.get("/stats")
async def get_search_stats(
    current_user: User = Depends(get_current_active_user)
):
    """Get search and content statistics."""
    try:
        supabase_client = SupabaseClient()
        
        # Get content statistics
        stats_query = """
        SELECT 
            COUNT(*) as total_content,
            COUNT(*) FILTER (WHERE source_type = 'youtube') as youtube_content,
            COUNT(*) FILTER (WHERE source_type = 'website') as website_content,
            AVG(legal_relevance_score) as avg_legal_relevance,
            COUNT(DISTINCT source_url) as unique_sources
        FROM content
        """
        
        stats = await supabase_client.execute_query(stats_query)
        
        if stats:
            return {
                "content_statistics": stats[0],
                "search_capabilities": {
                    "search_types": ["keyword", "semantic", "hybrid", "entity"],
                    "supported_entity_types": [
                        "VIRGINIA_CODE", "CASE_CITATION", "COURT", 
                        "FAMILY_LAW", "PERSON", "ORG", "DATE"
                    ],
                    "content_types": ["youtube", "website"]
                }
            }
        else:
            return {"error": "No statistics available"}
        
    except Exception as e:
        logger.error("Failed to get search stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")