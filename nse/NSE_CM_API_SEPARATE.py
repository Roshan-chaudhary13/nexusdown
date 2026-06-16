import requests
import json
import shutil
import os
import pandas as pd
import logging
pd.options.io.excel.xls.writer = 'xlwt'
#**************************Get Function Variable***************************************

def GetWorkPath():
    a_file = open("workpath.txt", "r")
    workpath = a_file.read()
    a_file.close()
    return workpath
workpath=GetWorkPath()

json_file = open(workpath + "\\config.json", "r")
json_data = json.load(json_file)
json_file.close()

#Function for Get MemberCode
def GetMemberCode():
    # NSEFO Path
    MemberCode = json_data["config"]["Member_Code"]["NSE_CODE"]
    return MemberCode

#Function for Get UserrId
def GetUserId():
    # NSEFO Path
    UserId =json_data["config"]["API_DETAILS"]["NSE_API"]["LoginID"]
    return UserId

#Function for Get Password
def GetPassword():
    # NSEFO Path
    Password = json_data["config"]["API_DETAILS"]["NSE_API"]["Password"]
    return Password

#Function for Get NSE Member Code
def GetNseCode():
    NSECode =json_data["config"]["Member_Code"]["NSE_CODE"]
    return NSECode

#Function for Get NSE CM Path
def GetNSECMPath():
    # NSEFO Path
    NSECashPath = json_data["config"]["Path"]["Equity"]["NSECM"]
    return NSECashPath

#Function for Get FromDate
def GetFromDate():
    # FromDate
    fromdate = json_data["config"]["Dates"]["Capital_Dates"]["FromDate"]
    return fromdate

def GetNextDate():
    # NextDate
    NextDate = json_data["config"]["Dates"]["Capital_Dates"]["NextDate"]
    return NextDate


memberCode=GetMemberCode()
loginId=GetUserId()
password=GetPassword()
NSECMPath=GetNSECMPath()
NSECode=GetNseCode()
FromDate=GetFromDate()
NextDate=GetNextDate()

shortdate = FromDate[0:4]
DD = FromDate[0:2]
MM = FromDate[2:4]
YYYY = FromDate[-4:]
YY = FromDate[-6:]
REVFROMDATE=str(YYYY)+str(MM)+str(DD)
Nextshortdate = NextDate[0:4]

#*******************************Path Variable****************************************

pathtemp = (NSECMPath)+str(FromDate)+ '\\temp'
tempPath=os.path.exists((NSECMPath)+str(FromDate)+ '\\temp')
datePath=os.path.exists((NSECMPath)+str(FromDate))

