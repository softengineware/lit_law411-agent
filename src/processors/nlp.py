"""
Legal NLP processing for entity extraction and content classification.

This module provides comprehensive NLP capabilities for legal content,
including Virginia law statutes, case citations, and family law concepts.
"""

import re
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from pathlib import Path

import spacy
from spacy.matcher import Matcher
from spacy.lang.en import English
import structlog

from ..core.config import settings
from ..core.logging import get_logger
from ..utils.performance_decorators import monitor_performance

logger = get_logger(__name__)


@dataclass
class LegalEntity:
    """Represents a legal entity extracted from text."""
    entity_type: str
    text: str
    start_pos: int
    end_pos: int
    confidence: float
    context: str
    normalized_form: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class VirginiaStatute:
    """Virginia Code statute reference."""
    title: str
    section: str
    subsection: Optional[str] = None
    full_citation: str = ""
    description: Optional[str] = None


@dataclass
class CaseCitation:
    """Legal case citation."""
    case_name: str
    reporter: Optional[str] = None
    volume: Optional[str] = None
    page: Optional[str] = None
    year: Optional[str] = None
    court: Optional[str] = None
    full_citation: str = ""


@dataclass
class LegalConcept:
    """Family law or legal concept."""
    concept: str
    category: str  # custody, support, divorce, procedure, etc.
    confidence: float
    context: str


@dataclass
class NLPResults:
    """Results of NLP processing."""
    virginia_statutes: List[VirginiaStatute]
    case_citations: List[CaseCitation]
    legal_concepts: List[LegalConcept]
    entities: List[LegalEntity]
    topics: List[str]
    confidence_score: float
    processing_time_seconds: float


