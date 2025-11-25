#!/usr/bin/env python3
"""
Simple URL analyzer using Claude API.
Takes any URL and provides a decompressed analysis of the content.
"""

import os
import sys
import requests
from anthropic import Anthropic
import arxiv
from urllib.parse import urlparse
import json


class URLAnalyzer:
    """Analyzes any URL content using Claude"""
    
    def __init__(self, api_key: str = None):
        # Use provided API key or get from environment
        if api_key:
            self.client = Anthropic(api_key=api_key)
        else:
            self.client = Anthropic()  # Will use ANTHROPIC_API_KEY env var
    
    def fetch_content(self, url: str) -> dict:
        """Fetch content from URL"""
        
        # Handle ArXiv papers specially
        if 'arxiv.org' in url:
            return self.fetch_arxiv(url)
        
        # Handle Twitter/X
        elif 'twitter.com' in url or 'x.com' in url:
            # For tweets, we'll need to ask user to paste content
            # since Twitter API requires auth
            return {
                'url': url,
                'type': 'tweet',
                'content': None,
                'needs_paste': True
            }
        
        # For other URLs, try to fetch HTML
        else:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (compatible; ContentAnalyzer/1.0)'
                }
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                
                return {
                    'url': url,
                    'type': 'article',
                    'content': response.text[:50000],  # Limit content size
                    'needs_paste': False
                }
            except Exception as e:
                print(f"Could not fetch URL directly: {e}")
                return {
                    'url': url,
                    'type': 'unknown',
                    'content': None,
                    'needs_paste': True
                }
    
    def fetch_arxiv(self, url: str) -> dict:
        """Fetch ArXiv paper details"""
        # Extract paper ID
        if 'abs/' in url:
            paper_id = url.split('abs/')[-1].split('v')[0]
        elif 'pdf/' in url:
            paper_id = url.split('pdf/')[-1].replace('.pdf', '').split('v')[0]
        else:
            paper_id = url.split('/')[-1].split('v')[0]
        
        try:
            search = arxiv.Search(id_list=[paper_id])
            paper = next(arxiv.Client().results(search))
            
            return {
                'url': url,
                'type': 'arxiv',
                'title': paper.title,
                'authors': [author.name for author in paper.authors],
                'abstract': paper.summary,
                'needs_paste': False
            }
        except Exception as e:
            print(f"Error fetching ArXiv paper: {e}")
            return {
                'url': url,
                'type': 'arxiv',
                'content': None,
                'needs_paste': True
            }
    
    def create_analysis_prompt(self, content_data: dict) -> str:
        """Create the decompression prompt for Claude"""
        
        base_prompt = """You are an expert at quickly understanding and explaining technical content.
Your task is to decompress this content into a clear, actionable summary.

Provide your analysis in this EXACT format:

## 📝 ONE-LINER
[What is this in one clear sentence?]

## 🚀 KEY INNOVATION
[What's new or important here? 1-2 sentences]

## 💡 WHY IT MATTERS
[Why should someone care? Impact and relevance. 2-3 sentences]

## 🔍 MAIN INSIGHTS
• [Key point 1]
• [Key point 2]
• [Key point 3]
• [Add more if needed, up to 5 total]

## ⚙️ HOW IT WORKS
[Brief explanation of the methodology or approach. 2-3 sentences. Skip if not applicable]

## 📊 KEY RESULTS
[What did they achieve? Include specific metrics if mentioned. 2-3 sentences]

## ⚠️ LIMITATIONS
[What are the caveats, limitations, or things to watch out for? 1-2 sentences]

## 🔗 CONNECTIONS
[How does this relate to other work or trends? 1-2 sentences]

## 🎯 WHO SHOULD READ THIS
[Specific audience who would benefit most. 1 sentence]

## 📌 TLDR
[2-3 sentence summary for someone with 30 seconds]

## 🤔 SHOULD YOU READ THE FULL VERSION?
[Yes/No and specific reason why. 1 sentence]

---

Now analyze this content:

"""
        
        # Format content based on type
        if content_data['type'] == 'arxiv':
            content_str = f"""
PAPER: {content_data.get('title', 'Unknown')}
AUTHORS: {', '.join(content_data.get('authors', []))}
URL: {content_data['url']}

ABSTRACT:
{content_data.get('abstract', 'Not available')}
"""
        elif content_data['type'] == 'tweet':
            content_str = f"""
TWEET/THREAD from {content_data['url']}:
{content_data.get('content', 'Content not provided')}
"""
        else:
            # For articles and other content
            content_str = f"""
URL: {content_data['url']}
CONTENT:
{content_data.get('content', 'Content not provided')[:10000]}  # Limit for token management
"""
        
        return base_prompt + content_str
    
    def analyze(self, url: str, pasted_content: str = None) -> str:
        """Main analysis function"""
        
        # Fetch content
        print(f"📥 Fetching content from: {url}")
        content_data = self.fetch_content(url)
        
        # Handle pasted content if needed
        if content_data['needs_paste'] and pasted_content:
            content_data['content'] = pasted_content
        elif content_data['needs_paste'] and not pasted_content:
            return "⚠️  This URL requires manual content paste. Please provide the content."
        
        # Create prompt
        prompt = self.create_analysis_prompt(content_data)
        
        # Call Claude using the beta API for large context
        print("🤖 Analyzing with Claude...")
        try:
            response = self.client.beta.messages.create(
                model="claude-3-5-sonnet-20241022",  # Latest Sonnet model
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                betas=["prompt-caching-2024-07-31"]  # Enable prompt caching for efficiency
            )
            
            return response.content[0].text
            
        except Exception as e:
            return f"❌ Error calling Claude API: {e}"


