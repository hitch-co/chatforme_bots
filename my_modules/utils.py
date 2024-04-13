import json
import os
import re
from datetime import datetime

from my_modules.my_logging import create_logger

logger = create_logger(
    dirname='log', 
    logger_name='logger_utils',
    debug_level='DEBUG',
    mode='w',
    stream_logs=False
    )

def load_json(
        dir_path,
        file_name
        ):
    file_path = os.path.join(dir_path, file_name)
    
    #Add Error Checkign
    if not os.path.exists(file_path):
        logger.error(f"File {file_path} does not exist.")
        return None
    else:
        logger.debug(f"File {file_path} exists.")
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading JSON file: {e}")
        return None

    return data

def show_json(obj):
    # Assuming obj.model_dump_json() returns a JSON string
    json_data = json.loads(obj.model_dump_json())
    return json.dumps(json_data, indent=4)

async def find_unique_to_new_list(
        source_list, 
        new_list
        ) -> list:
    set1 = set(source_list)
    set2 = set(new_list)
    unique_strings = set2 - set1
    unique_list = list(unique_strings)

    # print("_find_unique_to_new_list inputs/output:")
    # print(f"source_list: {source_list}")
    # print(f"new_list: {new_list}")
    # print(f"unique_list: {unique_list}")
    return unique_list

async def find_unique_to_new_dict(
        source_dict, 
        new_dict
        ) -> list:
    # Assuming the first dictionary in list2 represents the key structure
    keys = new_dict[0].keys()

    # Convert list1 and list2 to sets of a primary key (assuming the first key is unique)
    primary_key = next(iter(keys))
    set1 = {user[primary_key] for user in source_dict}
    set2 = {user[primary_key] for user in new_dict}

    # Find the difference - users in list2 but not in list1
    unique_user_ids = set2 - set1

    # Convert the unique user_ids back to dictionary format
    unique_users = [user for user in new_dict if user[primary_key] in unique_user_ids]
    # print("This is the list of unique_users:")
    # print(unique_users)
    
    return unique_users
    
def shutdown_server():
    from flask import request 
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()

def get_datetime_formats():
    """
    Generate a dictionary containing formatted datetime strings for SQL and filenames.

    Returns:
    dict: A dictionary with the following keys and values:
        - 'sql_format': A string representing the current date and time formatted as 'YYYY-MM-DD HH:MM:SS'.
        - 'filename_format': A string representing the current date and time formatted as 'YYYY-MM-DD_HH-MM-SS'.
    """
    now = datetime.now()
    sql_format = now.strftime('%Y-%m-%d %H:%M:%S')
    filename_format = now.strftime('%Y-%m-%d_%H-%M-%S')
    dates_dict = {"sql_format":sql_format, "filename_format":filename_format}
    return dates_dict