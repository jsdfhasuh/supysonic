# download tool and json_tool
import os
import json
import requests


def download_image(url, save_folder, save_name, logger=None):
    try_count = 3
    while True:
        # Check image type from URL or fall back to content-type check
        web_image_type = os.path.splitext(url)[1].lower()
        if not web_image_type:
            image_type = '.png'
        if web_image_type:
            for element in ['.png', '.jpg']:
                save_name = save_name.replace(element, '')
            image_type = web_image_type
        if image_type in save_name:
            pass
        else:
            save_name = save_name + image_type
        save_path = os.path.join(save_folder, save_name)
        folder_path = os.path.dirname(save_path)
        os.makedirs(folder_path, exist_ok=True)
        if os.path.exists(save_path):
            logger.info('have save')
            return save_path
        try:
            response = requests.get(url)
            response.raise_for_status()  # 检查请求是否成功
            with open(save_path, 'wb') as file:
                file.write(response.content)
            return save_path
            # logger.info("图片下载完成")
        except requests.exceptions.RequestException as e:
            try_count -= 1
            if try_count == 0:
                logger.error(f"图片下载失败: {e}")
                return ""
        except IOError as e:
            try_count -= 1
            if try_count == 0:
                logger.error(f"保存图片失败: {e}")
                return ""


def write_dict_to_json(data, filename):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w") as json_file:
        json.dump(data, json_file, ensure_ascii=False, indent=4)


def read_dict_from_json(filename):
    try:
        with open(filename, "r", encoding='utf-8') as json_file:
            loaded_data = json.load(json_file)
        if loaded_data:
            return loaded_data
        else:
            return {}
    except FileNotFoundError:
        write_dict_to_json(data={}, filename=filename)
        return {}


def remove_dict_from_json(filename, key):
    with open(filename, "r") as json_file:
        data = json.load(json_file)
    if key in data:
        del data[key]
    write_dict_to_json(data=data, filename=filename)
