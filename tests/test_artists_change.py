import requests


class SupysonicClient:
    def __init__(self, base_url="http://192.168.100.40:5000"):
        self.base_url = base_url
        # 创建 session 对象以保持会话
        self.session = requests.Session()
    
    def login(self, username="root", password="camu1217"):
        """模拟登录并获取session"""
        login_url = f"{self.base_url}/user/login"
        
        # 首先获取登录页面（可能包含CSRF token）
        response = self.session.get(login_url)
        
        # 准备登录数据
        login_data = {
            "user": username,
            "password": password
        }
        
        # 发送POST请求进行登录
        response = self.session.post(
            login_url,
            data=login_data,
            # 设置 Referer 头，某些网站可能需要
            headers={
                "Referer": login_url
            }
        )
        
        # 检查是否登录成功
        if "Logged in!" in response.text:
            print("登录成功!")
            return True
        else:
            print("登录失败!")
            return False
    
    def get_user_profile(self):
        """获取用户资料页面（测试session是否有效）"""
        response = self.session.get(f"{self.base_url}/user/me")
        return response.text
    
    def get_artists(self):
        """获取艺术家列表页面"""
        response = self.session.get(f"{self.base_url}/rest/getArtists?f=json&v=1.15.0&c=Musiver")
        return response.json()
    

def test():
    client = SupysonicClient()
    
    # 尝试登录
    if client.login():
        # 测试获取需要登录的页面
        raw_data = client.get_artists()
        artist_data = raw_data['subsonic-response']['artists']['index'][2]['artist'][13]
        # 改变主艺人名称
        change_data = { "action" : "change_real_artist",
            "id" : artist_data['id'],
            "real_name" : "張韶涵"}
        # 发送请求以更改艺术家名称
        response = client.session.post(f"{client.base_url}/artists?f=json&v=1.15.0&c=Musiver", json=change_data)
        print(response.json())
        pass

    
if __name__ == "__main__":
    test()
    pass