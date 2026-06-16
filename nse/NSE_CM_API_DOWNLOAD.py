import time
import requests
import json
import shutil
import os
import logging
from datetime import datetime as dt

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
#*****************************Variable ***************************************

a_file = open("workpath.txt", "r")
workpath = a_file.read()
a_file.close()

json_file = open(workpath + "\\config.json", "r")
json_data = json.load(json_file)
json_file.close()

NSECMPath=json_data["config"]["Path"]["Equity"]["NSECM"]
NSECode=json_data["config"]["Member_Code"]["NSE_CODE"]
FromDate=json_data["config"]["Dates"]["Capital_Dates"]["FromDate"]
NextDate=json_data["config"]["Dates"]["Capital_Dates"].get("NextDate", "")
MemberCode=json_data["config"]["API_DETAILS"]["NSE_API"]["MemberCode"]
LoginID=json_data["config"]["API_DETAILS"]["NSE_API"]["LoginID"]
Password=json_data["config"]["API_DETAILS"]["NSE_API"]["Password"]

import re

CM_NSE_Config = json_data["config"].get("Master_Files", {}).get("CM_NSE", {})

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

CM_Mode = json_data["config"].get("Extraction_Modes", {}).get("CM", "Custom")

# Pre-compute resolved target regexes
target_files = []
if CM_Mode == "Custom" and CM_NSE_Config:
    for key, val in CM_NSE_Config.items():
        if key.startswith("UDIFF_") or not val:
            continue
        regex = resolve_pattern_to_regex(val, FromDate, NextDate)
        if regex:
            target_files.append(regex)

def is_target_file(server_filename, targets):
    if not targets:
        return True # Fallback if config is missing/empty
    
    name = server_filename.lower()
    if name.endswith(".gz"):
        name = name[:-3]
    elif name.endswith(".zip"):
        name = name[:-4]
        
    for regex in targets:
        if re.match(regex, name):
            return True
    return False

version=json_data["config"]["API_DETAILS"]["NSE_API"]["version"]
LoginURL = json_data["config"]["API_DETAILS"]["NSE_API"]["LoginURL"]
LogoutURL = json_data["config"]["API_DETAILS"]["NSE_API"]["LogoutURL"]
Member_File_Download_Url = json_data["config"]["API_DETAILS"]["NSE_API"]["Member_File_Download_Url"]
Common_File_Download_Url = json_data["config"]["API_DETAILS"]["NSE_API"]["Common_File_Download_Url"]
Member_File_Get_Url = json_data["config"]["API_DETAILS"]["NSE_API"]["Member_File_Get_Url"]
Common_File_Get_Url = json_data["config"]["API_DETAILS"]["NSE_API"]["Common_File_Get_Url"]

MemberPathFolder=json_data["config"]["API_DETAILS"]["NSE_API"]["Path_CM_Member"]
CommonPathFolder=json_data["config"]["API_DETAILS"]["NSE_API"]["Path_CM_Common"]

Segment='CM'


#*************************Replece***************************

LoginURL=str(LoginURL).replace("#version#",version)
LogoutURL=str(LogoutURL).replace("#version#",version)
Member_File_Download_Url=str(Member_File_Download_Url).replace("#version#",version)
Common_File_Download_Url=str(Common_File_Download_Url).replace("#version#",version)
Member_File_Get_Url=str(Member_File_Get_Url).replace("#version#",version)
Common_File_Get_Url=str(Common_File_Get_Url).replace("#version#",version)



shortdate = FromDate[0:4]
DD = FromDate[0:2]
MM = FromDate[2:4]
YY = FromDate[-4:]

RevFromDate=YY+MM+DD
#**************************Path Variable***********************************

pathtemp = (NSECMPath)+str(FromDate)+ '\\temp'

tempPath=os.path.exists((NSECMPath)+str(FromDate)+ '\\temp')
datePath=os.path.exists((NSECMPath)+str(FromDate))

# logging.basicConfig(filename=workpath + "\logs\script_logs_" + str(dt.today().strftime("%d%m%Y")) + ".log",level=logging.DEBUG)
logging.basicConfig(filename=workpath+'\logs\\NSE_CM_API_DOWNLOAD_'+str(FromDate)+'.log', level=logging.INFO, format='[ %(asctime)s] - [%(levelname)s ] - %(message)s')

