"""
DataTrail - Part A: The agent (TinyFish + data collection)
Team Apex Vanguard

Deliverable: scan_site(url) -> dict with
    policy_text, policy_url, tracker_findings (+ a few basic site facts)

Setup:
    pip install requests python-dotenv
    Create a .env file next to this script containing:
        TINYFISH_API_KEY=your_key_here
    (Never commit .env to GitHub. Add it to .gitignore.)

Run a quick test:
    python tinyfish_agent.py https://www.spotify.com
"""

import json
import os
import re
import sys
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()  # reads TINYFISH_API_KEY from .env so the key stays out of the code

TINYFISH_API_KEY = os.getenv("TINYFISH_API_KEY")
# Check this URL against the TinyFish docs / dashboard if you get a 404.
TINYFISH_RUN_URL = "https://agent.tinyfish.ai/v1/automation/run"

# ---------------------------------------------------------------------------
# Step 3: the goal we give the TinyFish web agent
# ---------------------------------------------------------------------------
GOAL_TEMPLATE = """
You are visiting a website as a normal visitor. Do NOT log in or sign up.

1. Find this site's privacy policy page (check the footer first, then look for
   links named "Privacy", "Privacy Policy", "Privacy Notice" or "Data Policy").
2. Open it and copy the FULL text of the policy (all sections, not a summary).
3. Note basic facts about the site: its name, whether a cookie banner or cookie
   settings link is visible, and whether a signup or login option exists.

Return JSON only, in exactly this shape:
{{
  "site_name": "string",
  "policy_url": "full URL of the privacy policy page, or null if not found",
  "policy_text": "full text of the policy, or null if not found",
  "has_cookie_banner": true or false,
  "has_signup_or_login": true or false
}}
"""

# ---------------------------------------------------------------------------
# Step 4: simple tracker check (plain Python, no AI needed)
# Compare the <script> domains a page loads against a list of known trackers.
# Extend this dictionary as you find more.
# ---------------------------------------------------------------------------
KNOWN_TRACKERS = {
    "google-analytics.com": "Google Analytics",
    "googletagmanager.com": "Google Tag Manager",
    "doubleclick.net": "Google Ads / DoubleClick",
    "googlesyndication.com": "Google Ads",
    "connect.facebook.net": "Meta (Facebook) Pixel",
    "facebook.net": "Meta (Facebook)",
    "analytics.twitter.com": "X (Twitter) Analytics",
    "ads-twitter.com": "X (Twitter) Ads",
    "snap.licdn.com": "LinkedIn Insight Tag",
    "analytics.tiktok.com": "TikTok Pixel",
    "static.hotjar.com": "Hotjar (session recording)",
    "script.hotjar.com": "Hotjar (session recording)",
    "cdn.segment.com": "Segment",
    "api.mixpanel.com": "Mixpanel",
    "cdn.mxpnl.com": "Mixpanel",
    "js.hs-scripts.com": "HubSpot",
    "bat.bing.com": "Microsoft Advertising",
    "clarity.ms": "Microsoft Clarity (session recording)",
    "criteo.com": "Criteo (ad retargeting)",
    "taboola.com": "Taboola (ads)",
    "outbrain.com": "Outbrain (ads)",
    "amplitude.com": "Amplitude",
    "fullstory.com": "FullStory (session recording)",
}


def normalize_url(url: str) -> str:
    """Add https:// if the user pasted something like 'example.com'."""
    url = url.strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    return url


def call_tinyfish(url: str, goal: str, timeout: int = 300) -> dict:
    """Send a goal to the TinyFish Web Agent and return the raw response JSON."""
    if not TINYFISH_API_KEY:
        raise RuntimeError("TINYFISH_API_KEY is missing. Add it to your .env file.")

    response = requests.post(
        TINYFISH_RUN_URL,
        headers={"X-API-Key": TINYFISH_API_KEY, "Content-Type": "application/json"},
        json={"url": url, "goal": goal},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def parse_result(raw: dict) -> dict:
    """
    The agent's answer lives under the 'result' key. Depending on the run it can
    be a dict already or a JSON string, so handle both.
    """
    result = raw.get("result", raw)
    if isinstance(result, str):
        # strip ```json fences if the model added them
        cleaned = re.sub(r"^```(?:json)?|```$", "", result.strip(), flags=re.M).strip()
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            result = {"policy_text": cleaned}
    return result if isinstance(result, dict) else {}


def check_trackers(url: str) -> list:
    """
    Download the page's HTML and list known trackers found in its script/iframe/
    img sources. Simple and fast; it will miss trackers loaded later by other
    scripts, which is fine for an MVP (say so in the demo).
    """
    try:
        html = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (DataTrail privacy scanner)"},
            timeout=20,
        ).text
    except requests.RequestException:
        return []

    sources = re.findall(r'(?:src|href)=["\']([^"\']+)["\']', html, flags=re.I)
    own_domain = urlparse(url).netloc.lower()
    findings, seen = [], set()

    for src in sources:
        host = urlparse(src if "//" in src else "//" + src).netloc.lower()
        if not host or host == own_domain:
            continue
        for tracker_domain, name in KNOWN_TRACKERS.items():
            if host == tracker_domain or host.endswith("." + tracker_domain):
                if name not in seen:
                    seen.add(name)
                    findings.append({"tracker": name, "domain": host})
    return findings


def scan_site(url: str) -> dict:
    """
    THE DELIVERABLE.
    Given a website URL, return:
    {
      "url": ...,
      "site_name": ...,
      "policy_url": ...,
      "policy_text": ...,
      "has_cookie_banner": ...,
      "has_signup_or_login": ...,
      "tracker_findings": [{"tracker": ..., "domain": ...}, ...],
      "error": None or "message"
    }
    Part B's analyze(policy_text) takes the 'policy_text' field from this.
    """
    url = normalize_url(url)
    output = {
        "url": url,
        "site_name": None,
        "policy_url": None,
        "policy_text": None,
        "has_cookie_banner": None,
        "has_signup_or_login": None,
        "tracker_findings": [],
        "error": None,
    }

    try:
        raw = call_tinyfish(url, GOAL_TEMPLATE)
        data = parse_result(raw)
        for key in ("site_name", "policy_url", "policy_text",
                    "has_cookie_banner", "has_signup_or_login"):
            output[key] = data.get(key)
        if not output["policy_text"]:
            output["error"] = "Agent could not find or read a privacy policy."
    except Exception as exc:  # keep the demo alive even if one site fails
        output["error"] = f"{type(exc).__name__}: {exc}"

    output["tracker_findings"] = check_trackers(url)
    return output


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "https://www.spotify.com"
    report = scan_site(target)
    preview = dict(report)
    if preview["policy_text"]:
        preview["policy_text"] = preview["policy_text"][:300] + "... [trimmed]"
    print(json.dumps(preview, indent=2))
