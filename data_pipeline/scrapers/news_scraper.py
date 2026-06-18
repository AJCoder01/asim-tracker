"""
ASIM-Tracker: Asynchronous News RSS Scraper
Polls news RSS feeds and HTML corporate announcement boards asynchronously,
extracts and cleans title/description text, resolves relevant stock tickers,
and pushes the processed news to the ingestion buffer queue.
"""

import asyncio
import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Set
import xml.etree.ElementTree as ET

import aiohttp
from bs4 import BeautifulSoup

from data_pipeline.scrapers.redis_queue import RedisQueueClient

logger = logging.getLogger("asim_tracker.news_scraper")

# List of default RSS feeds representing financial news and disclosures in India
DEFAULT_FEED_URLS = [
    "https://www.moneycontrol.com/rss/latestnews.xml",
    "https://www.moneycontrol.com/rss/business.xml",
    "https://www.moneycontrol.com/rss/MC_trends.xml",
]

# Static mapping for prominent low-priced cash equity tickers (under ₹200) and general active NSE tickers
COMPANY_TICKER_MAP = {
    # Tickers under/around ₹200 or high-liquid targets
    "suzlon energy": "SUZLON",
    "suzlon": "SUZLON",
    "vodafone idea": "IDEA",
    "idea cellular": "IDEA",
    "yes bank": "YESBANK",
    "nhpc limited": "NHPC",
    "nhpc": "NHPC",
    "gmr airports infrastructure": "GMRINFRA",
    "gmr airports": "GMRINFRA",
    "gmr infra": "GMRINFRA",
    "gmr infrastructure": "GMRINFRA",
    "indian railway finance corporation": "IRFC",
    "irfc": "IRFC",
    "south indian bank": "SOUTHBANK",
    "punjab national bank": "PNB",
    "pnb": "PNB",
    "tata steel": "TATASTEEL",
    "zomato limited": "ZOMATO",
    "zomato": "ZOMATO",
    
    # Larger benchmark names for index references
    "tata motors": "TATAMOTORS",
    "reliance industries": "RELIANCE",
    "reliance": "RELIANCE",
    "state bank of india": "SBIN",
    "sbi": "SBIN",
    "tata steel limited": "TATASTEEL",
    "infosys": "INFY",
    "tcs": "TCS",
    "tata consultancy services": "TCS",
}

