#!/usr/bin/env python3
"""
Legal Website Research and Analysis Demo

This demo shows how the research agent discovers valuable legal websites
for family law practice in Virginia, analyzes their scraping potential,
and recommends optimal approaches.
"""

import asyncio
import sys
from pathlib import Path
from typing import List
import json

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.research.legal_website_researcher import get_legal_website_researcher, LegalWebsiteCandidate
from src.research.website_analyzer import get_website_analyzer, WebsiteAnalysis


async def demo_legal_website_research():
    """Demonstrate the complete legal website research process."""
    print("🚀 Legal Website Research Agent Demo")
    print("=" * 70)
    print("Discovering valuable legal websites for Virginia family law practice")
    print("Focus: Circuit Court procedures, forms, and educational content")
    
    researcher = get_legal_website_researcher()
    analyzer = get_website_analyzer()
    
    try:
        # Step 1: Discover legal websites
        print(f"\n🔍 STEP 1: Website Discovery")
        print("=" * 40)
        print("Researching legal websites from seed URLs...")
        print("• Virginia official court sites")
        print("• Virginia State Bar resources") 
        print("• National family law organizations")
        print("• Legal education platforms")
        print("• Practice-oriented resources")
        
        candidates = await researcher.research_legal_websites(max_sites=20)
        
        print(f"\n📊 Discovery Results:")
        print(f"   Total candidates found: {len(candidates)}")
        
        # Show top candidates
        print(f"\n🏆 Top Legal Website Candidates:")
        print("-" * 50)
        for i, candidate in enumerate(candidates[:10], 1):
            print(f"{i:2d}. {candidate.domain}")
            print(f"    Title: {candidate.title}")
            print(f"    Relevance: {candidate.relevance_score:.2f}")
            print(f"    Authority: {candidate.authority_level}")
            print(f"    Virginia: {'✅' if candidate.virginia_specific else '❌'}")
            print(f"    Family Law: {'✅' if candidate.family_law_focus else '❌'}")
            print(f"    Practice Focus: {'✅' if candidate.practice_oriented else '❌'}")
            print(f"    Content: {', '.join(candidate.content_types) if candidate.content_types else 'general'}")
            print()
        
        # Step 2: Analyze top candidates
        print(f"\n🔬 STEP 2: Website Analysis")
        print("=" * 40)
        print("Analyzing top candidates for scraping strategies...")
        
        analyses = []
        top_candidates = candidates[:5]  # Analyze top 5
        
        for i, candidate in enumerate(top_candidates, 1):
            print(f"\n📋 Analyzing {i}/{len(top_candidates)}: {candidate.domain}")
            
            try:
                analysis = await analyzer.analyze_website(candidate)
                analyses.append(analysis)
                
                print(f"   ✅ Analysis complete")
                print(f"   Recommended approach: {analysis.recommended_approach}")
                print(f"   Estimated value: {analysis.estimated_value:.2f}")
                print(f"   Content areas: {len(analysis.content_areas)}")
                
            except Exception as e:
                print(f"   ❌ Analysis failed: {e}")
        
        # Step 3: Show detailed analysis results
        print(f"\n📊 STEP 3: Detailed Analysis Results")
        print("=" * 50)
        
        for i, analysis in enumerate(analyses, 1):
            candidate = analysis.candidate
            strategy = analysis.technical_analysis.get('strategy', {})
            
            print(f"\n🎯 Website {i}: {candidate.domain}")
            print("-" * 30)
            print(f"📚 Title: {candidate.title}")
            print(f"🏛️  Authority Level: {candidate.authority_level}")
            print(f"📈 Relevance Score: {candidate.relevance_score:.2f}")
            print(f"💎 Estimated Value: {analysis.estimated_value:.2f}")
            
            print(f"\n🔧 Technical Analysis:")
            print(f"   Scraping Method: {analysis.recommended_approach}")
            print(f"   Complexity: {strategy.get('complexity', 'unknown')}")
            print(f"   Success Probability: {strategy.get('success_probability', 0):.1%}")
            print(f"   Estimated Pages: {strategy.get('estimated_pages', 0)}")
            
            print(f"\n📝 Content Features:")
            features = []
            if candidate.virginia_specific:
                features.append("Virginia-specific")
            if candidate.family_law_focus:
                features.append("Family law focus")
            if candidate.practice_oriented:
                features.append("Practice-oriented")
            if candidate.has_forms:
                features.append("Legal forms")
            if candidate.has_procedures:
                features.append("Procedures")
            if candidate.has_case_law:
                features.append("Case law")
            
            print(f"   {', '.join(features) if features else 'General legal content'}")
            
            if analysis.content_areas:
                print(f"\n🎯 Content Areas Found:")
                for area, score in sorted(analysis.content_areas.items(), key=lambda x: x[1], reverse=True):
                    print(f"   • {area.replace('_', ' ').title()}: {score:.2f}")
            
            if analysis.scraping_notes:
                print(f"\n📋 Scraping Notes:")
                for note in analysis.scraping_notes[:3]:  # Show first 3 notes
                    print(f"   • {note}")
            
            print()
        
        # Step 4: Generate recommendations
        print(f"\n🎯 STEP 4: Scraping Recommendations")
        print("=" * 50)
        
        # Group by scraping method
        by_method = {}
        for analysis in analyses:
            method = analysis.recommended_approach
            if method not in by_method:
                by_method[method] = []
            by_method[method].append(analysis)
        
        for method, method_analyses in by_method.items():
            print(f"\n🔧 {method.upper()} Scraping Method:")
            print(f"   Sites: {len(method_analyses)}")
            
            for analysis in method_analyses:
                print(f"   • {analysis.candidate.domain} (value: {analysis.estimated_value:.2f})")
            
            # Method-specific recommendations
            if method == "static":
                print(f"   📋 Tools: Scrapy, BeautifulSoup, Requests")
                print(f"   📅 Frequency: Weekly")
                print(f"   ⚡ Complexity: Low")
                
            elif method == "dynamic":
                print(f"   📋 Tools: Selenium, Playwright")
                print(f"   📅 Frequency: Weekly (with caching)")
                print(f"   ⚡ Complexity: High")
                
            elif method == "hybrid":
                print(f"   📋 Tools: Scrapy + Selenium")
                print(f"   📅 Frequency: Weekly")
                print(f"   ⚡ Complexity: Medium")
        
        # Step 5: Priority recommendations
        print(f"\n🏆 STEP 5: Implementation Priority")
        print("=" * 40)
        
        # Sort by estimated value
        sorted_analyses = sorted(analyses, key=lambda x: x.estimated_value, reverse=True)
        
        print(f"Recommended implementation order:")
        for i, analysis in enumerate(sorted_analyses, 1):
            candidate = analysis.candidate
            print(f"\n{i}. {candidate.domain}")
            print(f"   Value: {analysis.estimated_value:.2f}")
            print(f"   Method: {analysis.recommended_approach}")
            print(f"   Focus: ", end="")
            
            focus_areas = []
            if candidate.virginia_specific:
                focus_areas.append("Virginia law")
            if candidate.family_law_focus:
                focus_areas.append("Family law")
            if candidate.practice_oriented:
                focus_areas.append("Practice guidance")
            
            print(", ".join(focus_areas) if focus_areas else "General legal")
        
        # Summary statistics
        print(f"\n📊 RESEARCH SUMMARY")
        print("=" * 30)
        print(f"Total websites discovered: {len(candidates)}")
        print(f"Detailed analyses completed: {len(analyses)}")
        print(f"High-value sites (>0.7): {len([a for a in analyses if a.estimated_value > 0.7])}")
        print(f"Virginia-specific sites: {len([a for a in analyses if a.candidate.virginia_specific])}")
        print(f"Family law focused sites: {len([a for a in analyses if a.candidate.family_law_focus])}")
        print(f"Practice-oriented sites: {len([a for a in analyses if a.candidate.practice_oriented])}")
        
        # Show method distribution
        method_counts = {}
        for analysis in analyses:
            method = analysis.recommended_approach
            method_counts[method] = method_counts.get(method, 0) + 1
        
        print(f"\nScraping method distribution:")
        for method, count in method_counts.items():
            print(f"   {method}: {count} sites")
        
        print(f"\n✅ Legal website research complete!")
        print(f"Ready to implement scraping strategies for identified sites.")
        
    finally:
        await researcher.close()
        await analyzer.close()


def main():
    """Run the legal website research demo."""
    asyncio.run(demo_legal_website_research())


if __name__ == "__main__":
    main()