"""
Competitor Dashboard Auto-Updater
Scrapes public data and updates competitor-dashboard.html
"""

import re
import json
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime


HTML_FILE = 'competitor-dashboard.html'

# === CONFIG ===
INSTAGRAM_PROFILES = {
    'headit':   'headitsolutions',
    'itrust':   'itrust.ch',
    'care4it':  'care4it',
    'leuchter': 'leuchterag.ch',
}

LINKEDIN_PAGES = {
    'headit':   'https://ch.linkedin.com/company/headitsolutions',
    'itrust':   'https://ch.linkedin.com/company/itrust',
    'care4it':  'https://www.linkedin.com/company/care4it-ch',
    'leuchter': 'https://ch.linkedin.com/company/leuchter-it-solutions',
}

RSS_FEEDS = {
    'headit':   ['https://www.headitsolutions.ch/feed/', 'https://www.headitsolutions.ch/news/feed/'],
    'itrust':   ['https://www.itrust.ch/feed/', 'https://www.itrust.ch/blog/feed/'],
    'care4it':  ['https://info.care4it.ch/blog/rss.xml'],
    'leuchter': ['https://www.leuchterag.ch/blog/feed/', 'https://www.leuchterag.ch/feed/'],
}

WEBSITES = {
    'headit':   'https://www.headitsolutions.ch',
    'itrust':   'https://www.itrust.ch',
    'care4it':  'https://www.care4it.ch',
    'leuchter': 'https://www.leuchterag.ch',
}


def fetch_url(url, timeout=15):
    """Fetch URL content with a browser-like user agent."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'de-CH,de;q=0.9,en;q=0.8',
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f'  [WARN] Could not fetch {url}: {e}')
        return None


def scrape_instagram_followers(username):
    """Try to get follower count from Instagram public profile."""
    url = f'https://www.instagram.com/{username}/'
    html = fetch_url(url)
    if not html:
        return None

    # Try meta description: "X Followers, Y Following, Z Posts"
    m = re.search(r'content="([\d,.]+[KkMm]?)\s+Followers', html)
    if m:
        return parse_count(m.group(1))

    # Try JSON in page source
    m = re.search(r'"edge_followed_by":\{"count":(\d+)\}', html)
    if m:
        return int(m.group(1))

    # Try og:description
    m = re.search(r'<meta[^>]+property="og:description"[^>]+content="([\d,.]+[KkMm]?)\s+Followers', html)
    if m:
        return parse_count(m.group(1))

    return None


def scrape_instagram_posts(username):
    """Try to get post count from Instagram public profile."""
    url = f'https://www.instagram.com/{username}/'
    html = fetch_url(url)
    if not html:
        return None

    m = re.search(r'([\d,.]+)\s+Posts', html)
    if m:
        return parse_count(m.group(1))

    m = re.search(r'"edge_owner_to_timeline_media":\{"count":(\d+)', html)
    if m:
        return int(m.group(1))

    return None


def parse_count(s):
    """Parse a count string like '1,234' or '3.2K' into an integer."""
    s = s.strip().replace(',', '').replace("'", '')
    if s.upper().endswith('K'):
        return int(float(s[:-1]) * 1000)
    if s.upper().endswith('M'):
        return int(float(s[:-1]) * 1000000)
    try:
        return int(float(s))
    except ValueError:
        return None


def format_ch_number(n):
    """Format number Swiss style: 1'234"""
    if n is None:
        return None
    s = str(n)
    if len(s) <= 3:
        return s
    parts = []
    while s:
        parts.append(s[-3:])
        s = s[:-3]
    return "'".join(reversed(parts))


def fetch_rss_posts(feed_urls):
    """Fetch latest blog posts from RSS feeds. Returns list of (title, link, date)."""
    for url in feed_urls:
        xml = fetch_url(url)
        if not xml:
            continue
        try:
            root = ET.fromstring(xml)
            items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
            posts = []
            for item in items[:5]:
                title_el = item.find('title') or item.find('{http://www.w3.org/2005/Atom}title')
                link_el = item.find('link') or item.find('{http://www.w3.org/2005/Atom}link')
                title = title_el.text if title_el is not None else ''
                link = ''
                if link_el is not None:
                    link = link_el.text or link_el.get('href', '')
                if title:
                    posts.append((title.strip(), link.strip()))
            if posts:
                return posts
        except ET.ParseError:
            continue
    return []


def update_stat_in_html(html, comp, stat_label, new_value):
    """
    Update a stat value in a card.
    Looks for pattern: data-comp="comp" ... <div class="val">OLD</div><div class="lbl">stat_label</div>
    """
    if new_value is None:
        return html

    formatted = format_ch_number(new_value) if isinstance(new_value, int) else str(new_value)

    # Find the card block for this competitor and update the specific stat
    pattern = (
        r'(data-comp="' + re.escape(comp) + r'".*?'
        r'<div class="val">)[^<]*(</div>\s*<div class="lbl">\s*' + re.escape(stat_label) + r')'
    )
    updated, count = re.subn(pattern, r'\g<1>' + formatted + r'\g<2>', html, flags=re.DOTALL)
    if count > 0:
        print(f'  Updated {comp} / {stat_label} -> {formatted}')
    return updated


def update_table_stat(html, comp_name, new_value):
    """Update a <strong>VALUE</strong> in the social media table for a competitor."""
    if new_value is None:
        return html
    formatted = format_ch_number(new_value) if isinstance(new_value, int) else str(new_value)
    # This is trickier - skip for now, card stats are the primary display
    return html


def update_timestamp(html):
    """Update the last-updated timestamp in the header."""
    now = datetime.now()
    months_de = ['Januar','Februar','M\u00e4rz','April','Mai','Juni',
                 'Juli','August','September','Oktober','November','Dezember']
    date_str = f'{now.day}. {months_de[now.month-1]} {now.year}'
    html = re.sub(
        r'Stand: [^<]+',
        f'Stand: {date_str}',
        html
    )
    return html


def main():
    print('=== Competitor Dashboard Updater ===')
    print(f'Time: {datetime.now().isoformat()}\n')

    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

    # --- Instagram ---
    print('[Instagram] Scraping follower counts...')
    for comp, username in INSTAGRAM_PROFILES.items():
        print(f'  Checking @{username}...')
        followers = scrape_instagram_followers(username)
        posts = scrape_instagram_posts(username)
        html = update_stat_in_html(html, comp, 'Instagram', followers)
        html = update_stat_in_html(html, comp, 'Insta Posts', posts)

    # --- RSS Blog Posts ---
    print('\n[RSS] Fetching latest blog posts...')
    for comp, urls in RSS_FEEDS.items():
        print(f'  Fetching {comp}...')
        posts = fetch_rss_posts(urls)
        if posts:
            print(f'  Found {len(posts)} posts')
            for title, link in posts[:3]:
                print(f'    - {title[:60]}')
        else:
            print(f'  No posts found')

    # --- Timestamp ---
    print('\n[Timestamp] Updating...')
    html = update_timestamp(html)

    # --- Write ---
    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

    print('\nDone! Dashboard updated.')


if __name__ == '__main__':
    main()
