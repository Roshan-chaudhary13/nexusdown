import time
import requests
import json
import shutil
import os
import logging
from datetime import datetime as dt
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
NextDate=json_data["config"]["Dates"]["Capital_Dates"]["NextDate"]
MemberCode=json_data["config"]["API_DETAILS"]["NSE_API"]["MemberCode"]
LoginID=json_data["config"]["API_DETAILS"]["NSE_API"]["LoginID"]
Password=json_data["config"]["API_DETAILS"]["NSE_API"]["Password"]

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



shortdate = NextDate[0:4]
DD = NextDate[0:2]
MM = NextDate[2:4]
YY = NextDate[-4:]

RevNextDate=YY+MM+DD
#**************************Path Variable***********************************

pathtemp = (NSECMPath)+str(NextDate)+ '\\temp'

tempPath=os.path.exists((NSECMPath)+str(NextDate)+ '\\temp')
datePath=os.path.exists((NSECMPath)+str(NextDate))

# logging.basicConfig(filename=workpath + "\logs\script_logs_" + str(dt.today().strftime("%d%m%Y")) + ".log",level=logging.DEBUG)
logging.basicConfig(filename=workpath+'\logs\\NSE_CM_API_DOWNLOAD_'+str(NextDate)+'.log', level=logging.INFO, format='[ %(asctime)s] - [%(levelname)s ] - %(message)s')

if not datePath==True:
    os.mkdir(NSECMPath+NextDate)

if not tempPath==True:
    os.mkdir(pathtemp)


#****************** List of Folder Name *************

listCELList=[]



