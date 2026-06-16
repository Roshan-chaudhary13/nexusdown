import os
import json
import logging
import requests
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from time import sleep
import shutil

# Auto-extract zip/gz helper
def auto_extract_file(file_path, dest_dir):
    try:
        import zipfile
        import gzip
        
        if file_path.lower().endswith('.zip'):
            print(f"Extracting ZIP: {file_path} to {dest_dir} ...")
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(dest_dir)
            print("ZIP extraction completed successfully!")
            
        elif file_path.lower().endswith('.gz'):
            dest_file = file_path[:-3]
            print(f"Decompressing GZ: {file_path} -> {dest_file} ...")
            with gzip.open(file_path, 'rb') as f_in:
                with open(dest_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            print("GZ decompression completed successfully!")
    except Exception as e:
        print(f"WARNING: Could not extract/unzip {file_path}: {e}")

# ================= CONFIG LOADER =================

def load_config():
    with open("workpath.txt", "r") as f:
        workpath = f.read().strip()

    with open(os.path.join(workpath, "config.json"), "r") as f:
        config = json.load(f)

    return workpath, config
workpath, config = load_config()
NSECDPath = config["config"]["Path"]["CDS"]["NSECD"]
FromDate = config["config"]["Dates"]["Capital_Dates"]["FromDate"]

# ================= LOGGER =================

def setup_logger(workpath, from_date):
    log_dir = os.path.join(workpath, "logs")
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        filename=os.path.join(log_dir, f"NSE_CD_DOWNLOAD_{from_date}.log"),
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )


# ================= RETRY =================

def retry(func, retries=3, delay=2):
    for i in range(retries):
        try:
            return func()
        except Exception as e:
            logging.error(f"Retry {i+1} failed: {e}")
            print(f"Retry {i+1} failed: {e}")
            sleep(delay)
    raise Exception("Max retries exceeded")


# ================= NSE CLIENT =================

class NSEClient:

    def __init__(self, cfg):
        self.cfg = cfg
        self.token = None
        self.lock = threading.Lock()

    def login(self):
        logging.info("Logging in...")
        print("Logging in...")
        res = requests.post(
            self.cfg["LoginURL"],
            json={
                "memberCode": self.cfg["MemberCode"],
                "loginId": self.cfg["LoginID"],
                "password": self.cfg["Password"]
            },
            timeout=15
        )
        data = res.json()

        if data.get("status") != "success":
            raise Exception("Login Failed")

        self.token = data["token"]
        # Write to Token.txt so it's shared across segments
        with open("Token.txt", "w") as f:
            f.write(self.token)
        logging.info("Login successful")
        print("Login successful")

    def refresh_token(self, old_token=None):
        with self.lock:
            current_token = ""
            if os.path.exists("Token.txt"):
                try:
                    with open("Token.txt", "r") as f:
                        current_token = f.read().strip()
                except Exception:
                    pass

            if old_token and current_token and current_token != old_token:
                self.token = current_token
                return current_token

            print("\n[API] Session expired. Re-logging in currency derivatives client...")
            try:
                self.login()
                return self.token
            except Exception as e:
                print(f"Currency Derivatives re-login failed: {e}")
            return None

    def headers(self):
        if os.path.exists("Token.txt"):
            try:
                with open("Token.txt", "r") as f:
                    t = f.read().strip()
                    if t:
                        self.token = t
            except Exception:
                pass
        return {"Authorization": f"Bearer {self.token}"}

    def get_files(self, url, folder):
        import sys
        if getattr(sys, 'abort_requested', False):
            print("\n[ABORT] Abort requested by user. Terminating process...")
            sys.exit(0)
            
        def call():
            res = requests.get(
                f"{url}segment=CD&folderPath=/{folder}",
                headers=self.headers(),
                timeout=15
            )
            if res.status_code in [400, 401, 403]:
                print("Currency derivatives listing failed with status. Re-logging in...")
                self.refresh_token(old_token=self.token)
                res = requests.get(
                    f"{url}segment=CD&folderPath=/{folder}",
                    headers=self.headers(),
                    timeout=15
                )
            return res.json().get("data", [])

        return retry(call)

    def download_file(self, url, folder, filename, save_path):
        import sys
        if getattr(sys, 'abort_requested', False):
            return
            
        def call():
            if getattr(sys, 'abort_requested', False):
                return
            dl_url = f"{url}segment=CD&folderPath=/{folder}&filename={filename}"
            res = requests.get(dl_url, headers=self.headers(), stream=True, timeout=15)

            if res.status_code in [400, 401, 403]:
                print(f"Currency derivatives download of {filename} failed. Re-logging in...")
                self.refresh_token(old_token=self.token)
                res = requests.get(dl_url, headers=self.headers(), stream=True, timeout=15)

            if res.status_code != 200:
                raise Exception(f"Failed {filename}")

            with open(save_path, "wb") as f:
                for chunk in res.iter_content(8192):
                    if getattr(sys, 'abort_requested', False):
                        return
                    f.write(chunk)

        retry(call)
        logging.info(f"{filename} : Downloaded")
        print(f"{filename} : Downloaded")


