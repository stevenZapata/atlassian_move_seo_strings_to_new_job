import csv
from email.mime import base
import locale
from os import access
import string
import requests
import time
import datetime
import argparse
from datetime import datetime, timedelta, timezone
import json
import config

token_secret = config.token_secret
user_identifier = config.user_identifier
Base_URL = 'https://api.smartling.com'
CSV_file_path = config.CSV_file_path
nameOfJob = 'SEO Content'

parser = argparse.ArgumentParser(description='Process arguments for the job')
parser.add_argument('--content', type=str, help='Contentful or Magnolia project', required=True)
parser.add_argument('--seotags', type=str, default=':title', help='SEO tag in strings variant to move to new job')
parser.add_argument('--workFlowStepUid', type=str, help='SEO tag in strings variant to move to new job')


try:
    args = parser.parse_args()

    if args.content:
        projectType = args.content.lower()
        if 'contentful' in projectType:
            projectType = "Contentful"
            project_id = config.contentful_project_id
        if 'magnolia' in projectType:
            projectType = "Magnolia"
            project_id = config.magnolia_project_id


    if args.seotags:
        seoTagSite = args.seotags
        seoTagSitesArray = []
        if "," in seoTagSite:
            seoTagSite = seoTagSite.split(',')
            for tag in seoTagSite:
                tag = tag.replace(" ", "")
                seoTagSitesArray.append(tag)
        else: 
            seoTagSitesArray = [seoTagSite] 
        
    if args.workFlowStepUid:
        workflowStepUid = args.workFlowStepUid
    else:
        workflowStepUid = config.default_workFlowStepUid
    

except argparse.ArgumentError:
    print('Catching an argumentError, most likely missing an argument')


#read CSV file
def openCSVFile(filePath):
    fields = []
    rows = []
    with open(filePath, 'r') as csvfile:
        csvreader = csv.reader(csvfile)
        fields = next(csvreader)
  
    # extracting each data row one by one
        for row in csvreader:
            rowFile = row[0]
            rowLocales = row[1]
            if ',' in rowLocales:
                #more than one locale, create an array for all of the locales. 
                rowLocales = rowLocalesProcess(rowLocales)
            rowObj = {"File": rowFile, "Locales": rowLocales}
            rows.append(rowObj)
    print(rows)
    return rows

def requestLocalesForProject(project_id):
    accessToken = authenticate(user_identifier, token_secret)
    localeEndpiont = f'{Base_URL}/projects-api/v2/projects/{project_id}'
    header = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + accessToken
    }
    try:
        response = requests.get(localeEndpiont, headers=header)
        data = response.json()
        locales = data['response']['data']['targetLocales']
        return locales
    except requests.exceptions.HTTPError as err:
        print(err)




def authenticate(user_identifier, token_secret):
    authEndpoint = Base_URL + '/auth-api/v2/authenticate'
    payload = {'userIdentifier': user_identifier, 'userSecret': token_secret}
    header = {'content-type': 'application/json'}
    try: 
        response = requests.post(authEndpoint, json = payload, headers = header)
        data = response.json()
        accessToken = data['response']['data']['accessToken']
        refreshToken = data['response']['data']['refreshToken']
        return accessToken
    except requests.exceptions.HTTPError as err:
        print(err)


def rowLocalesProcess(rowLocales):
        splitLocales = rowLocales.split(', ')
        print(splitLocales)
        print('more than one locale')
        return splitLocales


def fetchJSONFileWithLocales():
    localesArray = ''
    try:
        with open('locales.json') as jsonFile: 
            localesArray = json.load(jsonFile)['locales']
    except:
        print('could not load the JSON file')
    
    return localesArray

def localeCodeMappingProcess(allRowsInfoArray,projectLocalesArray):

    updatedRowLocales = []
    for row in allRowsInfoArray:
        rowLocales = row['Locales']
        rowFile = row['File']
        print(rowLocales)
        localeIdsPerRow = []
        if type(rowLocales) == str:
            rowLocales = [rowLocales]
        for rowLocale in rowLocales:
            for projectLocale in projectLocalesArray:
                atlassianLocale = projectLocale['locale']
                if rowLocale == atlassianLocale:
                    localeIdsPerRow.append(projectLocale['smartling_locale_code'])
                    break

        newRowObj = {"File": rowFile, "Locales": localeIdsPerRow}
        updatedRowLocales.append(newRowObj)
    
    return updatedRowLocales

def fileNameForSite(rowsArray):
    updatedRowsFileName = []
    for row in rowsArray:
        fileName = row['File']
        fileName = fileName.split('www.atlassian.com')[1]
        row['File'] = f'/wac{fileName}'
        updatedRowsFileName.append(row)
    
    return updatedRowsFileName

def fileNameForContentful(rowsArray):
    updatedRowsFileName = []
    for row in rowsArray:
        fileName = row['File']
        row['File'] = f'{fileName}'
        updatedRowsFileName.append(row)

def getStringsPerFile(fileName):
    offSet = 0
    limit = 500
    allStrings = []
    while True:
        accessToken = authenticate(user_identifier, token_secret)
        getStringsEndPoint = f'{Base_URL}/strings-api/v2/projects/{project_id}/source-strings?fileUri={fileName}&limit={limit}&offset={offSet}'
        payload={}
        header = {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + accessToken
            }

        try: 
            r = requests.get(getStringsEndPoint, headers=header, data=payload)
            if r.status_code == 200:
                data = r.json()['response']['data']
                strings = data['items']
                totalCount = data['totalCount']
        except requests.exceptions.HTTPError as err:
            print(err)
            break

        if len(strings) == 0 and offSet == 0:
            print('no strings in file')
            break

        if totalCount < 500:
            allStrings = strings
            break
        else: 
            offSet += limit
            for x in strings:
                allStrings.append(x)

    return allStrings