#************ OOPS ***************
class NSE_FILE_CLASS:

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

            response = requests.request("POST", url, headers=headers, data=payload)
            return response.json()
        except Exception as e:
            print(e)
            return "Error"
            logging.error( " ------- NSECM API -----"+str(e))

    def Login(self,Login_url, MemberCode, LoginID, PasswordEnc):
        response=''
        try:
            print("Loging.............")
            logging.info(" Loging.............")

            url = Login_url

            payload = json.dumps({
                "memberCode": "" + MemberCode + "",
                "loginId": "" + LoginID + "",
                "password": "" + PasswordEnc + ""
            })
            headers = {
                'Content-Type': 'application/json'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            return response.json()
        except Exception as e:
            print(e)
            logging.error(" ------- NSECM API -----"+str(e))
            return response

    def File_Download(self,Login_Token_Param, FileDownloadURL_Param, Segment_Param, FolderPath_Param, FileName_Param):
        try:
            Download_URL = FileDownloadURL_Param + "segment=" + Segment_Param + '&folderPath=/' + FolderPath_Param + '&filename=' + FileName_Param
            logging.info(Download_URL)
            payload = {}
            headers = {
                'Authorization': 'Bearer ' + str(Login_Token_Param),
                'Cookie': 'HttpOnly'
            }
            response = requests.request("GET", Download_URL, headers=headers, data=payload, stream=True)
            time.sleep(1)
            #print(response.status_code)
            if response.status_code==200:
                return response.raw
            else:
                return "error"
            #return response.raw
        except Exception as e:
            print(e)
            return "error"
            logging.error(" ------- NSECM API -----"+str(e))

    def Get_All_FileName(self,AuthToken_Param, File_Get_Url_Param, Segment_Param, MemberFolderPath_Param):
        try:
            GetFolderURL = File_Get_Url_Param + 'segment=' + Segment_Param + '&folderPath=/' + MemberFolderPath_Param

            payload = {}
            headers = {
                'Authorization': 'Bearer ' + str(AuthToken_Param),
                'Cookie': 'HttpOnly'
            }
            response = requests.request("GET", GetFolderURL, headers=headers, data=payload)
            datajson = response.json()
            return datajson['data']
        except Exception as e:
            print(e)
            return "Error"
            logging.error(" ------- NSECM API -----"+str(e))



#************Objects*************
Class_Object=NSE_FILE_CLASS()


#****************Calling*********
TokenSession=""
if os.path.exists("Token.txt"):
    tokenFile=open("Token.txt","r")
    TokenSession=tokenFile.read()
    tokenFile.close()

LogoutStatus=Class_Object.Logout(TokenSession,LogoutURL, MemberCode, LoginID)
print("Cleared old session")
logging.info("")
logging.info("")
logging.info("")
current_datetime = dt.now()
print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"+str(current_datetime)+"<<<<<<<<<<<<<<<<<<<<<<<<<<<")
logging.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"+str(current_datetime)+"<<<<<<<<<<<<<<<<<<<<<<<<<<<")
Login_response=Class_Object.Login(LoginURL, MemberCode, LoginID, Password)
Login_status=''
try:
    Login_status = Login_response["status"]
except Exception as e:
    print(e)
    logging.error(" ------- NSECM API -----"+str(e))
Login_token = ""
if Login_status == "success":
    Login_token = Login_response["token"]
    tokenFile=open("Token.txt","w")
    TokenSession=tokenFile.write(Login_token)
    tokenFile.close()
    print(Login_status)
    logging.info( str(Login_status))
    FileNameList = []

    #*********************MEMEBER FILES****************
    def MemberFiles():
        for MemberFolderName in MemberPathFolder:
            print("****************************" + MemberFolderName + "******************************")
            logging.info(str("****************************" + MemberFolderName + "******************************"))
            # if "CEP" in MemberFolderName:
            #     FileNameList = Class_Object.Get_All_FileName(Login_token, Member_File_Get_Url, Segment,MemberFolderName)
            #
            #     try:
            #         for i in FileNameList:
            #             MemberFileName = i['name']
            #             FileType = i["type"]
            #
            #             if FileType == "File":
            #
            #                 if MemberCode+"_CEP" + str(YY) + str(MM) + str(DD) in MemberFileName and "CEP" in MemberFileName:
            #                     FileExistTemp=os.path.exists(NSECMPath + "\\" + NextDate + '\\temp\\' + str(MemberFileName))
            #                     Repl_File=MemberFileName.replace(".gz","")
            #                     FileExist=os.path.exists(NSECMPath + "\\" + NextDate + '\\' + str(Repl_File))
            #                     listCELList.append(MemberFileName)
            #         print(len(listCELList))
            #         if len(listCELList) >=1:
            #             FileCEP=listCELList[-1]
            #             File_Down_Resp = Class_Object.File_Download(Login_token, Member_File_Download_Url,Segment, MemberFolderName,FileCEP)
            #             try:
            #                 with open(str(NSECMPath + "\\" + NextDate + '\\temp\\') + str(FileCEP),'wb') as out_file:
            #                     shutil.copyfileobj(File_Down_Resp, out_file)
            #                     print(MemberFileName+" Downloading...")
            #                     #*********Write CEP file*****************
            #                     json_data["config"]["CEP_File"]["CEP_File_Name"]= FileCEP
            #                     json_file = open(workpath + "\config.json", "w+")
            #                     json.dump(json_data, json_file, indent=8)
            #                     json_file.close()
            #                     #****************************************
            #
            #             except Exception as e:
            #                 logging.error(str(dt.now())+ " ------- NSECM API -----"+str(e))
            #                 print(e)
            #     except Exception as e:
            #         logging.error(str(dt.now()) + " ------- NSECM API -----" + str(e))
            #         print(e)
            if '':
                print()
            else:
                FileNameList = Class_Object.Get_All_FileName(Login_token, Member_File_Get_Url, Segment,MemberFolderName)
                time.sleep(1)
                try:
                    for i in FileNameList:
                        MemberFileName = i['name']
                        FileType = i["type"]
                        if FileType == "File":
                            if NextDate in MemberFileName or RevNextDate in MemberFileName:
                                FileExistTemp=os.path.exists(NSECMPath + "\\" + NextDate + '\\temp\\' + str(MemberFileName))
                                Repl_File=MemberFileName.replace(".gz","")
                                FileExist=os.path.exists(NSECMPath + "\\" + NextDate + '\\' + str(Repl_File))
                                if not FileExist and not FileExistTemp:
                                    File_Down_Resp = Class_Object.File_Download(Login_token, Member_File_Download_Url,Segment, MemberFolderName,MemberFileName)
                                    if File_Down_Resp!='error':
                                        try:
                                            time.sleep(1)
                                            with open(str(NSECMPath + "\\" + NextDate + '\\temp\\') + str(MemberFileName),'wb') as out_file:
                                                shutil.copyfileobj(File_Down_Resp, out_file)
                                                print(MemberFileName+" Downloading...")
                                                logging.info(MemberFileName+" Downloading...")

                                        except Exception as e:
                                                logging.error(str(dt.now())+ " ------- NSECM API -----"+str(e))
                                                print(e)
                                    else:
                                        print(MemberFileName+" Error in file")
                                        logging.error(MemberFileName + " Error in file")
                                else:
                                    print(MemberFileName+" exists")
                                    logging.info(MemberFileName+" exists")

                except Exception as e:
                    logging.error(str(dt.now()) + " ------- NSECM API -----" + str(e))
                    print(e)
    #*********************COMMON FILES****************
    def CommonFiles():
        for CommonFolderName in CommonPathFolder:
            print("****************************" + CommonFolderName + "******************************")
            logging.info(str("****************************" + CommonFolderName + "******************************"))

            if 'varrate' in CommonFolderName:
                FileNameList = Class_Object.Get_All_FileName(Login_token, Common_File_Get_Url, Segment,CommonFolderName)
                try:
                    for i in FileNameList:
                        CommonFileName = i['name']
                        FileType = i["type"]
                        if FileType == "File":
                            if "C_VAR1_"+NextDate+"_6.DAT" in CommonFileName or "C_VAR1_"+NextDate+"_1.DAT" in CommonFileName:
                                # Save directly to category subfolder
                                subfolder = CommonFolderName.replace("/", "\\").strip("\\")
                                dest_dir = os.path.join(NSECMPath, NextDate, subfolder)
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
                                        except Exception as e:
                                            logging.error(" ------- NSECM API -----"+str(e))
                                            print(e)
                                    else:
                                        print(CommonFileName+" error in file")
                                        logging.error(CommonFileName + " error in file")

                                else:
                                    print(CommonFileName+" exists")
                                    logging.info(CommonFileName+" exists")

                except Exception as e:
                    logging.error(" ------- NSECM API -----" + str(e))
                    print(e)
            elif 'bhavcopy' in CommonFolderName:
                FileNameList = Class_Object.Get_All_FileName(Login_token, Common_File_Get_Url, Segment,CommonFolderName)
                try:
                    for i in FileNameList:
                        CommonFileName = i['name']
                        FileType = i["type"]
                        if FileType == "File":
                            if DD+MM+"0000.md" in CommonFileName or RevNextDate in CommonFileName:
                                # Save directly to category subfolder
                                subfolder = CommonFolderName.replace("/", "\\").strip("\\")
                                dest_dir = os.path.join(NSECMPath, NextDate, subfolder)
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


                                        except Exception as e:
                                            logging.error(" ------- NSECM API -----"+str(e))
                                            print(e)
                                    else:
                                        print(CommonFileName+" error in files")
                                        logging.error(CommonFileName+" error in files")

                                else:
                                    print(CommonFileName+" exists")
                                    logging.info(CommonFileName +" exists")

                except Exception as e:
                    logging.error(" ------- NSECM API -----" + str(e))
                    print(e)
            else:
                FileNameList = Class_Object.Get_All_FileName(Login_token, Common_File_Get_Url, Segment,CommonFolderName)
                try:
                    for i in FileNameList:
                        CommonFileName = i['name']
                        FileType = i["type"]
                        if FileType == "File":
                            if NextDate in CommonFileName or RevNextDate in CommonFileName:
                                # Save directly to category subfolder
                                subfolder = CommonFolderName.replace("/", "\\").strip("\\")
                                dest_dir = os.path.join(NSECMPath, NextDate, subfolder)
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

                                        except Exception as e:
                                                logging.error(" ------- NSECM API -----"+str(e))
                                                print(e)
                                    else:
                                        print(CommonFileName+ " error in file")
                                        logging.error(CommonFileName+" error in files")

                                else:
                                    print(CommonFileName+" exists")
                                    logging.info(CommonFileName + " exists")

                except Exception as e:
                    logging.error(" ------- NSECM API -----"+ str(e))
                    print(e)
    #MemberFiles()
    CommonFiles()
else:
    print(Login_status)
    logging.error(str(dt.now())+ " ------- NSECM API -----"+str(Login_status))

try:
    pathtemp = os.path.join(NSECMPath, NextDate, 'temp')
    os.makedirs(pathtemp, exist_ok=True)
    fileTemp = open(os.path.join(pathtemp, "temp.xls"), "w+")
    fileTemp.write("xyz")
    fileTemp.close()
except Exception:
    pass