class VirginiaLegalNLP:
    """NLP processor specialized for Virginia legal content."""
    
    def __init__(self):
        self.nlp = None
        self.matcher = None
        self._initialize_patterns()
        
        # Virginia-specific legal terms
        self.virginia_courts = {
            'virginia supreme court', 'supreme court of virginia',
            'virginia circuit court', 'circuit court',
            'virginia district court', 'district court',
            'virginia court of appeals', 'court of appeals',
            'fairfax circuit court', 'henrico circuit court',
            'chesterfield circuit court', 'loudoun circuit court'
        }
        
        self.family_law_terms = {
            'divorce', 'custody', 'child custody', 'visitation',
            'child support', 'spousal support', 'alimony',
            'equitable distribution', 'property division',
            'marital property', 'separate property',
            'guardian ad litem', 'pendente lite',
            'best interests of the child', 'parenting plan',
            'supervised visitation', 'contempt of court'
        }
        
        self.legal_procedures = {
            'motion', 'petition', 'complaint', 'answer',
            'discovery', 'deposition', 'interrogatories',
            'subpoena', 'hearing', 'trial', 'settlement',
            'mediation', 'arbitration', 'appeal'
        }
    
    async def initialize(self):
        """Initialize spaCy model and patterns."""
        try:
            # Load spaCy model
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("en_core_web_sm not found, using basic English model")
                self.nlp = English()
            
            # Initialize matcher with patterns
            self.matcher = Matcher(self.nlp.vocab)
            self._add_legal_patterns()
            
            logger.info("Virginia Legal NLP initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize NLP model: {e}")
            raise
    
    def _initialize_patterns(self):
        """Initialize regex patterns for legal entity extraction."""
        # Virginia Code patterns
        self.va_code_patterns = [
            r'(?:Virginia\s+)?Code\s+(?:§|Section)\s*(\d+(?:\.\d+)*[A-Z]?-\d+(?:\.\d+)*)',
            r'(?:Va\.?\s+)?Code\s+(?:Ann\.?\s+)?(?:§|Section)\s*(\d+(?:\.\d+)*[A-Z]?-\d+(?:\.\d+)*)',
            r'(?:§|Section)\s*(\d+(?:\.\d+)*[A-Z]?-\d+(?:\.\d+)*)',
            r'(\d+(?:\.\d+)*[A-Z]?-\d+(?:\.\d+)*)\s+of\s+the\s+Virginia\s+Code'
        ]
        
        # Case citation patterns
        self.case_patterns = [
            r'([A-Z][a-zA-Z\s]+)\s+v\.?\s+([A-Z][a-zA-Z\s]+),?\s*(\d+)\s+([A-Z][a-z\.]+)\s*(\d+)(?:\s*\(([^)]+)\s*(\d{4})\))?',
            r'([A-Z][a-zA-Z\s]+)\s+v\.?\s+([A-Z][a-zA-Z\s]+)',
            r'([A-Z][a-zA-Z\s]+)\s+vs\.?\s+([A-Z][a-zA-Z\s]+)'
        ]
        
        # Court name patterns
        self.court_patterns = [
            r'(?:Virginia\s+)?(?:Supreme\s+)?Court\s+of\s+Appeals',
            r'(?:Virginia\s+)?Supreme\s+Court',
            r'(?:Virginia\s+)?Circuit\s+Court(?:\s+for\s+[A-Z][a-zA-Z\s]+)?',
            r'(?:Virginia\s+)?District\s+Court',
            r'[A-Z][a-zA-Z]+\s+(?:County\s+)?Circuit\s+Court'
        ]
    
    def _add_legal_patterns(self):
        """Add spaCy matcher patterns for legal entities."""
        # Virginia Code patterns
        va_code_pattern = [
            {"LOWER": {"IN": ["virginia", "va"]}},
            {"LOWER": "code"},
            {"TEXT": {"REGEX": r"§|Section"}},
            {"TEXT": {"REGEX": r"\d+.*"}}
        ]
        self.matcher.add("VIRGINIA_CODE", [va_code_pattern])
        
        # Court patterns
        court_pattern = [
            {"LOWER": {"IN": ["virginia", "va"]}, "OP": "?"},
            {"LOWER": {"IN": ["supreme", "circuit", "district"]}},
            {"LOWER": "court"}
        ]
        self.matcher.add("COURT", [court_pattern])
        
        # Family law terms
        family_terms = list(self.family_law_terms)
        for term in family_terms:
            if len(term.split()) > 1:
                pattern = [{"LOWER": word} for word in term.split()]
                self.matcher.add("FAMILY_LAW", [pattern])
    
    @monitor_performance
    async def process_text(self, text: str, source_type: str = "general") -> NLPResults:
        """Process text to extract legal entities and concepts."""
        try:
            if not self.nlp:
                await self.initialize()
            
            logger.info(f"Processing text for legal entities (length: {len(text)})")
            
            # Process with spaCy
            doc = self.nlp(text)
            
            # Extract entities
            virginia_statutes = self._extract_virginia_statutes(text)
            case_citations = self._extract_case_citations(text)
            legal_concepts = self._extract_legal_concepts(text, doc)
            entities = self._extract_named_entities(doc)
            topics = self._classify_legal_topics(text)
            
            # Calculate confidence score
            confidence = self._calculate_confidence(
                virginia_statutes, case_citations, legal_concepts, entities
            )
            
            results = NLPResults(
                virginia_statutes=virginia_statutes,
                case_citations=case_citations,
                legal_concepts=legal_concepts,
                entities=entities,
                topics=topics,
                confidence_score=confidence,
                processing_time_seconds=0.0  # Set by decorator
            )
            
            logger.info(f"NLP processing completed: {len(entities)} entities, {len(virginia_statutes)} statutes")
            return results
            
        except Exception as e:
            logger.error(f"Error in NLP processing: {e}")
            raise
    
    def _extract_virginia_statutes(self, text: str) -> List[VirginiaStatute]:
        """Extract Virginia Code statute references."""
        statutes = []
        
        for pattern in self.va_code_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                section = match.group(1) if match.groups() else match.group(0)
                
                # Parse title and section
                if '-' in section:
                    parts = section.split('-')
                    title = parts[0]
                    section_num = parts[1] if len(parts) > 1 else ""
                else:
                    title = section
                    section_num = ""
                
                statute = VirginiaStatute(
                    title=title,
                    section=section_num,
                    full_citation=match.group(0),
                    description=self._get_statute_description(title, section_num)
                )
                statutes.append(statute)
        
        return self._deduplicate_statutes(statutes)
    
    def _extract_case_citations(self, text: str) -> List[CaseCitation]:
        """Extract legal case citations."""
        citations = []
        
        for pattern in self.case_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                groups = match.groups()
                
                if len(groups) >= 2:
                    case_name = f"{groups[0]} v. {groups[1]}"
                    
                    citation = CaseCitation(
                        case_name=case_name,
                        volume=groups[2] if len(groups) > 2 else None,
                        reporter=groups[3] if len(groups) > 3 else None,
                        page=groups[4] if len(groups) > 4 else None,
                        court=groups[5] if len(groups) > 5 else None,
                        year=groups[6] if len(groups) > 6 else None,
                        full_citation=match.group(0)
                    )
                    citations.append(citation)
        
        return self._deduplicate_citations(citations)
    
    def _extract_legal_concepts(self, text: str, doc) -> List[LegalConcept]:
        """Extract family law and legal concepts."""
        concepts = []
        text_lower = text.lower()
        
        # Family law concepts
        for concept in self.family_law_terms:
            if concept in text_lower:
                # Find context around the concept
                concept_pos = text_lower.find(concept)
                context_start = max(0, concept_pos - 50)
                context_end = min(len(text), concept_pos + len(concept) + 50)
                context = text[context_start:context_end]
                
                legal_concept = LegalConcept(
                    concept=concept,
                    category="family_law",
                    confidence=0.8,
                    context=context.strip()
                )
                concepts.append(legal_concept)
        
        # Legal procedures
        for procedure in self.legal_procedures:
            if procedure in text_lower:
                procedure_pos = text_lower.find(procedure)
                context_start = max(0, procedure_pos - 50)
                context_end = min(len(text), procedure_pos + len(procedure) + 50)
                context = text[context_start:context_end]
                
                legal_concept = LegalConcept(
                    concept=procedure,
                    category="legal_procedure",
                    confidence=0.7,
                    context=context.strip()
                )
                concepts.append(legal_concept)
        
        return self._deduplicate_concepts(concepts)
    
    def _extract_named_entities(self, doc) -> List[LegalEntity]:
        """Extract named entities using spaCy."""
        entities = []
        
        # Standard spaCy entities
        for ent in doc.ents:
            if ent.label_ in ['PERSON', 'ORG', 'GPE', 'LAW', 'DATE']:
                entity = LegalEntity(
                    entity_type=ent.label_,
                    text=ent.text,
                    start_pos=ent.start_char,
                    end_pos=ent.end_char,
                    confidence=0.6,
                    context=self._get_entity_context(doc.text, ent.start_char, ent.end_char)
                )
                entities.append(entity)
        
        # Custom matcher entities
        matches = self.matcher(doc)
        for match_id, start, end in matches:
            span = doc[start:end]
            label = self.nlp.vocab.strings[match_id]
            
            entity = LegalEntity(
                entity_type=label,
                text=span.text,
                start_pos=span.start_char,
                end_pos=span.end_char,
                confidence=0.8,
                context=self._get_entity_context(doc.text, span.start_char, span.end_char)
            )
            entities.append(entity)
        
        return entities
    
    def _classify_legal_topics(self, text: str) -> List[str]:
        """Classify text into legal topic categories."""
        topics = []
        text_lower = text.lower()
        
        # Topic classification based on keywords
        topic_keywords = {
            'divorce': ['divorce', 'dissolution', 'marital', 'spouse'],
            'custody': ['custody', 'visitation', 'parenting', 'guardian'],
            'support': ['support', 'alimony', 'maintenance', 'child support'],
            'property': ['property', 'asset', 'distribution', 'equitable'],
            'domestic_relations': ['domestic', 'family', 'marriage', 'children'],
            'virginia_law': ['virginia', 'va code', 'commonwealth'],
            'court_procedure': ['motion', 'hearing', 'trial', 'petition', 'complaint']
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                topics.append(topic)
        
        return topics
    
    def _get_entity_context(self, text: str, start: int, end: int, window: int = 100) -> str:
        """Get context around an entity."""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end].strip()
    
    def _get_statute_description(self, title: str, section: str) -> Optional[str]:
        """Get description for common Virginia statutes."""
        # Common Virginia Code descriptions
        descriptions = {
            '20-107.1': 'Grounds for divorce from bond of matrimony',
            '20-107.3': 'Determination of custody and visitation',
            '20-108.1': 'Child support guidelines',
            '20-88.1': 'Court order for support of minor children',
            '16.1-278.15': 'Custody and visitation arrangements',
            '20-124.2': 'Best interests of the child',
            '20-124.3': 'Joint custody or sole custody'
        }
        
        full_section = f"{title}-{section}" if section else title
        return descriptions.get(full_section)
    
    def _calculate_confidence(self, statutes: List[VirginiaStatute], 
                            citations: List[CaseCitation],
                            concepts: List[LegalConcept], 
                            entities: List[LegalEntity]) -> float:
        """Calculate overall confidence score for NLP results."""
        scores = []
        
        # Weight different types of entities
        if statutes:
            scores.append(0.9)  # High confidence for statute references
        if citations:
            scores.append(0.8)  # High confidence for case citations
        if concepts:
            avg_concept_confidence = sum(c.confidence for c in concepts) / len(concepts)
            scores.append(avg_concept_confidence)
        if entities:
            avg_entity_confidence = sum(e.confidence for e in entities) / len(entities)
            scores.append(avg_entity_confidence)
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _deduplicate_statutes(self, statutes: List[VirginiaStatute]) -> List[VirginiaStatute]:
        """Remove duplicate statute references."""
        seen = set()
        unique_statutes = []
        
        for statute in statutes:
            key = f"{statute.title}-{statute.section}"
            if key not in seen:
                seen.add(key)
                unique_statutes.append(statute)
        
        return unique_statutes
    
    def _deduplicate_citations(self, citations: List[CaseCitation]) -> List[CaseCitation]:
        """Remove duplicate case citations."""
        seen = set()
        unique_citations = []
        
        for citation in citations:
            key = citation.case_name.lower()
            if key not in seen:
                seen.add(key)
                unique_citations.append(citation)
        
        return unique_citations
    
    def _deduplicate_concepts(self, concepts: List[LegalConcept]) -> List[LegalConcept]:
        """Remove duplicate legal concepts."""
        seen = set()
        unique_concepts = []
        
        for concept in concepts:
            key = f"{concept.concept}-{concept.category}"
            if key not in seen:
                seen.add(key)
                unique_concepts.append(concept)
        
        return unique_concepts