# logging.basicConfig(filename=workpath + "\logs\Logs_" + FromDate + ".log",level=logging.DEBUG)
logging.basicConfig(filename=workpath+'\logs\\NSE_CM_API_DOWNLOAD_'+FromDate+'.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


os.makedirs(NSECMPath + FromDate, exist_ok=True)
os.makedirs(pathtemp, exist_ok=True)


SegmentVar='CM'
FolderVar=['Onlinebackup','Reports','Reports/Dnld/PNL01']


#**************************************URL*************************************************

url = "https://www.connect2nse.com/extranet-api/"
Login_Endpoint_url="login/2.0"
MemberURL='member/content/2.0?'
CommonURL='common/content/2.0?'

#**************create dataframe***********************
data = [['memberCode', memberCode], ['loginId', loginId], ['password', password]]
df = pd.DataFrame(data, columns=['key', 'Value'])

#**************Logout JSON dataframe******************
data = [['memberCode', memberCode], ['loginId', loginId]]
Logout_df = pd.DataFrame(data, columns=['key', 'Value'])

#*************convert dataframe to dic*****************
area_dict = dict(zip(df['key'], df['Value']))

#************convert  Logout dataframe to dic*********
Logout_dict = dict(zip(Logout_df['key'], Logout_df['Value']))

#***************convert dic to json******************
json_object = json.dumps(area_dict)

#****************convert dic to json****************
LogOut_json_object = json.dumps(Logout_dict)

#******************* Login ************************

Res_memberCode=''
Res_loginId=""
Res_token=""
Res_status=""

try:
    def Login(json_object,endpoint_url):
        pd=""
        try:
            payload =json_object #json.dumps(json_object)
            headers = {
              'Content-Type': 'application/json',
              'Cookie': 'HttpOnly'
            }
            loginurl=str(url)+str(endpoint_url)
            response = requests.request("POST", loginurl, headers=headers, data=payload)
            pd=response.json()
            logging.debug("Loging status : "+pd["status"])
            print("Loging status :"+pd["status"])
            return response

        except Exception as e:
            logging.error("Login error "+str(e))
            #logging.error("Loging status : " + pd["status"])
            return response



    #**************** Start Loging********************

    LoginRespone=Login(str(json_object),str(Login_Endpoint_url))#.json()
    print(type(LoginRespone))
    logging.info("")
    logging.info("")
    logging.info(type(LoginRespone))

    print(LoginRespone.status_code)
    logging.info(LoginRespone.status_code)


    LoginStatus=LoginRespone
    LoginRespone=LoginRespone.json()

    def Download_File_cof(url_m,file_Name):
        FileURL=url_m+file_Name
        payload={}
        headers = {
          'Authorization': 'Bearer '+str(Res_token),
          'Cookie': 'HttpOnly'
        }

        response = requests.request("GET", FileURL, headers=headers, data=payload,stream=True)
        if "200" in str(response.status_code):
            temp_file_path = os.path.join(pathtemp, file_Name)
            final_file_path = os.path.join(NSECMPath+FromDate, file_Name.replace(".gz","").replace(".zip", ""))
            
            #print(temp_file_path)
            #print(final_file_path)
            if not os.path.exists(final_file_path) and not os.path.exists(temp_file_path):
                try:
                    with open(str(pathtemp + '\\') + str(file_Name), 'wb') as out_file:
                        shutil.copyfileobj(response.raw, out_file)
                    print(f"{file_Name} : Downloaded")
                    logging.info(f"{file_Name} Downloaded")

                except Exception as e:
                    logging.error(f"{file_Name} :Error downloading")
                    print(f"{file_Name} :Error downloading")
            else:
                logging.info(f"{file_Name} File exists")
                print(f"{file_Name} File exists")

            return response.raw
        else:
            logging.error("NSECM " + file_Name + ", statuscode:-" + str(response.status_code))

    def Logout(Res_token):
        url = "https://www.connect2nse.com/extranet-api/logout/2.0"

        payload = LogOut_json_object
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + str(Res_token),
            'Cookie': 'HttpOnly'
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        print(response.text)


    if "200" in str(LoginStatus.status_code):
        Logout(Res_token)

    if "200" in str(LoginStatus.status_code):

        Res_memberCode=LoginRespone["memberCode"]
        Res_responseCode=LoginRespone["responseCode"]
        Res_loginId=LoginRespone["loginId"]
        Res_token=LoginRespone["token"]
        Res_status=LoginRespone["status"]
        Download_DF=pd.read_excel(workpath+"\Files\Download_File.xls",sheet_name="NSECM")
        print()


    if "200" in str(LoginStatus.status_code):
        for url_m,file_Name in zip(Download_DF["Source"],Download_DF["Name"]):
            file_Name=(str(file_Name)).replace("#FROMDATE#",FromDate)
            file_Name=(str(file_Name)).replace("#NSECODE#", NSECode)
            file_Name=(str(file_Name)).replace("#DD#", DD)
            file_Name=(str(file_Name)).replace("#MM#", MM)
            file_Name=(str(file_Name)).replace("#YY#", YY)
            file_Name=(str(file_Name)).replace("#YYYY#", YYYY)
            file_Name=(str(file_Name)).replace("#REVFROMDATE#", REVFROMDATE)
            #print(file_Name)
            Download_File_cof(url_m,file_Name)
            logging.info("NSECM " + file_Name)





except Exception as e:
    print(e)
    logging.error(str(e)+str(Res_memberCode))
finally:
    try:
        df = pd.DataFrame(columns=['A', 'B', 'C', 'D', 'E', 'F', 'G'])
        pathtemp = os.path.join(NSECMPath, FromDate, 'temp')
        os.makedirs(pathtemp, exist_ok=True)
        df.to_excel(os.path.join(pathtemp, "temp.xls"))
    except Exception:
        pass