if not datePath==True:
    os.makedirs(NSECMPath+FromDate, exist_ok=True)

if not tempPath==True:
    os.makedirs(pathtemp, exist_ok=True)


#****************** List of Folder Name *************

listCELList=[]



#************ OOPS ***************
import threading

class NSE_FILE_CLASS:

    def __init__(self):
        self.LoginURL = None
        self.LogoutURL = None
        self.MemberCode = None
        self.LoginID = None
        self.Password = None
        self.lock = threading.Lock()

    def get_current_token(self, fallback_token):
        if os.path.exists("Token.txt"):
            try:
                with open("Token.txt", "r") as f:
                    t = f.read().strip()
                    if t:
                        return t
            except Exception:
                pass
        return fallback_token

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
                # Token was already refreshed by another thread!
                return current_token

            print("\n[API] Session expired or invalid. Attempting transparent re-login...")
            logging.info("Session expired or invalid. Attempting transparent re-login...")
            try:
                if current_token and self.LogoutURL:
                    self.Logout(current_token, self.LogoutURL, self.MemberCode, self.LoginID)
                
                # Login to get fresh token
                Login_response = self.Login(self.LoginURL, self.MemberCode, self.LoginID, self.Password)
                if Login_response and Login_response.get("status") == "success":
                    new_token = Login_response["token"]
                    with open("Token.txt", "w") as f:
                        f.write(new_token)
                    print("[API] Session refreshed successfully!")
                    logging.info("Session refreshed successfully!")
                    return new_token
            except Exception as e:
                print(f"[API ERROR] Session refresh failed: {e}")
                logging.error(f"Session refresh failed: {e}")
            return None

    def Logout(self,Logout_Token_Param,LogoutURL, MemberCode, LoginID):
        try:
            url = LogoutURL
            payload = json.dumps({
                "memberCode": "" + MemberCode + "",
                "loginId": "" + LoginID + ""
            })
            headers = {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + str(Logout_Token_Param),
                'Cookie': 'HttpOnly'
            }
            response = requests.request("POST", url, headers=headers, data=payload, timeout=15)
            return response.json()
        except Exception as e:
            print(e)
            return "Error"
            logging.error( " ------- NSECM API -----"+str(e))

    def Login(self,Login_url, MemberCode, LoginID, PasswordEnc):
        response=''
        try:
            print("Logging in...")
            logging.info(" Logging in...")
            url = Login_url
            payload = json.dumps({
                "memberCode": "" + MemberCode + "",
                "loginId": "" + LoginID + "",
                "password": "" + PasswordEnc + ""
            })
            headers = {
                'Content-Type': 'application/json'
            }
            response = requests.request("POST", url, headers=headers, data=payload, timeout=15)
            return response.json()
        except Exception as e:
            print(e)
            logging.error(" ------- NSECM API -----"+str(e))
            return response

    def File_Download(self,Login_Token_Param, FileDownloadURL_Param, Segment_Param, FolderPath_Param, FileName_Param):
        import sys
        if getattr(sys, 'abort_requested', False):
            print("\n[ABORT] Abort requested by user. Terminating process...")
            sys.exit(0)
            
        token = self.get_current_token(Login_Token_Param)
        for attempt in range(2):
            try:
                Download_URL = FileDownloadURL_Param + "segment=" + Segment_Param + '&folderPath=/' + FolderPath_Param + '&filename=' + FileName_Param
                logging.info(Download_URL)
                payload = {}
                headers = {
                    'Authorization': 'Bearer ' + str(token),
                    'Cookie': 'HttpOnly'
                }
                response = requests.request("GET", Download_URL, headers=headers, data=payload, stream=True, timeout=15)
                
                if response.status_code == 200:
                    return response.raw
                elif response.status_code in [400, 401, 403] and attempt == 0:
                    print(f"Download status {response.status_code}. Auto-refreshing session...")
                    token = self.refresh_token(old_token=token)
                    if not token:
                        return "error"
                else:
                    return "error"
            except Exception as e:
                print(e)
                if attempt == 0:
                    print("Download exception. Auto-refreshing session...")
                    token = self.refresh_token(old_token=token)
                    if not token:
                        return "error"
                else:
                    logging.error(" ------- NSECM API -----" + str(e))
                    return "error"

    def Get_All_FileName(self,AuthToken_Param, File_Get_Url_Param, Segment_Param, MemberFolderPath_Param):
        import sys
        if getattr(sys, 'abort_requested', False):
            print("\n[ABORT] Abort requested by user. Terminating process...")
            sys.exit(0)
            
        token = self.get_current_token(AuthToken_Param)
        for attempt in range(2):
            try:
                GetFolderURL = File_Get_Url_Param + 'segment=' + Segment_Param + '&folderPath=/' + MemberFolderPath_Param
                payload = {}
                headers = {
                    'Authorization': 'Bearer ' + str(token),
                    'Cookie': 'HttpOnly'
                }
                response = requests.request("GET", GetFolderURL, headers=headers, data=payload, timeout=15)
                datajson = response.json()
                
                if datajson.get("status") == "error" or "data" not in datajson:
                    if attempt == 0:
                        print("List files failed. Auto-refreshing session...")
                        token = self.refresh_token(old_token=token)
                        if not token:
                            return "Error"
                        continue
                    else:
                        return "Error"
                return datajson['data']
            except Exception as e:
                print(e)
                if attempt == 0:
                    print("List files exception. Auto-refreshing session...")
                    token = self.refresh_token(old_token=token)
                    if not token:
                        return "Error"
                else:
                    logging.error(" ------- NSECM API -----" + str(e))
                    return "Error"

