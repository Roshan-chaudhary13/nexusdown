import os
import json
import time
import logging
import requests
import shutil
import gzip
import zipfile
from datetime import datetime as dt

# ================= LOAD CONFIG =================

with open("workpath.txt", "r") as f:
    workpath = f.read().strip()

with open(workpath + "\\config.json", "r") as f:
    json_data = json.load(f)

cfg = json_data["config"]["API_DETAILS"]["NSE_API"]

NSECMPath = json_data["config"]["Path"]["Equity"]["NSECM"]
FromDate = json_data["config"]["Dates"]["Capital_Dates"]["FromDate"]

MemberCode = cfg["MemberCode"]
LoginID = cfg["LoginID"]
Password = cfg["Password"]

version = cfg["version"]

# Replace version
for key in cfg:
    if isinstance(cfg[key], str):
        cfg[key] = cfg[key].replace("#version#", version)

LoginURL = cfg["LoginURL"]
LogoutURL = cfg["LogoutURL"]
Member_File_Download_Url = cfg["Member_File_Download_Url"]
Member_File_Get_Url = cfg["Member_File_Get_Url"]

Segment = 'CM'
MemberPathFolder = ["CEP/Dnld/"]

# ================= DATE =================

DD = FromDate[:2]
MM = FromDate[2:4]
YY = FromDate[-4:]

# ================= PATH =================

base_path = os.path.join(NSECMPath, FromDate)
temp_path = os.path.join(base_path, "temp")

os.makedirs(temp_path, exist_ok=True)
os.makedirs(base_path, exist_ok=True)

# ================= LOGGER =================

logging.basicConfig(
    filename=workpath + "\\logs\\"+ str(dt.today().strftime("%d%m%Y")) + ".log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ================= CLASS =================

class NSE:

    def login(self):
        res = requests.post(LoginURL, json={
            "memberCode": MemberCode,
            "loginId": LoginID,
            "password": Password
        })
        data = res.json()
        if data.get("status") != "success":
            raise Exception("Login failed")
        return data["token"]

    def get_files(self, token, folder):
        res = requests.get(
            f"{Member_File_Get_Url}segment=CM&folderPath=/{folder}",
            headers={"Authorization": f"Bearer {token}"}
        )
        return res.json().get("data", [])

    def download(self, token, folder, filename):
        url = f"{Member_File_Download_Url}segment=CM&folderPath=/{folder}&filename={filename}"

        for i in range(3):
            try:
                r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, stream=True)
                if r.status_code == 200:
                    return r.raw
            except:
                time.sleep(2)
        return None


# ================= AI FILE SELECTION =================

def select_best_cep(files):
    scored = []

    for f in files:
        name = f["name"]
        score = 0

        if "CEP" in name:
            score += 5
        if YY+MM+DD in name:
            score += 10

        score += len(name)

        scored.append((score, name))

    if not scored:
        return None

    scored.sort(reverse=True)
    return scored[0][1]


# ================= EXIST CHECK =================

def exists(filename):
    extracted = filename.replace(".gz", "").replace(".zip", "")
    return os.path.exists(os.path.join(base_path, extracted))


# ================= EXTRACT =================

def extract(file_path):
    name = os.path.basename(file_path)

    if name.endswith(".gz"):
        out = os.path.join(base_path, name.replace(".gz", ""))
        with gzip.open(file_path, 'rb') as f_in:
            with open(out, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

    elif name.endswith(".zip"):
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(base_path)

    else:
        shutil.move(file_path, os.path.join(base_path, name))
        return

    


# ================= CEP PROCESS =================

def process_cep(original_filename):

    # Step 1: Get extracted file name (remove .gz if exists)
    extracted_name = original_filename.replace(".gz", "")
    input_file = os.path.join(base_path, extracted_name)

    if not os.path.exists(input_file):
        print("❌ Extracted file not found:", input_file)
        logging.error(f"Extracted file not found: {input_file}")
        return

    # Step 2: Create new renamed filename
    new_name = extracted_name.replace("_T_", "_")
    output_file = os.path.join(base_path, new_name)

    try:
        # Step 3: Read file
        with open(input_file, "r") as f:
            lines = f.readlines()

        # Step 4: Fix header
        if lines and lines[0].startswith("10,"):
            parts = lines[0].strip().split(",")
            if len(parts) >= 4:
                lines[0] = f"10,ACEP,{','.join(parts[1:])}\n"

        # Step 5: Write renamed file
        with open(output_file, "w") as f:
            f.writelines(lines)

        # Step 6: Delete old file (IMPORTANT)
        if input_file != output_file:
            os.remove(input_file)

        # Step 7: Save updated name
        with open("CEP_File_update.txt", "w") as f:
            f.write(new_name)

        print("✅ Rename + header update done:", new_name)
        logging.info(f"Rename + header update done: {new_name}")

    except Exception as e:
        print("❌ Error processing CEP:", e)
        logging.error(f"Error processing CEP:{e}")


# ================= MAIN =================

def main():

    obj = NSE()

    token = obj.login()

    for folder in MemberPathFolder:

        files = obj.get_files(token, folder)

        best = select_best_cep(files)

        if not best:
            print("No CEP file found")
            logging.error("No CEP file found")
            return

        logging.info(f"Selected CEP: {best}")

        if exists(best):
            print("Already exists:", best)
            logging.info(f"Already exists: {best}")
            return

        raw = obj.download(token, folder, best)

        if not raw:
            print("Download failed")
            logging.error("Download failed")
            return

        temp_file = os.path.join(temp_path, best)

        with open(temp_file, "wb") as f:
            shutil.copyfileobj(raw, f)

        print("Downloaded:", best)
        logging.info(f"Downloaded: {best}")

        extract(temp_file)

        # Save filename
        with open("CEP_File.txt", "w") as f:
            f.write(best)

        process_cep(best)



# ================= RUN =================

if __name__ == "__main__":
    main()