import os
import re
import subprocess
import spotify_main
from nfo import NfoHandler
final_file_dict = {}
history_points =[]
def extract_year(s):
    """提取形如20151201这种字符串的前4位数字作为年份"""
    if not s:
        return None
    match = re.match(r"^(\d{4})\d{4}", s)
    if match:
        return match.group(1)
    match = re.match(r"^(\d{4})-\d{2}", s)
    if match:
        return match.group(1)
    match = re.match(r"^(\d{4})", s)
    if match:
        return match.group(1)
    # '10 Oct 2023, 14:42'
    match = re.match(r"^\d{1,2}\s\w+\s(\d{4})", s)
    if match:
        return match.group(1)
    return None

def extract_artist_name(artist):
    """提取所有括号内的内容并拼接"""
    if "(" in artist and ")" in artist:
        # 查找所有括号内的内容
        artist = artist.replace("CV:", "").replace("CV.", "")
        results = re.findall(r'\(([^)]+)\)', artist)
        if results:
            # 拼接所有括号内容，用空格分隔
            new_result = []
            for result in results:
                new_name = result.replace(' ', '')
                new_result.append(new_name)
            if len(results) == 1:
                return new_result[0].strip()
            # 有多个括号内容时，用逗号连接
            else:
                cleaned_results = [result.strip() for result in new_result]
                return ",".join(cleaned_results)
    return artist.strip()

def get_real_artist(raw_artists):
    new_artists = {}
    for artist in raw_artists:
        name = ""
        if not name:
            name = spotify_main.get_artist_name(artist)
        if name in new_artists:
            new_artists[name] += raw_artists[artist]
        else:
            new_artists[name] = raw_artists[artist]
    new_artists = dict(
        sorted(new_artists.items(), key=lambda item: item[1], reverse=True)
    )
    return list(new_artists.keys())