#************Objects*************
Class_Object=NSE_FILE_CLASS()
Class_Object.LoginURL = LoginURL
Class_Object.LogoutURL = LogoutURL
Class_Object.MemberCode = MemberCode
Class_Object.LoginID = LoginID
Class_Object.Password = Password


#****************Calling*********
TokenSession = ""
if os.path.exists("Token.txt"):
    try:
        with open("Token.txt", "r") as tokenFile:
            TokenSession = tokenFile.read().strip()
    except Exception:
        pass

Login_status = ""
Login_token = ""

if TokenSession:
    print("Reusing cached session token.")
    logging.info("Reusing cached session token.")
    Login_status = "success"
    Login_token = TokenSession
else:
    print("No cached token found. Logging in...")
    logging.info("No cached token found. Logging in...")
    Login_response = Class_Object.Login(LoginURL, MemberCode, LoginID, Password)
    try:
        Login_status = Login_response.get("status", "")
    except Exception as e:
        print(e)
        logging.error(" ------- NSECM API -----" + str(e))
        
    if Login_status == "success":
        Login_token = Login_response["token"]
        try:
            with open("Token.txt", "w") as tokenFile:
                tokenFile.write(Login_token)
        except Exception:
            pass
        print("Logged in successfully. Token saved.")
        logging.info("Logged in successfully. Token saved.")
    else:
        print(f"Login failed: {Login_status}")
        logging.error(f"Login failed: {Login_status}")