class LegalContentClassifier:
    """Classify legal content by practice area and relevance."""
    
    def __init__(self):
        self.virginia_indicators = [
            'virginia', 'va', 'commonwealth', 'richmond', 'norfolk',
            'virginia beach', 'chesapeake', 'newport news', 'hampton',
            'alexandria', 'portsmouth', 'suffolk', 'lynchburg'
        ]
        
        self.practice_areas = {
            'family_law': [
                'divorce', 'custody', 'child support', 'alimony',
                'adoption', 'paternity', 'domestic relations'
            ],
            'civil_litigation': [
                'contract', 'tort', 'personal injury', 'breach',
                'damages', 'lawsuit', 'litigation'
            ],
            'criminal_law': [
                'criminal', 'felony', 'misdemeanor', 'dui', 'dwi',
                'assault', 'theft', 'drug', 'traffic'
            ],
            'real_estate': [
                'property', 'deed', 'mortgage', 'closing',
                'title', 'easement', 'zoning'
            ]
        }
    
    @monitor_performance
    async def classify_content(self, text: str, title: str = "") -> Dict[str, Any]:
        """Classify legal content by relevance and practice area."""
        try:
            content = f"{title} {text}".lower()
            
            # Virginia relevance score
            virginia_score = self._calculate_virginia_relevance(content)
            
            # Practice area classification
            practice_scores = self._classify_practice_areas(content)
            primary_practice_area = max(practice_scores.items(), key=lambda x: x[1])
            
            # Legal relevance score
            legal_relevance = self._calculate_legal_relevance(content)
            
            # Content quality indicators
            quality_score = self._assess_content_quality(text)
            
            return {
                'virginia_relevance': virginia_score,
                'practice_area': primary_practice_area[0],
                'practice_area_confidence': primary_practice_area[1],
                'all_practice_scores': practice_scores,
                'legal_relevance': legal_relevance,
                'quality_score': quality_score,
                'is_virginia_specific': virginia_score > 0.3,
                'is_family_law': practice_scores.get('family_law', 0) > 0.5,
                'overall_relevance': (virginia_score + legal_relevance + quality_score) / 3
            }
            
        except Exception as e:
            logger.error(f"Error classifying content: {e}")
            return {'error': str(e)}
    
    def _calculate_virginia_relevance(self, content: str) -> float:
        """Calculate Virginia-specific relevance score."""
        virginia_matches = sum(1 for indicator in self.virginia_indicators if indicator in content)
        max_possible = len(self.virginia_indicators)
        return min(virginia_matches / max_possible * 2, 1.0)  # Scale and cap at 1.0
    
    def _classify_practice_areas(self, content: str) -> Dict[str, float]:
        """Classify content by practice area."""
        scores = {}
        
        for area, keywords in self.practice_areas.items():
            matches = sum(1 for keyword in keywords if keyword in content)
            scores[area] = min(matches / len(keywords) * 2, 1.0)
        
        return scores
    
    def _calculate_legal_relevance(self, content: str) -> float:
        """Calculate overall legal relevance."""
        legal_indicators = [
            'court', 'judge', 'attorney', 'lawyer', 'legal', 'law',
            'statute', 'code', 'case', 'ruling', 'decision', 'motion',
            'hearing', 'trial', 'litigation', 'settlement'
        ]
        
        matches = sum(1 for indicator in legal_indicators if indicator in content)
        return min(matches / len(legal_indicators) * 2, 1.0)
    
    def _assess_content_quality(self, text: str) -> float:
        """Assess content quality indicators."""
        # Basic quality metrics
        word_count = len(text.split())
        sentence_count = len([s for s in text.split('.') if s.strip()])
        
        # Quality indicators
        has_citations = bool(re.search(r'\d+\s+[A-Z][a-z\.]+\s+\d+', text))
        has_code_refs = bool(re.search(r'(?:§|Section)\s*\d+', text))
        has_case_names = bool(re.search(r'[A-Z][a-z]+\s+v\.?\s+[A-Z][a-z]+', text))
        
        quality_score = 0.0
        
        # Length bonus
        if word_count > 100:
            quality_score += 0.3
        if word_count > 500:
            quality_score += 0.2
        
        # Structure bonus
        if sentence_count > 5:
            quality_score += 0.2
        
        # Legal content indicators
        if has_citations:
            quality_score += 0.1
        if has_code_refs:
            quality_score += 0.1
        if has_case_names:
            quality_score += 0.1
        
        return min(quality_score, 1.0)