def get_flac_tags(flac):
    tags = {}
    for tag in (
        'TITLE',
        'ALBUM',
        'ARTIST',
        'TRACKNUMBER',
        'GENRE',
        'COMMENT',
        'DATE',
        'DISCNUMBER',
        'ALBUMARTIST',
    ):
        # 不使用shell=True，更安全的命令构建方式
        tagcommand = ['metaflac', f'--show-tag={tag}', flac]
        # print(' '.join(tagcommand))
        tagcommand1 = f"metaflac --export-tags-to=- {flac}"
        print(f"tagcommand1 :{tagcommand1}")
        # 设置环境变量确保UTF-8编码
        env = os.environ.copy()
        env['LANG'] = 'zh_CN.UTF-8'
        env['LC_ALL'] = 'zh_CN.UTF-8'

        try:
            process = subprocess.Popen(
                tagcommand,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            stdout_bytes, stderr_bytes = process.communicate()

            if process.returncode != 0:
                print(f"警告: 获取标签 {tag} 失败")
                temp = ""
            else:
                try:
                    temp = stdout_bytes.decode('utf-8').rstrip()
                except UnicodeDecodeError:
                    temp = stdout_bytes.decode('utf-8', errors='replace').rstrip()

                temp = re.sub(f'{tag}=', '', temp, flags=re.IGNORECASE)
                    
                if "ARTIST" in tag:
                    temp = extract_artist_name(temp.replace('\n', ','))

                if 'NUMBER' in tag:
                    result = re.match(r'(\d+)/(\d+)', temp)
                    if result:
                        temp = result.group(1)
                if 'NUMBER' in tag and not temp:
                    temp = "1"
                if 'TRACKNUMBER' in tag:
                    pass
            tags[tag] = temp
            del temp
        except Exception as e:
            print(f"处理标签 {tag} 时出错: {str(e)}")
            tags[tag] = ""
        # 
    else:
        Tracknumber = tags.get('TRACKNUMBER', '')
        if not Tracknumber.isdigit():
            match = re.search(r'(\d+)-(\d+)', os.path.basename(flac))
            if match:
                tags['TRACKNUMBER'] = int(match.group(2))
            else:
                tags['TRACKNUMBER'] = '1'
    return tags


def split_artist(raw_artists):
    # &符号分割艺术家,with,feat.,/
    input_artists = raw_artists
    split_flag = [
        ',',
        'with',
        'feat.',
        'Feat.',
        '/',
        '、',
        '&',
        'and',
        'vs.',
        'x',
        'vs',
        'VS',
        ';',
    ]
    for flag in split_flag:
        if isinstance(raw_artists, str):
            for flag in split_flag:
                if flag in raw_artists:
                    raw_artists = raw_artists.split(flag)
        elif isinstance(raw_artists, list):
            for element in raw_artists.copy():
                if flag in element:
                    raw_artists.remove(element)
                    raw_artists.extend(element.split(flag))
    else:
        if isinstance(raw_artists, list):
            for element in raw_artists.copy():
                if element == ' ' or element == '':
                    raw_artists.remove(element)
                else:
                    raw_artists[raw_artists.index(element)] = element.strip()
        else:
            raw_artists = [raw_artists]
        return raw_artists


def get_album_name(raw_album_name):
    # 去除disc
    if re.search(r'Disc ?\d', raw_album_name, re.IGNORECASE):
        raw_album_name = re.sub(r'Disc ?\d', '', raw_album_name, flags=re.IGNORECASE)
    # 去除多余的括号
    raw_album_name = re.sub(r'\[\]', '', raw_album_name)
    return raw_album_name.strip()
    pass


def scan_folder_for_flac(input_folder):
    flac_files = []
    for root, dirs, files in os.walk(input_folder):
        for file in files:
            if file.lower().endswith('.flac'):
                flac_files.append(os.path.join(root, file))
    return flac_files


def reform_flac_to_flac_dict(flac_files, input_folder):
    flac_dict = {}
    for flac in flac_files:
        temp_path = input_folder
        last_point = ""
        relative_path = os.path.relpath(flac, input_folder)
        paths = relative_path.split(os.sep)
        flac_name = paths[-1]
        for index in range(len(paths) - 1):  # 排除文件名部分
            folder_name = paths[index]
            if index == len(paths) - 2:
                if folder_name not in last_point:
                    last_point[folder_name] = []
                last_point = last_point[folder_name]
                break
            if folder_name not in flac_dict:
                flac_dict[folder_name] = {}
            if last_point == "":
                last_point = flac_dict[folder_name]
            else:
                if folder_name not in last_point:
                    last_point[folder_name] = {}
                last_point = last_point[folder_name]
            # 是最后一个元素
        last_point.append({'file_name': flac_name, 'full_path': flac})
    return flac_dict


def get_flac_file_point(flac_dict,):
    global final_file_dict
    global history_points
    last_point = ""
    for key, value in flac_dict.items():
        if isinstance(value, dict):
            history_points.append(key)
            get_flac_file_point(value)
        elif isinstance(value, list):
            final_file_dict[key] = {"files": value, "path": os.path.join(*history_points,)}
            history_points.clear()
    return final_file_dict


if __name__ == "__main__":

    # check local environment for metaflac
    try:
        output = subprocess.run(
            ['metaflac'], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        version_raw_info = (
            output.stdout.decode('utf-8').strip()
            or output.stderr.decode('utf-8').strip()
        )
        # FLAC metadata editor version 1.5.0
        version_match = re.search(
            r'FLAC metadata editor version (\d+\.\d+\.\d+)', version_raw_info
        )
        if version_match:
            version = version_match.group(1)
            print(f"找到 metaflac 版本: {version}")
        else:
            print("警告: 未能解析 metaflac 版本信息。\n 请确保已正确安装 FLAC 工具包。")
    except FileNotFoundError:
        print("错误: 未找到 'metaflac' 命令。请确保已安装 FLAC 工具包。")
        exit(1)
    input_folder = r"C:\\Users\\jsdfhasuh\\Downloads\\Compressed\\AppleMusicDecrypt-Windows\\downloads"
    if input_folder == "":
        input_folder = input("请输入FLAC文件所在文件夹路径：").strip()
        if not os.path.isdir(input_folder):
            print("错误: 输入的路径不是有效的文件夹。")
            exit(1)
    flac_files = scan_folder_for_flac(input_folder)
    # 重新组织flac文件按目录
    flac_dict = reform_flac_to_flac_dict(flac_files, input_folder=input_folder)
    flac_final_dict = get_flac_file_point(flac_dict)
    print(flac_dict)
    for folder, items in flac_final_dict.items():
        nfo_data = {}
        artists = {}
        nfo_data['album'] = {"lock_data": False}
        nfo_data['album']['track'] = []
        files = items['files']
        path  = items['path']
        for file_info in files:
            flac_path = file_info['full_path']
            flac_name = file_info['file_name']
            tags = get_flac_tags(flac_path)
            raw_artists = split_artist(tags.get('ARTIST', ''))
            raw_album_artists = split_artist(tags.get('ALBUMARTIST', ''))
            cd_num = tags.get('DISCNUMBER')
            album = get_album_name(tags.get('ALBUM'))
            album_date = tags.get('DATE')
            cd_nums = []
            for artist_name in raw_artists:
                if artist_name in artists:
                    artists[artist_name] += 1
                else:
                    artists[artist_name] = 1
            if cd_num in cd_nums:
                pass
            else:
                cd_nums.append(cd_num)
            real_artists = get_real_artist(raw_artists=artists)  # 这两个都是数组 # 这两个都是数组
            temp_artists = tags.get('ARTIST', '').split(',')
            if not temp_artists:
                raw_artists = real_artists
            final_artist = ','.join(raw_artists)
            track_info = {
                'title': tags.get('TITLE', ''),
                'cdnum': tags.get('DISCNUMBER', '1'),
                'position': tags.get('TRACKNUMBER', ''),
            }
            
            if path in raw_artists: # 上一级路径是艺术家的名字
                track_info['albumartist'] = path
            track_info['artist'] = final_artist
            nfo_data['album']['track'].append(track_info)
        year = extract_year(tags.get('date'))
        if year:
            nfo_data['album']['year'] = year
        nfo_data['album']['artist'] = ', '.join(real_artists)
        nfo_data['album']['albumartist'] = real_artists[0]
        final_folder = os.path.dirname(flac_path)
        nfo_file = os.path.join(final_folder, 'album.nfo')
        NfoHandler.show(nfo_data)
        if os.path.exists(nfo_file):
            local_data = NfoHandler.read(nfo_file)
            lock_data_status = local_data['album'].get("lock_data", False)
            if not lock_data_status:
                NfoHandler.write(
                    data=nfo_data, output_path=nfo_file, pretty=True,
                )
        else:
            NfoHandler.write(
                data=nfo_data, output_path=nfo_file, pretty=True,
            )
           
            

