import json
import datetime
import shutil
import time

import pymongo
import requests
import wget
from zipfile import ZipFile
import os
import pandas as pd

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0",
}


def get_request_data(url, verify=False):
    response = requests.get(url, verify=verify)
    if response.status_code == 200:
        return response
    else:
        time.sleep(10)
        get_request_data(url, verify=False)


def get_collection_from_db(data_base, collection, client):
    db = client[data_base]
    return db[collection]


def download_file_requests(url, file_name):
    try:
        response = requests.get(url, headers=headers)
        open(file_name, "wb").write(response.content)
    except:
        time.sleep(60)
        print('problem')
        download_file_requests(url, file_name)
    print('File is downloaded')


def delete_directory(path_to_directory):
    if os.path.exists(path_to_directory):
        shutil.rmtree(path_to_directory)
    else:
        print("Directory does not exist")


def create_directory(path_to_dir, name):
    mypath = f'{path_to_dir}/{name}'
    if not os.path.isdir(mypath):
        os.makedirs(mypath)


def upload_patents_data(file):
    data_collection = get_collection_from_db('db', 'uspto_data', client)
    update_collection = get_collection_from_db('db', 'update_collection', client)
    last_len_records = data_collection.count_documents({})
    for line in open(file, 'r', encoding='utf-8'):
        patent = json.loads(line)
        if not data_collection.find_one({'id': patent.get('id')}):
            patent['upload_at'] = datetime.datetime.now()
            data_collection.insert_one(patent)
    total_records = data_collection.count_documents({})
    update_query = {'name': 'uspto_data', 'new_records': total_records - last_len_records,
                    'total_records': total_records,
                    'update_date': datetime.datetime.now()}
    if update_collection.find_one({'name': 'uspto_data'}):
        update_collection.update_one({'name': 'uspto_data'}, {"$set": update_query})
    else:
        update_collection.insert_one(update_query)


def upload_all_uspto_zips():
    start_date = "2016-01-01"
    uspto_all_zip = get_collection_from_db('db', 'uspto_zips', client)
    current_directory = os.getcwd()
    for i in range(100):
        from_date = pd.to_datetime(start_date) + pd.DateOffset(months=i)
        from_date = from_date.strftime('%m-%d-%Y')
        to_date = pd.to_datetime(start_date) + pd.DateOffset(months=i + 1)
        to_date = to_date.strftime('%m-%d-%Y')
        url = f'https://developer.uspto.gov/ibd-api/v1/weeklyarchivedata/searchWeeklyArchiveData?fromDate={from_date}&toDate={to_date}'
        request_data = get_request_data(url)
        directory_name = 'uspto'
        path_to_directory = f'{current_directory}/{directory_name}'
        delete_directory(path_to_directory)
        create_directory(current_directory, directory_name)
        for file_data in json.loads(request_data.text):
            zip_file_link = (file_data.get('archiveDownloadURL'))
            if not uspto_all_zip.find_one({'zip_link': zip_file_link}):
                zip_file_name = zip_file_link[-37:]
                path_to_zip_file = f'{path_to_directory}/{zip_file_name}'
                try:
                    wget.download(zip_file_link, path_to_zip_file)
                except:
                    print('Problem download')
                    continue
                with ZipFile(path_to_zip_file, 'r') as zip:
                    file_path = zip.namelist()[0]
                    zip.extract(file_path, path_to_directory)
                upload_patents_data(f'{path_to_directory}/{file_path}')
                delete_directory(path_to_directory)
                uspto_all_zip.insert_one({'zip_link': zip_file_link})


if __name__ == '__main__':
    while True:
        start_time = time.time()
        client = pymongo.MongoClient('mongodb://localhost:27017')
        upload_all_uspto_zips()
        work_time = int(time.time() - start_time)
        print(work_time)
        print(14400 - work_time)
        time.sleep(14400 - work_time)
        client.close()