# ================= FILE FILTER =================

import re

def smart_filter(files, from_date, rev_date, targets=None):
    filtered = []
    for f in files:
        name = f.get("name", "").lower()
        if name == "cd_contract" or name == "contract.gz" or name == "contract":
            filtered.append(f)
            continue
        if targets:
            check_name = name
            if check_name.endswith(".gz"):
                check_name = check_name[:-3]
            elif check_name.endswith(".zip"):
                check_name = check_name[:-4]
            matched = False
            for regex in targets:
                if re.match(regex, check_name):
                    matched = True
                    break
            if matched:
                filtered.append(f)
        else:
            keywords = [from_date, rev_date]
            if any(k.lower() in name for k in keywords):
                filtered.append(f)
    return filtered


# ================= DOWNLOAD ENGINE =================

def download_parallel(client, files, folder, base_path, url):

    def task(f):
        filename = f["name"]
        
        # Save directly to category subfolder
        subfolder = folder.replace("/", "\\").strip("\\")
        dest_dir = os.path.join(base_path, subfolder)
        os.makedirs(dest_dir, exist_ok=True)
        
        file_path = os.path.join(dest_dir, filename)
        Repl_File = filename.replace(".gz", "").replace(".zip", "")
        unzipped_path = os.path.join(dest_dir, Repl_File)

        if not os.path.exists(file_path) and not os.path.exists(unzipped_path):
            try:
                client.download_file(url, folder, filename, file_path)
                auto_extract_file(file_path, dest_dir)
            except Exception as e:
                logging.error(f"{filename} failed: {e}")
                print(f"{filename} failed: {e}")
        else:
            logging.info(f"{filename} : Already exists")
            print(f"{filename} : Already exists")
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(task, files)


# ================= MAIN PROCESS =================