# Main NLP service combining all components
class LegalNLPService:
    """Main service for legal NLP processing."""
    
    def __init__(self):
        self.virginia_nlp = VirginiaLegalNLP()
        self.classifier = LegalContentClassifier()
        self._initialized = False
    
    async def initialize(self):
        """Initialize all NLP components."""
        if not self._initialized:
            await self.virginia_nlp.initialize()
            self._initialized = True
            logger.info("Legal NLP Service initialized successfully")
    
    @monitor_performance
    async def process_legal_content(self, text: str, title: str = "", 
                                  source_type: str = "general") -> Dict[str, Any]:
        """Complete NLP processing for legal content."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Extract legal entities
            nlp_results = await self.virginia_nlp.process_text(text, source_type)
            
            # Classify content
            classification = await self.classifier.classify_content(text, title)
            
            # Combine results
            return {
                'entities': {
                    'virginia_statutes': [vars(s) for s in nlp_results.virginia_statutes],
                    'case_citations': [vars(c) for c in nlp_results.case_citations],
                    'legal_concepts': [vars(c) for c in nlp_results.legal_concepts],
                    'named_entities': [vars(e) for e in nlp_results.entities]
                },
                'classification': classification,
                'topics': nlp_results.topics,
                'confidence_score': nlp_results.confidence_score,
                'processing_time': nlp_results.processing_time_seconds
            }
            
        except Exception as e:
            logger.error(f"Error in legal content processing: {e}")
            raise


# Export main components
__all__ = [
    'LegalNLPService',
    'VirginiaLegalNLP', 
    'LegalContentClassifier',
    'LegalEntity',
    'VirginiaStatute',
    'CaseCitation',
    'LegalConcept',
    'NLPResults'
]