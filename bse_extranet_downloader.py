#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BSE Extranet Auto-Downloader  (pure requests + RSA login — no Selenium / UiPath)
=================================================================================
Real login flow discovered from JS analysis:
  1. GET / → load page (sets ASP.NET session cookie)
  2. Download CAPTCHA from Handler.ashx → solve with captcha_solver.py
  3. RSA-encrypt MemberCode, UserID, Password with BSE's public key
  4. POST to AjaxClass.aspx?a=getLogin  (AJAX login endpoint)
     Response: "Valid Login~mid~lid~SessionID"  OR  "Wrong Verification Code"  etc.
  5. Redirect to Extranet_Main.aspx  (member file browser)
  6. Navigate: EQ → Transaction → <Month-Year> → <dd-mm-yyyy>
  7. Check all checkboxes → Download → save ZIP

Dependencies:
  pip install requests beautifulsoup4 cryptography
  (opencv-python, torch already present for captcha_solver)
"""
import sys, io
# UTF-8 stdout for Windows console
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import json
import time
import base64
from pathlib import Path
from datetime import datetime

import cv2
import requests
from bs4 import BeautifulSoup

# ── RSA encryption (same as JSEncrypt used by BSE) ────────────────────────────
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# ── Local captcha solver ───────────────────────────────────────────────────────
def get_script_dir():
    import sys
    from pathlib import Path
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

SCRIPT_DIR = get_script_dir()
sys.path.insert(0, str(SCRIPT_DIR))
from captcha_solver import solve_captcha

# =============================================================================
# CONFIG
# =============================================================================

def load_config():
    config_path = SCRIPT_DIR / "config.json"
    if not config_path.exists() and SCRIPT_DIR.name == "dist":
        parent_path = SCRIPT_DIR.parent / "config.json"
        if parent_path.exists():
            config_path = parent_path
            
    if not config_path.exists():
        wp = SCRIPT_DIR / "workpath.txt"
        if wp.exists():
            config_path = Path(wp.read_text().strip()) / "config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

CONFIG    = load_config()
BSE_CFG   = CONFIG["config"]["BSE_WEBEXTRANET"]

BASE_URL  = "https://member.bseindia.com"   # no trailing slash
MEMBER_ID = BSE_CFG["Member_ID"]
USER_ID   = BSE_CFG["User_ID"]
PASSWORD  = BSE_CFG["User_Password"]
MAIN_FOLDER = BSE_CFG.get("MainFolder", "EQ")
SUB_FOLDER  = BSE_CFG.get("SubFolder", "Transaction")

# Date from config (Capital_Dates / FromDate → ddmmyyyy)
raw_date     = CONFIG["config"]["Dates"]["Capital_Dates"]["FromDate"]
dt           = datetime.strptime(raw_date, "%d%m%Y")
FROM_DATE    = dt.strftime("%d-%m-%Y")        # e.g. 25-05-2026
MONTH_FOLDER = dt.strftime("%b-%Y").upper()   # e.g. MAY-2026

# Save path (EQ Transaction)
EQ_TRANSACTION_DIR = CONFIG["config"]["Path"]["Equity"].get(
    "BSECM",
    str(SCRIPT_DIR / "downloads")
).rstrip("\\").rstrip("/")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

MAX_CAPTCHA_RETRIES = 10

# IMPORTANT: The captcha solver model was trained on 2x-upscaled screenshots
# from UiPath's browser. Raw server images (100x40) must be upscaled 2x
# before passing to solve_captcha() for accurate results.
CAPTCHA_UPSCALE = 2

# BSE RSA public key (from Extranet_Login_JS.js)
BSE_PUBLIC_KEY_B64 = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAhcdokMOGIuSP49QpAMeL"
    "oROTLhSokqvteENdJaUeF82oxQSs90w5fk+tIAcfQ6fgAvH4lGAvq6exnnQ9NuRs"
    "1Y3MPKGVijU0IHxsGur8yjAYhavCOP1zH9BkS4y5HBwWpzYBXAH/GE7yaUbl8X23"
    "4nHL6fDkgR1NJ+wJ8C/Pytpge25Gnq9ND6s8rwNzkoOEMlWuXky6GY/mioDU7rAA"
    "31JZ22PT+WEZcHX9cPeZ5sYlLFmnrYZixV5CQokPbIJxmrTCXQ2LTX3zuTqSiF5n"
    "Oeu70xnhY5ikHFk/inii1NduRGcylTKQ+L7RpkxZEmBcJG71ptmLaKRqPU6mhu5X"
    "BQIDAQAB"
)

# =============================================================================
# LOGGING
# =============================================================================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# =============================================================================
# RSA ENCRYPTION  (mirrors JSEncrypt's encrypt())
# =============================================================================

def rsa_encrypt(plaintext: str) -> str:
    """
    Encrypt plaintext with BSE's RSA public key using PKCS#1 v1.5 padding.
    JSEncrypt uses PKCS#1 v1.5 (same as OpenSSL RSA_public_encrypt with RSA_PKCS1_PADDING).
    Returns base64-encoded ciphertext.
    """
    # Build DER from raw modulus+exponent (SubjectPublicKeyInfo / SPKI format)
    pem = (
        "-----BEGIN PUBLIC KEY-----\n"
        + "\n".join(
            BSE_PUBLIC_KEY_B64[i:i+64]
            for i in range(0, len(BSE_PUBLIC_KEY_B64), 64)
        )
        + "\n-----END PUBLIC KEY-----"
    )
    pub_key = serialization.load_pem_public_key(
        pem.encode(), backend=default_backend()
    )
    ciphertext = pub_key.encrypt(
        plaintext.encode("utf-8"),
        asym_padding.PKCS1v15()
    )
    return base64.b64encode(ciphertext).decode("ascii")

# =============================================================================
# HTML HELPERS
# =============================================================================

def get_soup(html):
    return BeautifulSoup(html, "html.parser")

def get_hidden_fields(soup):
    data = {}
    for inp in soup.find_all("input", {"type": "hidden"}):
        name = inp.get("name")
        if name:
            data[name] = inp.get("value", "")
    return data

# =============================================================================
# POSTBACK  (ASP.NET __doPostBack)
# =============================================================================

CURRENT_HTML = ""

def postback(session, event_target, event_argument="", url=None, set_dir_id=True):
    """
    Fire ASP.NET postback on download.aspx.
    set_dir_id=True mirrors the JS SetID() call that sets hCurrDirID before __doPostBack.
    This is required for folder navigation — without it the server ignores the click.
    """
    global CURRENT_HTML
    if url is None:
        url = BASE_URL + "/download.aspx"  # file browser lives here
    soup = get_soup(CURRENT_HTML)
    data = get_hidden_fields(soup)
    data["__EVENTTARGET"]   = event_target
    data["__EVENTARGUMENT"] = event_argument
    # Mimic JS: SetID(id, 'FOLDER') sets hCurrDirID to folder id before postback
    if set_dir_id:
        data["hCurrDirID"] = event_target

    post_headers = {
        **HEADERS,
        "Referer": BASE_URL + "/download.aspx",
    }
    resp = session.post(url, data=data, headers=post_headers)
    CURRENT_HTML = resp.text
    return get_soup(resp.text)

# =============================================================================
# LOGIN
# =============================================================================

def login(session) -> bool:
    """
    Real BSE login flow:
    1. GET / to establish session cookie
    2. Download+solve CAPTCHA
    3. RSA-encrypt credentials
    4. POST to AjaxClass.aspx
    5. On success: GET Extranet_Main.aspx
    """
    global CURRENT_HTML

    log("Step 1: GET homepage (establish session cookie)")
    resp = session.get(BASE_URL + "/", headers=HEADERS)
    CURRENT_HTML = resp.text
    log(f"  Status: {resp.status_code}  Cookies: {list(session.cookies.keys())}")

    for attempt in range(1, MAX_CAPTCHA_RETRIES + 1):
        log(f"--- Login attempt {attempt}/{MAX_CAPTCHA_RETRIES} ---")

        # Step 2: Download CAPTCHA
        # Add random query param to force fresh CAPTCHA (mirrors RefreshCaptcha() in JS)
        cap_url = f"{BASE_URL}/Handler.ashx?query={time.time()}"
        log(f"  Downloading CAPTCHA: {cap_url}")
        cap_resp = session.get(cap_url, headers=HEADERS)

        cap_path = SCRIPT_DIR / f"_captcha_tmp_{attempt}.png"
        cap_path.write_bytes(cap_resp.content)
        log(f"  CAPTCHA saved ({len(cap_resp.content)} bytes)")

        # Step 3: Upscale CAPTCHA 2x then solve
        # The model was trained on 2x browser screenshots from UiPath,
        # so raw 100x40 server images need 2x upscale for best accuracy.
        try:
            raw_img = cv2.imread(str(cap_path))
            if raw_img is not None and CAPTCHA_UPSCALE != 1:
                h, w = raw_img.shape[:2]
                up_img = cv2.resize(raw_img, (w * CAPTCHA_UPSCALE, h * CAPTCHA_UPSCALE),
                                    interpolation=cv2.INTER_CUBIC)
                cv2.imwrite(str(cap_path), up_img)
                log(f"  Upscaled {w}x{h} -> {w*CAPTCHA_UPSCALE}x{h*CAPTCHA_UPSCALE}")
        except Exception as ue:
            log(f"  Upscale warning: {ue}")

        captcha_text, err = solve_captcha(str(cap_path))
        try:
            cap_path.unlink()
        except Exception:
            pass

        if err or not captcha_text:
            log(f"  Solver error: {err} -- retrying")
            time.sleep(1)
            continue

        log(f"  CAPTCHA solved: '{captcha_text}'")

        # Step 4: RSA-encrypt credentials
        log("  Encrypting credentials (RSA)...")
        try:
            enc_member = rsa_encrypt(MEMBER_ID)
            enc_user   = rsa_encrypt(USER_ID)
            enc_pwd    = rsa_encrypt(PASSWORD)
        except Exception as e:
            log(f"  RSA encryption failed: {e}")
            return False

        # Step 5: POST to AjaxClass.aspx (AJAX login endpoint)
        ajax_url = f"{BASE_URL}/AjaxClass.aspx"
        ajax_headers = {
            **HEADERS,
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": BASE_URL + "/",
        }
        ajax_data = {
            "a":           "getLogin",
            "UserID":      enc_user,
            "MemberID":    enc_member,
            "passwordval": enc_pwd,
            "Code":        captcha_text,
        }

        log(f"  Posting to {ajax_url}...")
        ajax_resp = session.post(ajax_url, data=ajax_data, headers=ajax_headers)
        raw = ajax_resp.text.strip()
        log(f"  AJAX response: {raw[:120]!r}")

        parts = [p.strip() for p in raw.split("~")]

        if parts[0] == "Valid Login":
            log("  LOGIN SUCCESS!")
            # Step 6: GET Extranet_Main.aspx (member file browser)
            log("  Loading Extranet_Main.aspx...")
            main_resp = session.get(
                BASE_URL + "/Extranet_Main.aspx",
                headers={**HEADERS, "Referer": BASE_URL + "/"}
            )
            CURRENT_HTML = main_resp.text
            log(f"  Main page status: {main_resp.status_code}  URL: {main_resp.url}")
            # The actual file browser is in download.aspx (loaded inside iframe)
            log("  Loading download.aspx (file browser)...")
            dl_resp = session.get(
                BASE_URL + "/download.aspx",
                headers={**HEADERS, "Referer": BASE_URL + "/Extranet_Main.aspx"}
            )
            CURRENT_HTML = dl_resp.text
            log(f"  download.aspx status: {dl_resp.status_code}")
            return True

        elif parts[0] == "Wrong Verification Code":
            log("  Wrong CAPTCHA -- retrying")
            time.sleep(1)
            # Refresh login page for fresh CAPTCHA
            resp = session.get(BASE_URL + "/", headers=HEADERS)
            CURRENT_HTML = resp.text
            continue

        elif parts[0] == "Password Page":
            log("  Password change required -- cannot proceed")
            return False

        else:
            log(f"  Unknown response: {raw[:200]!r} -- retrying")
            time.sleep(1)
            resp = session.get(BASE_URL + "/", headers=HEADERS)
            CURRENT_HTML = resp.text
            continue

    log("ERROR: All login attempts exhausted")
    return False

# =============================================================================
# DOWNLOAD FLOW  (EQ → Transaction → Month → Date → Download All)
# =============================================================================

def click_folder(session, soup, folder_name):
    """Find link by display text (without the folder icon prefix), fire postback."""
    import re as _re
    for link in soup.find_all("a"):
        txt = link.get_text(strip=True)
        # BSE puts a folder icon img before the text: "📁 EQ" → strip icon noise
        txt = txt.strip()
        if txt == folder_name:
            link_id = link.get("id", "")
            if link_id:
                event_target = link_id.replace("_", "$")
                log(f"  Clicking '{folder_name}' -> event_target={event_target}")
                return postback(session, event_target)
            # Fallback: extract event target from href
            href = link.get("href", "")
            m = _re.search(r"__doPostBack\('([^']+)'", href)
            if m:
                et = m.group(1)
                log(f"  Clicking '{folder_name}' via href -> {et}")
                return postback(session, et)
    log(f"  Folder not found: '{folder_name}'")
    log("  Available links: " + ", ".join(
        f"'{a.get_text(strip=True)}'"
        for a in soup.find_all("a")
        if a.get_text(strip=True)
    ))
    return None


def run_download(session) -> bool:
    global CURRENT_HTML

    soup = get_soup(CURRENT_HTML)

    # Check if we're on the right page
    links = [a.get_text(strip=True) for a in soup.find_all("a") if a.get_text(strip=True)]
    log(f"Current page links: {links[:15]}")

    # Verify main folder is visible
    if MAIN_FOLDER not in links:
        log(f"ERROR: {MAIN_FOLDER} folder not visible on current page")
        dbg = SCRIPT_DIR / "debug_main_page.html"
        dbg.write_text(CURRENT_HTML, encoding="utf-8")
        log(f"  Saved debug -> {dbg}")
        return False

    # Main Folder (e.g. EQ)
    log(f"Opening main folder: {MAIN_FOLDER}...")
    soup = click_folder(session, soup, MAIN_FOLDER)
    if soup is None:
        return False

    # Sub Folder (e.g. Transaction or Common)
    log(f"Opening sub folder: {SUB_FOLDER}...")
    soup = click_folder(session, soup, SUB_FOLDER)
    if soup is None:
        return False

    # Month folder  (e.g. MAY-2026)
    log(f"Opening month: {MONTH_FOLDER}...")
    soup = click_folder(session, soup, MONTH_FOLDER)
    if soup is None:
        return False

    # Date folder  (e.g. 25-05-2026)
    log(f"Opening date: {FROM_DATE}...")
    soup = click_folder(session, soup, FROM_DATE)
    if soup is None:
        return False

    # Find Download button
    download_btn = soup.find("input", {"value": "Download"})
    if not download_btn:
        log("ERROR: Download button not found")
        dbg = SCRIPT_DIR / "debug_date_folder.html"
        dbg.write_text(CURRENT_HTML, encoding="utf-8")
        log(f"  Saved debug -> {dbg}")
        return False

    download_name = download_btn.get("name")
    checkboxes    = soup.find_all("input", {"type": "checkbox"})
    log(f"Found {len(checkboxes)} checkboxes | Download button: '{download_name}'")

    # Build POST — check ALL checkboxes
    data = {}
    for inp in soup.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        itype = inp.get("type", "").lower()
        if itype == "submit":
            if name == download_name:
                data[name] = "Download"
        elif itype == "checkbox":
            data[name] = "on"
        else:
            data[name] = inp.get("value", "")

    log("Sending Download request...")
    post_headers = {
        **HEADERS,
        "Referer": BASE_URL + "/download.aspx",
    }
    resp = session.post(
        BASE_URL + "/download.aspx",
        data=data,
        headers=post_headers,
        stream=True,
        allow_redirects=True
    )

    log(f"Status      : {resp.status_code}")
    content_type = resp.headers.get("Content-Type", "")
    log(f"Content-Type: {content_type}")
    log(f"Final URL   : {resp.url}")

    if "text/html" in content_type.lower():
        log("WARNING: Got HTML instead of ZIP")
        dbg = SCRIPT_DIR / "debug_download_response.html"
        dbg.write_text(resp.text, encoding="utf-8")
        log(f"  Saved debug -> {dbg}")
        return False

    # Save ZIP inside a temp/ subfolder
    filename  = f"BSE_{MAIN_FOLDER}_{SUB_FOLDER}_{FROM_DATE}.zip"
    temp_dir  = os.path.join(EQ_TRANSACTION_DIR, "temp")
    save_path = os.path.join(temp_dir, filename)
    os.makedirs(temp_dir, exist_ok=True)

    log(f"Saving ZIP to temp folder: {save_path}")
    total = 0
    with open(save_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                total += len(chunk)

    log(f"Saved ZIP: {save_path}  ({total / 1024:.1f} KB)")
    
    # Auto-extract ZIP contents directly into the main save folder (EQ_TRANSACTION_DIR)
    try:
        import zipfile
        log(f"Extracting ZIP contents to main folder: {EQ_TRANSACTION_DIR} ...")
        with zipfile.ZipFile(save_path, 'r') as zip_ref:
            zip_ref.extractall(EQ_TRANSACTION_DIR)
        log("ZIP extraction completed successfully!")
    except Exception as ze:
        log(f"WARNING: Could not unzip downloaded file: {ze}")
        
    return True

# =============================================================================
# MAIN
# =============================================================================

def main():
    print()
    print("=" * 65)
    print("  BSE EXTRANET AUTO-DOWNLOADER  (pure requests + RSA login)")
    print("  EQ > Transaction > Month > Date > Download All")
    print("=" * 65)
    print()
    log(f"Member ID   : {MEMBER_ID}")
    log(f"User ID     : {USER_ID}")
    log(f"From Date   : {FROM_DATE}  |  Month: {MONTH_FOLDER}")
    log(f"Save path   : {EQ_TRANSACTION_DIR}")
    print()

    session = requests.Session()
    session.headers.update(HEADERS)

    # Login
    if not login(session):
        log("ABORTED: Login failed")
        sys.exit(1)

    print()

    # Download
    if run_download(session):
        print()
        log("ALL DONE  :)")
    else:
        print()
        log("DOWNLOAD FAILED  :(  -- check debug HTML files in script folder")
        sys.exit(1)


if __name__ == "__main__":
    main()