def process():

    workpath, config = load_config()
    NSECDPath = config["config"]["Path"]["CDS"]["NSECD"]
    FromDate = config["config"]["Dates"]["Capital_Dates"]["FromDate"]
    MemberFolders = config["config"]["API_DETAILS"]["NSE_API"]["Path_FO_Member"]
    CommonFolders = config["config"]["API_DETAILS"]["NSE_API"]["Path_FO_Common"]
    urls = config["config"]["API_DETAILS"]["NSE_API"]
    version = urls["version"]
    LoginURL = urls["LoginURL"].replace("#version#", version)
    MemberGetURL = urls["Member_File_Get_Url"].replace("#version#", version)
    CommonGetURL = urls["Common_File_Get_Url"].replace("#version#", version)
    MemberDL = urls["Member_File_Download_Url"].replace("#version#", version)
    CommonDL = urls["Common_File_Download_Url"].replace("#version#", version)

    cfg = {
        "LoginURL": LoginURL,
        "MemberCode": urls["MemberCode"],
        "LoginID": urls["LoginID"],
        "Password": urls["Password"]
    }

    setup_logger(workpath, FromDate)

    # Date formatting
    DD = FromDate[0:2]
    MM = FromDate[2:4]
    YY = FromDate[-4:]
    RevDate = YY + MM + DD

    NextDate = config["config"]["Dates"]["Capital_Dates"].get("NextDate", "")
    CD_NSE_Config = config["config"].get("Master_Files", {}).get("CD_NSE", {})

    def resolve_pattern_to_regex(pattern, from_date, next_date):
        if not pattern:
            return None
        
        pat = pattern.lower()
        if pat == "*" or pat == "all":
            dd = from_date[0:2]
            mm = from_date[2:4]
            yyyy = from_date[4:8]
            rev_from_date = yyyy + mm + dd
            return f".*(?:{from_date}|{rev_from_date}).*"
        
        # Resolve dates
        dd = from_date[0:2]
        mm = from_date[2:4]
        yyyy = from_date[4:8]
        rev_from_date = yyyy + mm + dd
        
        rev_next_date = ""
        if next_date and len(next_date) == 8:
            next_dd = next_date[0:2]
            next_mm = next_date[2:4]
            next_yyyy = next_date[4:8]
            rev_next_date = next_yyyy + next_mm + next_dd
            
        pat = pat.replace("#fromdate#", from_date)
        pat = pat.replace("#revfromdate#", rev_from_date)
        pat = pat.replace("#nextdate#", next_date)
        pat = pat.replace("#revnextdate#", rev_next_date)
        pat = pat.replace("#dd#", dd)
        pat = pat.replace("#mm#", mm)
        
        # Replace _cm_ and _tm_ with a token to be replaced by regex later
        pat = pat.replace("_cm_", "_tcm_")
        pat = pat.replace("_tm_", "_tcm_")
        
        # Replace #nsecode# with a token
        pat = pat.replace("#nsecode#", "nsecodewild")
        
        # Escape for regex
        pat_esc = re.escape(pat)
        
        # Replace tokens with real regex patterns
        pat_esc = pat_esc.replace("_tcm_", "_(?:cm|tm)_")
        pat_esc = pat_esc.replace("nsecodewild", "[a-z0-9]+")
        
        return "^" + pat_esc + "$"

    cd_mode = config["config"].get("Extraction_Modes", {}).get("CDS", "Custom")

    target_files = []
    if cd_mode == "Custom" and CD_NSE_Config:
        for key, val in CD_NSE_Config.items():
            if key.startswith("UDIFF_") or not val:
                continue
            regex = resolve_pattern_to_regex(val, FromDate, NextDate)
            if regex:
                target_files.append(regex)

    base_path = os.path.join(NSECDPath, FromDate)
    temp_path = os.path.join(base_path, "temp")

    os.makedirs(temp_path, exist_ok=True)

    client = NSEClient(cfg)
    client.login()

    # ===== MEMBER FILES =====
    for folder in MemberFolders:

        logging.info(f"**************Processing Member Folder: {folder} ****************")
        print(f"**************Processing Member Folder: {folder} ****************")

        files = client.get_files(MemberGetURL, folder)
        filtered = smart_filter(files, FromDate, RevDate, targets=target_files)

        download_parallel(client, filtered, folder, base_path, MemberDL)

    # ===== COMMON FILES =====
    for folder in CommonFolders:
        logging.info(f"**************Processing Common Folder: {folder} **************")
        print(f"**************Processing Common Folder: {folder} **************")

        files = client.get_files(CommonGetURL, folder)
        filtered = smart_filter(files, FromDate, RevDate, targets=target_files)

        download_parallel(client, filtered, folder, base_path, CommonDL)

    # Print summary of missing/not downloaded files
    print("\n==================================================")
    print("  DOWNLOAD RUN SUMMARY (MISSING/NOT DOWNLOADED)")
    print("==================================================")
    logging.info("DOWNLOAD RUN SUMMARY (MISSING/NOT DOWNLOADED)")

    local_files = set()
    for root, dirs, files in os.walk(os.path.join(NSECDPath, FromDate)):
        for f in files:
            name = f.lower()
            if name.endswith(".gz"):
                name = name[:-3]
            elif name.endswith(".zip"):
                name = name[:-4]
            local_files.add(name)
            
    missing_count = 0
    if CD_NSE_Config:
        for key, val in CD_NSE_Config.items():
            if key.startswith("UDIFF_") or not val:
                continue
            regex = resolve_pattern_to_regex(val, FromDate, NextDate)
            if not regex:
                continue
                
            found_local = False
            for local_f in local_files:
                if re.match(regex, local_f):
                    found_local = True
                    break
                    
            if not found_local:
                resolved_display = val.lower()
                dd = FromDate[0:2]
                mm = FromDate[2:4]
                yyyy = FromDate[4:8]
                rev_from_date = yyyy + mm + dd
                
                rev_next_date = ""
                if NextDate and len(NextDate) == 8:
                    next_dd = NextDate[0:2]
                    next_mm = NextDate[2:4]
                    next_yyyy = NextDate[4:8]
                    rev_next_date = next_yyyy + next_mm + next_dd
                    
                resolved_display = resolved_display.replace("#fromdate#", FromDate)
                resolved_display = resolved_display.replace("#revfromdate#", rev_from_date)
                resolved_display = resolved_display.replace("#nextdate#", NextDate)
                resolved_display = resolved_display.replace("#revnextdate#", rev_next_date)
                resolved_display = resolved_display.replace("#dd#", dd)
                resolved_display = resolved_display.replace("#mm#", mm)
                resolved_display = resolved_display.replace("#nsecode#", urls["MemberCode"].lower())
                
                print(f"[MISSING] {key} : {resolved_display}")
                logging.info(f"[MISSING] {key} : {resolved_display}")
                missing_count += 1
                
    if missing_count == 0:
        print("All configured files are available locally!")
        logging.info("All configured files are available locally!")
    print("==================================================\n")

    logging.info("Process Completed Successfully")
    print("Process Completed Successfully")


# ================= RUN =================

if __name__ == "__main__":
    try:
        process()
        try:
            pathtemp = os.path.join(NSECDPath, FromDate, 'temp')
            os.makedirs(pathtemp, exist_ok=True)
            fileTemp = open(os.path.join(pathtemp, "temp.xls"), "w+")
            fileTemp.write("xyz")
            fileTemp.close()
        except Exception:
            pass
    except Exception as e:
        logging.error(f"Fatal Error: {e}")
        print("Execution Failed:", e)
        try:
            pathtemp = os.path.join(NSECDPath, FromDate, 'temp')
            os.makedirs(pathtemp, exist_ok=True)
            fileTemp = open(os.path.join(pathtemp, "temp.xls"), "w+")
            fileTemp.write("xyz")
            fileTemp.close()
        except Exception:
            pass