def main():
    """Simple CLI interface"""
    
    # Get API key from environment variable
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not api_key:
        print("❌ Error: Please set ANTHROPIC_API_KEY environment variable")
        print("\nTo set it, run:")
        print("export ANTHROPIC_API_KEY='your-api-key-here'")
        print("\nOr add it to your ~/.bashrc or ~/.zshrc file")
        sys.exit(1)
    
    analyzer = URLAnalyzer(api_key)
    
    print("🔍 URL Content Analyzer (powered by Claude)")
    print("-" * 60)
    print("Enter a URL to analyze (or 'quit' to exit)")
    print("Supports: ArXiv papers, articles, tweets (paste required)")
    print("-" * 60)
    
    while True:
        print("\n📎 Enter URL:")
        url = input("> ").strip()
        
        if url.lower() in ['quit', 'exit', 'q']:
            print("👋 Goodbye!")
            break
        
        if not url:
            continue
        
        # Check if we need pasted content
        pasted_content = None
        if 'twitter.com' in url or 'x.com' in url:
            print("\n📋 Please paste the tweet content (press Enter twice when done):")
            lines = []
            while True:
                line = input()
                if not line:
                    break
                lines.append(line)
            pasted_content = '\n'.join(lines)
        
        # Analyze
        result = analyzer.analyze(url, pasted_content)
        
        # Display results
        print("\n" + "="*60)
        print(result)
        print("="*60)
        
        # Option to save
        save = input("\n💾 Save this analysis? (y/n): ").strip().lower()
        if save == 'y':
            # Create output directory if it doesn't exist
            os.makedirs('out', exist_ok=True)
            
            # Generate filename
            domain = urlparse(url).netloc.replace('.', '_')
            filename = f"analysis_{domain}_{len(os.listdir('out'))}.md"
            filepath = os.path.join('out', filename)
            
            with open(filepath, 'w') as f:
                f.write(f"# Analysis of {url}\n\n")
                f.write(result)
            
            print(f"✅ Saved to: {filepath}")


if __name__ == "__main__":
    main()