if Login_status == "success":
    FileNameList = []

    #*********************MEMEBER FILES****************
    def MemberFiles():
        for MemberFolderName in MemberPathFolder:
            print("****************************" + MemberFolderName + "******************************")
            logging.info(str("****************************" + MemberFolderName + "******************************"))
            if "CEP" in MemberFolderName:
                FileNameList = Class_Object.Get_All_FileName(Login_token, Member_File_Get_Url, Segment, MemberFolderName)
                if isinstance(FileNameList, list):
                    try:
                        listCELList = []
                        for i in FileNameList:
                            MemberFileName = i['name']
                            FileType = i["type"]
                            if FileType == "File":
                                if MemberCode+"_CEP" + str(YY) + str(MM) + str(DD) in MemberFileName and "CEP" in MemberFileName:
                                    listCELList.append(MemberFileName)
                        
                        if len(listCELList) >= 1:
                            listCELList_final = sorted(listCELList)
                            FileCEP = listCELList_final[-1]
                            
                            subfolder = MemberFolderName.replace("/", "\\").strip("\\")
                            dest_dir = os.path.join(NSECMPath, FromDate, subfolder)
                            os.makedirs(dest_dir, exist_ok=True)
                            file_path = os.path.join(dest_dir, FileCEP)
                            
                            Repl_File = FileCEP.replace(".gz", "").replace(".zip", "")
                            unzipped_path = os.path.join(dest_dir, Repl_File)
                            
                            FileExistTemp = os.path.exists(file_path)
                            FileExist = os.path.exists(unzipped_path)
                            
                            if not FileExist and not FileExistTemp:
                                File_Down_Resp = Class_Object.File_Download(Login_token, Member_File_Download_Url, Segment, MemberFolderName, FileCEP)
                                if File_Down_Resp != 'error':
                                    try:
                                        with open(file_path, 'wb') as out_file:
                                            shutil.copyfileobj(File_Down_Resp, out_file)
                                            print(FileCEP + " Downloading...")
                                            logging.info(FileCEP + " Downloading...")
                                        auto_extract_file(file_path, dest_dir)
                                        
                                        #*********Write CEP file registration*****************
                                        try:
                                            json_data["config"]["CEP_File"]["CEP_File_Name"] = FileCEP
                                            with open(os.path.join(workpath, "config.json"), "w") as json_file:
                                                json.dump(json_data, json_file, indent=8)
                                        except Exception as je:
                                            logging.error("Failed to write to config.json for CEP: " + str(je))
                                            
                                        try:
                                            with open("CEP_File.txt", "w") as writeFile:
                                                writeFile.write(FileCEP)
                                        except Exception as fe:
                                            logging.error("Failed to write to CEP_File.txt: " + str(fe))
                                        #*****************************************************
                                    except Exception as e:
                                        logging.error(" ------- NSECM API -----" + str(e))
                                        print(e)
                                else:
                                    print(FileCEP + " Error in files")
                                    logging.error(FileCEP + " Error in files")
                            else:
                                print(FileCEP + " exists")
                                logging.info(FileCEP + " exists")
                    except Exception as e:
                        logging.error(" ------- NSECM API -----" + str(e))
                        print(e)
            else:
                FileNameList = Class_Object.Get_All_FileName(Login_token, Member_File_Get_Url, Segment, MemberFolderName)
                if isinstance(FileNameList, list):
                    from concurrent.futures import ThreadPoolExecutor
                    
                    def download_task(i):
                        MemberFileName = i['name']
                        FileType = i["type"]
                        if FileType == "File":
                            is_target = is_target_file(MemberFileName, target_files) if target_files else (FromDate in MemberFileName or RevFromDate in MemberFileName)
                            if is_target:
                                # Save directly to category subfolder
                                subfolder = MemberFolderName.replace("/", "\\").strip("\\")
                                dest_dir = os.path.join(NSECMPath, FromDate, subfolder)
                                os.makedirs(dest_dir, exist_ok=True)
                                
                                file_path = os.path.join(dest_dir, MemberFileName)
                                Repl_File = MemberFileName.replace(".gz", "").replace(".zip", "")
                                unzipped_path = os.path.join(dest_dir, Repl_File)
                                
                                FileExistTemp = os.path.exists(file_path)
                                FileExist = os.path.exists(unzipped_path)
                                
                                if not FileExist and not FileExistTemp:
                                    File_Down_Resp = Class_Object.File_Download(Login_token, Member_File_Download_Url, Segment, MemberFolderName, MemberFileName)
                                    if File_Down_Resp != 'error':
                                        try:
                                            with open(file_path, 'wb') as out_file:
                                                shutil.copyfileobj(File_Down_Resp, out_file)
                                                print(MemberFileName + " Downloading...")
                                                logging.info(MemberFileName + " Downloading...")
                                            auto_extract_file(file_path, dest_dir)
                                        except Exception as e:
                                            logging.error(str(dt.now()) + " ------- NSECM API -----" + str(e))
                                            print(e)
                                    else:
                                        print(MemberFileName + " Error in file")
                                        logging.error(MemberFileName + " Error in file")
                                else:
                                    print(MemberFileName + " exists")
                                    logging.info(MemberFileName + " exists")

                    try:
                        with ThreadPoolExecutor(max_workers=5) as executor:
                            executor.map(download_task, FileNameList)
                    except Exception as e:
                        logging.error(str(dt.now()) + " ------- NSECM API -----" + str(e))
                        print(e)
    #*********************COMMON FILES****************
    def CommonFiles():
        from concurrent.futures import ThreadPoolExecutor

        for CommonFolderName in CommonPathFolder:
            print("****************************" + CommonFolderName + "******************************")
            logging.info(str("****************************" + CommonFolderName + "******************************"))
 
            if 'varrate' in CommonFolderName:
                FileNameList = Class_Object.Get_All_FileName(Login_token, Common_File_Get_Url, Segment,CommonFolderName)
                if isinstance(FileNameList, list):
                    def download_task_varrate(i):
                        CommonFileName = i['name']
                        FileType = i["type"]
                        if FileType == "File":
                            is_target = is_target_file(CommonFileName, target_files) if target_files else ("C_VAR1_"+FromDate in CommonFileName)
                            if is_target:
                                # Save directly to category subfolder
                                subfolder = CommonFolderName.replace("/", "\\").strip("\\")
                                dest_dir = os.path.join(NSECMPath, FromDate, subfolder)
                                os.makedirs(dest_dir, exist_ok=True)
                                
                                file_path = os.path.join(dest_dir, CommonFileName)
                                Repl_File = CommonFileName.replace(".gz", "").replace(".zip", "")
                                unzipped_path = os.path.join(dest_dir, Repl_File)
                                
                                FileExistTemp = os.path.exists(file_path)
                                FileExist = os.path.exists(unzipped_path)
                                
                                if not FileExist and not FileExistTemp:
                                    File_Down_Resp = Class_Object.File_Download(Login_token, Common_File_Download_Url,Segment,CommonFolderName,CommonFileName)
                                    if File_Down_Resp!='error':
                                        try:
                                            with open(file_path, 'wb') as out_file:
                                                shutil.copyfileobj(File_Down_Resp, out_file)
                                                print(CommonFileName+" Downloading...")
                                                logging.info(CommonFileName+" Downloading...")
                                            auto_extract_file(file_path, dest_dir)
                                        except Exception as e:
                                            logging.error(str(dt.now())+ " ------- NSECM API -----"+str(e))
                                            print(e)
                                    else:
                                        print(CommonFileName+" error in file")
                                        logging.error(CommonFileName + " error in file")
 
                                else:
                                    print(CommonFileName+" exists")
                                    logging.info(CommonFileName+" exists")
                    try:
                        with ThreadPoolExecutor(max_workers=5) as executor:
                            executor.map(download_task_varrate, FileNameList)
                    except Exception as e:
                        logging.error(str(dt.now()) + " ------- NSECM API -----" + str(e))
                        print(e)
            elif 'bhavcopy' in CommonFolderName:
                FileNameList = Class_Object.Get_All_FileName(Login_token, Common_File_Get_Url, Segment,CommonFolderName)
                if isinstance(FileNameList, list):
                    def download_task_bhavcopy(i):
                        CommonFileName = i['name']
                        FileType = i["type"]
                        if FileType == "File":
                            is_target = is_target_file(CommonFileName, target_files) if target_files else (DD+MM+"0000.md" in CommonFileName or RevFromDate in CommonFileName)
                            if is_target:
                                # Save directly to category subfolder
                                subfolder = CommonFolderName.replace("/", "\\").strip("\\")
                                dest_dir = os.path.join(NSECMPath, FromDate, subfolder)
                                os.makedirs(dest_dir, exist_ok=True)
                                
                                file_path = os.path.join(dest_dir, CommonFileName)
                                Repl_File = CommonFileName.replace(".gz", "").replace(".zip", "")
                                unzipped_path = os.path.join(dest_dir, Repl_File)
                                
                                FileExistTemp = os.path.exists(file_path)
                                FileExist = os.path.exists(unzipped_path)
                                
                                if not FileExist and not FileExistTemp:
                                    File_Down_Resp = Class_Object.File_Download(Login_token, Common_File_Download_Url,Segment,CommonFolderName,CommonFileName)
                                    if File_Down_Resp!='error':
                                        try:
                                            with open(file_path, 'wb') as out_file:
                                                shutil.copyfileobj(File_Down_Resp, out_file)
                                                print(CommonFileName+" Downloading...")
                                                logging.info(CommonFileName+" Downloading...")
                                            auto_extract_file(file_path, dest_dir)
                                        except Exception as e:
                                            logging.error(str(dt.now())+ " ------- NSECM API -----"+str(e))
                                            print(e)
                                    else:
                                        print(CommonFileName+" error in files")
                                        logging.error(CommonFileName+" error in files")
 
                                else:
                                    print(CommonFileName+" exists")
                                    logging.info(CommonFileName +" exists")
                    try:
                        with ThreadPoolExecutor(max_workers=5) as executor:
                            executor.map(download_task_bhavcopy, FileNameList)
                    except Exception as e:
                        logging.error(str(dt.now()) + " ------- NSECM API -----" + str(e))
                        print(e)
            else:
                FileNameList = Class_Object.Get_All_FileName(Login_token, Common_File_Get_Url, Segment,CommonFolderName)
                if isinstance(FileNameList, list):
                    def download_task_other(i):
                        CommonFileName = i['name']
                        FileType = i["type"]
                        if FileType == "File":
                            is_target = is_target_file(CommonFileName, target_files) if target_files else (FromDate in CommonFileName or RevFromDate in CommonFileName)
                            if is_target:
                                # Save directly to category subfolder
                                subfolder = CommonFolderName.replace("/", "\\").strip("\\")
                                dest_dir = os.path.join(NSECMPath, FromDate, subfolder)
                                os.makedirs(dest_dir, exist_ok=True)
                                
                                file_path = os.path.join(dest_dir, CommonFileName)
                                Repl_File = CommonFileName.replace(".gz", "").replace(".zip", "")
                                unzipped_path = os.path.join(dest_dir, Repl_File)
                                
                                FileExistTemp = os.path.exists(file_path)
                                FileExist = os.path.exists(unzipped_path)
                                
                                if not FileExist and not FileExistTemp:
                                    File_Down_Resp = Class_Object.File_Download(Login_token, Common_File_Download_Url,Segment,
                                                                                CommonFolderName,CommonFileName)
                                    if File_Down_Resp!='error':
                                        try:
                                            with open(file_path, 'wb') as out_file:
                                                shutil.copyfileobj(File_Down_Resp, out_file)
                                                print(CommonFileName+" Downloading...")
                                                logging.info(CommonFileName+" Downloading...")
                                            auto_extract_file(file_path, dest_dir)
                                        except Exception as e:
                                                logging.error(str(dt.now())+ " ------- NSECM API -----"+str(e))
                                                print(e)
                                    else:
                                        print(CommonFileName+ " error in file")
                                        logging.error(CommonFileName+" error in files")
 
                                else:
                                    print(CommonFileName+" exists")
                                    logging.info(CommonFileName + " exists")
                    try:
                        with ThreadPoolExecutor(max_workers=5) as executor:
                            executor.map(download_task_other, FileNameList)
                    except Exception as e:
                        logging.error(str(dt.now()) + " ------- NSECM API -----"+ str(e))
                        print(e)
    MemberFiles()
    CommonFiles()