# HTTP headers to mimic browser and bypass basic scraping firewalls
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class NewsScraper:
    """
    Asynchronous RSS Crawler that polls financial feeds, processes HTML content,
    resolves news to NSE tickers via Regex, and pushes entries to Redis.
    """

    def __init__(
        self,
        feed_urls: Optional[List[str]] = None,
        queue_client: Optional[RedisQueueClient] = None,
    ) -> None:
        self.feed_urls = feed_urls or DEFAULT_FEED_URLS
        self.queue_client = queue_client or RedisQueueClient()
        self.processed_urls: Set[str] = set()

    def clean_text(self, text: str) -> str:
        """
        Strips HTML tags and normalizes whitespace in the text content.
        """
        if not text:
            return ""
        try:
            # Parse HTML and extract plain text
            soup = BeautifulSoup(text, "html.parser")
            cleaned = soup.get_text()
            # Normalize whitespace characters
            cleaned = re.sub(r"\s+", " ", cleaned)
            return cleaned.strip()
        except Exception as e:
            logger.warning(f"Error cleaning HTML text: {e}")
            return text.strip()

    def resolve_ticker(self, text: str) -> Optional[str]:
        """
        Resolves a target stock ticker from news headline/text content.
        Uses hierarchical regex matching against COMPANY_TICKER_MAP.
        """
        if not text:
            return None

        # Clean text lowercase for case-insensitive matching
        text_lower = text.lower()

        # 1. Search for specific company name patterns (prioritized)
        for company_name, ticker in COMPANY_TICKER_MAP.items():
            pattern = rf"\b{re.escape(company_name)}\b"
            if re.search(pattern, text_lower):
                return ticker

        # 2. Check for explicit exchange prefix or bracket patterns:
        # e.g. "NSE: SUZLON", "[SUZLON]", "(SUZLON)", "SUZLON.NS"
        patterns = [
            r"\bNSE\s*:\s*([A-Z0-9]+)\b",
            r"\(([A-Z0-9]+)\)",
            r"\[([A-Z0-9]+)\]",
            r"\b([A-Z0-9]+)\.NS\b",
        ]
        for pat in patterns:
            for match in re.finditer(pat, text):
                candidate = match.group(1).upper()
                if candidate in COMPANY_TICKER_MAP.values():
                    return candidate

        # 3. Check for standalone uppercase ticker names from our universe
        for ticker in COMPANY_TICKER_MAP.values():
            # Match only uppercase ticker as a standalone word
            pattern = rf"\b{re.escape(ticker)}\b"
            if re.search(pattern, text):
                return ticker

        return None

    async def fetch_feed(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        """
        Asynchronously fetches the XML/HTML feed payload.
        """
        try:
            async with session.get(url, headers=HTTP_HEADERS, timeout=10, ssl=False) as response:
                if response.status != 200:
                    logger.warning(f"Failed to fetch feed {url}: HTTP {response.status}")
                    return None
                return await response.text()
        except asyncio.TimeoutError:
            logger.warning(f"Timeout occurred fetching feed {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching feed {url}: {e}")
            return None

    def parse_rss_xml(self, xml_content: str) -> List[Dict[str, str]]:
        """
        Parses XML RSS structure to extract article metadata (title, description, link, pub_date).
        """
        articles = []
        try:
            # Parse XML tree
            root = ET.fromstring(xml_content)
            # Find all <item> tags (works for RSS 2.0)
            items = root.findall(".//item")
            for item in items:
                title_el = item.find("title")
                desc_el = item.find("description")
                link_el = item.find("link")
                pub_date_el = item.find("pubDate")

                title = title_el.text if title_el is not None else ""
                desc = desc_el.text if desc_el is not None else ""
                link = link_el.text if link_el is not None else ""
                pub_date = pub_date_el.text if pub_date_el is not None else ""

                articles.append({
                    "title": title,
                    "description": desc,
                    "link": link,
                    "pub_date": pub_date,
                })
        except ET.ParseError as pe:
            logger.error(f"XML parsing failed: {pe}")
        except Exception as e:
            logger.error(f"Unexpected error parsing RSS: {e}")
        return articles

    async def process_articles(self, articles: List[Dict[str, str]]) -> int:
        """
        Processes articles, resolves tickers, and pushes entries to the Redis queue.
        """
        pushed_count = 0
        for article in articles:
            url = article.get("link", "").strip()
            if not url or url in self.processed_urls:
                continue

            # Clean and combine title and description for resolution
            raw_title = article.get("title", "")
            raw_desc = article.get("description", "")
            
            clean_title = self.clean_text(raw_title)
            clean_desc = self.clean_text(raw_desc)
            combined_text = f"{clean_title} | {clean_desc}"

            # Attempt ticker resolution
            ticker = self.resolve_ticker(combined_text)
            if ticker:
                # Deduplicate url
                self.processed_urls.add(url)
                
                # Push to ingestion queue
                # We start with 0.0 sentiment score. It will be updated by FinBERT in Milestone 2
                await self.queue_client.push_news(
                    ticker=ticker,
                    text=combined_text,
                    sentiment=0.0
                )
                logger.info(f"Pushed news article resolved to ticker [{ticker}]: {clean_title[:60]}...")
                pushed_count += 1

        return pushed_count

    async def poll_once(self, session: aiohttp.ClientSession) -> int:
        """
        Runs a single crawl cycle over all feed URLs.
        """
        logger.info("Starting crawl cycle...")
        total_pushed = 0
        
        for url in self.feed_urls:
            xml_content = await self.fetch_feed(session, url)
            if xml_content:
                articles = self.parse_rss_xml(xml_content)
                pushed = await self.process_articles(articles)
                total_pushed += pushed
                
        logger.info(f"Crawl cycle completed. Pushed {total_pushed} new items.")
        return total_pushed

    async def run_scraper_loop(self, poll_interval_seconds: int = 60) -> None:
        """
        Runs the scraper in a continuous async polling loop.
        """
        await self.queue_client.connect()
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    await self.poll_once(session)
                except Exception as e:
                    logger.error(f"Uncaught exception in scraper loop: {e}")
                
                logger.info(f"Sleeping for {poll_interval_seconds} seconds...")
                await asyncio.sleep(poll_interval_seconds)


if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    # Run the scraper loop standalone
    scraper = NewsScraper()
    try:
        asyncio.run(scraper.run_scraper_loop())
    except KeyboardInterrupt:
        logger.info("Scraper execution stopped by user.")