def checkStringVariant(stringVariant):
    for tag in seoTagSitesArray:
        if tag in stringVariant:
            return True

    return False

def createJobForSEOStrings(nameOfJob, dateTime):
    jobName = f'{nameOfJob} {dateTime}'
    accessToken = authenticate(user_identifier, token_secret)
    localeEndpiont = f'{Base_URL}/jobs-api/v3/projects/{project_id}/jobs'
    
    payload = json.dumps({ "jobName": jobName})

    header = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + accessToken

    }
    try:
        response = requests.post(localeEndpiont, headers=header, data=payload)
        data = response.json()
        
    except requests.exceptions.HTTPError as err:
        print(err, 'could not create a job')
        return None

    jobinfo = data['response']['data']
    return jobinfo


def moveStringsToJob(stringsArray, jobInfo, locales):
    print(stringsArray)
    accessToken = authenticate(user_identifier, token_secret)
    jobTranslationId = jobInfo['translationJobUid']
    moveStringsEndPoint = f'{Base_URL}/jobs-api/v3/projects/{project_id}/jobs/{jobTranslationId}/strings/add'
    header = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + accessToken
            }

    payload = {'hashcodes': stringsArray, 'moveEnabled': True, 'targetLocaleIds': locales}
    try:
        response = requests.post(moveStringsEndPoint, headers=header, json=payload)
        data = response.json()
        print(data)
    except requests.exceptions.HTTPError as err:
        print(err, 'could not move strings to the job')
        return None

    if data['response']['code'] == 'SUCCESSS':
        print('added strings to the job')


def getDateTimeCETToday():
    timeStamp = time.time()
    timeStamp = str(timeStamp)
    timeStamp = timeStamp.split('.')[0]
    timeStamp = int(timeStamp)
    dt = datetime.fromtimestamp(timeStamp, timezone.utc)
    dt = str(dt).split(' ')
    dtTimeString = dt[1]
    dtTimeFirstTwoNumbers = dtTimeString[:2]
    dtFinalTimeCETHour = str(int(dtTimeFirstTwoNumbers) + 1)
    finalTimeString = dtTimeString.replace(dtTimeString[0:2], dtFinalTimeCETHour, 1)
    dt[1] = finalTimeString
    dtFinalCETDateTime = " ".join(dt)

    return dtFinalCETDateTime
    
def movedStringsWorkflowPerLocale(hashcodes, locale, targetWorkflowStepUid):
    accessToken = authenticate(user_identifier, token_secret)
    changeWorkflowApiUri= f'{Base_URL}/workflows-strings-api/v2/projects/{project_id}/move'
    
    header = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + accessToken
            }

    payload={
        'hashcodes': hashcodes,
        'targetLocaleId': locale,
        'targetWorkflowStepUid': targetWorkflowStepUid
    }
    
    try:
        response =requests.post(changeWorkflowApiUri, json=payload, headers=header)
        data = response.json()
        print(data)
    except requests.exceptions.HTTPError as err:
        print(err, 'could not move strings to the job')
        

def main():

    jobCreated = False
    #Job created response to use for other files
    jobInfo = ''
    
    allRowsInfoArray = openCSVFile(CSV_file_path)
    localesArray = fetchJSONFileWithLocales()
    allRowsUpdated = localeCodeMappingProcess(allRowsInfoArray, localesArray)

    # if project is for Contentful or Magnolia
    if projectType == "Contentful":
        finalRowsInfoArray = fileNameForContentful(allRowsUpdated)
    if projectType == "Magnolia":
        finalRowsInfoArray = fileNameForSite(allRowsUpdated)

    
    for row in finalRowsInfoArray:
        fileName = row['File']
        locales = row['Locales']
        stringsToMove = []
        allStrings = getStringsPerFile(fileName)
        if allStrings:
            for string in allStrings:
                stringHashCode = string['hashcode']
                stringVariant = string['stringVariant']
                if stringVariant:
                    strVariant = checkStringVariant(stringVariant)
                    if strVariant:
                        stringsToMove.append(stringHashCode)
    
        if stringsToMove and jobCreated == False:
            dateTimeTodayCET = getDateTimeCETToday()
            jobInfo = createJobForSEOStrings(nameOfJob, dateTimeTodayCET)
            jobCreated = True
            
        moveStringsToJob(stringsToMove, jobInfo, locales)
        for locale in locales:
            movedStringsWorkflowPerLocale(stringsToMove, locale, workflowStepUid)

main()



# def localeCodeMappingProcess(allRowsInfoArray):
#     projectLocalesArray = ''
#     with open('locales.json') as jsonFile: 
#         projectLocalesArray = json.load(jsonFile)

#     updatedRowLocales = []
#     for row in allRowsInfoArray:
#         rowLocales = row['Locales']
#         rowFile = row['File']
#         print(rowLocales)
#         localeIdsPerRow = []
#         if type(rowLocales) == str:
#             rowLocales = [rowLocales]
#         for rowLocale in rowLocales:
#             for projectLocale in projectLocalesArray:
#                 localeDescription = projectLocale['description'].split(' [')
#                 localeDescription = localeDescription[0]
#                 if rowLocale == localeDescription:
#                     localeIdsPerRow.append(projectLocale['localeId'])
#                     break

#         newRowObj = {"File": rowFile, "Locales": localeIdsPerRow}
#         updatedRowLocales.append(newRowObj)
    
#     return updatedRowLocales