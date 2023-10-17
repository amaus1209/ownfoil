import requests
import os
import re
import json
import hashlib
from constants import *

app_id_regex = r"\[([0-9A-Fa-f]{16})\]"
version_regex = r"\[v(\d+)\]"

def getDirsAndFiles(path):
    entries = os.listdir(path)
    allFiles = []
    allDirs = []

    for entry in entries:
        fullPath = os.path.join(path, entry)
        if os.path.isdir(fullPath):
            allDirs.append(fullPath)
            dirs, files = getDirsAndFiles(fullPath)
            allDirs += dirs
            allFiles += files
        elif fullPath.split('.')[-1] in ALLOWED_EXTENSIONS:
            allFiles.append(fullPath)
    return allDirs, allFiles

def get_app_id_from_filename(filename):
    app_id_match = re.search(app_id_regex, filename)
    return app_id_match[1] if app_id_match is not None else None

def get_version_from_filename(filename):
    version_match = re.search(version_regex, filename)
    return version_match[1] if version_match is not None else None

def get_file_size(filepath):
    return os.path.getsize(filepath)

def identify_appId(app_id):
    app_id = app_id.lower()

    if app_id in cnmts_db:
        app_id_keys = list(cnmts_db[app_id].keys())
        if len(app_id_keys):
            app = cnmts_db[app_id][app_id_keys[-1]]
            
            if app['titleType'] == 128:
                app_type = 'base'
                title_id = app_id.upper()
            elif app['titleType'] == 129:
                app_type = 'patch'
                if 'otherApplicationId' in app:
                    title_id = app['otherApplicationId'].upper()
                else:
                    base_id = app_id[:-3]
                    title_id = [t for t in list(cnmts_db.keys()) if t.startswith(base_id)][0].upper()
            elif app['titleType'] == 130:
                app_type = 'dlc'
                if 'otherApplicationId' in app:
                    title_id = app['otherApplicationId'].upper()
                else:
                    base_id = app_id[:-4]
                    title_id = [t for t in list(cnmts_db.keys()) if t.startswith(base_id)][0].upper()

    else:
        if app_id.endswith('000'):
            app_type = 'dlc'
            title_id = app_id
        elif app_id.endswith('800'):
            app_type = 'base'
            title_id = app_id[:-3] + '000'
        else:
            app_type = 'dlc'
            title_id = app_id[:-3] + '000'
    
    return title_id.upper(), app_type

def load_titledb(app_settings):
    global cnmts_db
    global titles_db
    global versions_db
    with open(os.path.join(TITLEDB_DIR, 'cnmts.json')) as f:
        cnmts_db = json.load(f)

    with open(os.path.join(TITLEDB_DIR, f"{app_settings['library']['region']}.{app_settings['library']['language']}.json")) as f:
        titles_db = json.load(f)

    with open(os.path.join(TITLEDB_DIR, 'versions.json')) as f:
        versions_db = json.load(f)

def identify_file(filepath):
    filedir, filename = os.path.split(filepath)
    app_id = get_app_id_from_filename(filename)
    version = get_version_from_filename(filename)
    extension = filename.split('.')[-1]
    try:
        title_id, app_type = identify_appId(app_id)
    except Exception as e:
        print(f'Unable to identify file {filename}, app ID: {app_id}. The error was:')
        print(e)
        return None

    return {
        'filepath': filepath,
        'filedir': filedir,
        'filename': filename,
        'title_id': title_id,
        'app_id': app_id,
        'type': app_type,
        'version': version,
        'extension': extension,
        'size': get_file_size(filepath),
    }


def get_game_info(title_id):
    try:
        title_info = [titles_db[t] for t in list(titles_db.keys()) if titles_db[t]['id'] == title_id][0]
        return {
            'name': title_info['name'],
            'bannerUrl': title_info['bannerUrl'],
            'iconUrl': title_info['iconUrl'],
            'id': title_info['id'],
            'category': title_info['category'],
        }
    except Exception:
        print(f"Title ID not found in titledb: {title_id}")
        return None

def convert_nin_version(version):
    return int(version)//65536

def get_game_latest_version(all_existing_versions):
    return max(v['version'] for v in all_existing_versions)

def get_all_existing_versions(titleid):
    titleid = titleid.lower()
    if titleid not in versions_db:
        print(f'Title ID not in versions.json: {titleid.upper()}')
        return None

    versions_from_db = versions_db[titleid].keys()
    return [
        {
            'version': int(version_from_db),
            'human_version': convert_nin_version(version_from_db),
            'release_date': versions_db[titleid][str(version_from_db)],
        }
        for version_from_db in versions_from_db
    ]


def set_titledb_default_files():
    os.system(f'cd {TITLEDB_DIR} && git sparse-checkout --no-cone set {" ".join(TITLEDB_DEFAULT_FILES)} > /dev/null')

def set_titledb_lang_file(region, language):
    os.system(f'cd {TITLEDB_DIR} && git sparse-checkout add {region}.{language}.json > /dev/null')

def git_fetch_and_pull():
    os.system(f'cd {TITLEDB_DIR} && git checkout master > /dev/null 2>&1')
    os.system(f'cd {TITLEDB_DIR} && git fetch > /dev/null 2>&1 && git pull > /dev/null 2>&1')

def update_titledb_files(app_settings):
    set_titledb_default_files()
    set_titledb_lang_file(app_settings['library']['region'], app_settings['library']['language'])
    
def update_titledb(app_settings):
    if not os.path.isdir(TITLEDB_DIR):
        print('Retrieving titledb for the first time...')
        os.system(f'git clone --depth=1 --no-checkout {TITLEDB_URL} {TITLEDB_DIR}')

    update_titledb_files(app_settings)
    git_fetch_and_pull()
    load_titledb(app_settings)