else:
    print(Login_status)
    logging.error(str(dt.now())+ " ------- NSECM API -----"+str(Login_status))

try:
    pathtemp = os.path.join(NSECMPath, FromDate, 'temp')
    os.makedirs(pathtemp, exist_ok=True)
    fileTemp = open(os.path.join(pathtemp, "temp.xls"), "w+")
    fileTemp.write("xyz")
    fileTemp.close()
except Exception:
    pass

# Print summary of missing/not downloaded files
print("\n==================================================")
print("  DOWNLOAD RUN SUMMARY (MISSING/NOT DOWNLOADED)")
print("==================================================")
logging.info("DOWNLOAD RUN SUMMARY (MISSING/NOT DOWNLOADED)")

local_files = set()
for root, dirs, files in os.walk(os.path.join(NSECMPath, FromDate)):
    for f in files:
        name = f.lower()
        if name.endswith(".gz"):
            name = name[:-3]
        elif name.endswith(".zip"):
            name = name[:-4]
        local_files.add(name)
        
missing_count = 0
if CM_NSE_Config:
    for key, val in CM_NSE_Config.items():
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
            resolved_display = resolved_display.replace("#nsecode#", NSECode.lower())
            
            print(f"[MISSING] {key} : {resolved_display}")
            logging.info(f"[MISSING] {key} : {resolved_display}")
            missing_count += 1
            
if missing_count == 0:
    print("All configured files are available locally!")
    logging.info("All configured files are available locally!")
print("==================================================\n")

