"""
认证 API 测试脚本
用于测试所有认证相关的 API 功能
"""
import requests
import json
from typing import Optional


class AuthAPITester:
    """认证 API 测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api/v1/auth"
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
    
    def print_response(self, title: str, response: requests.Response):
        """打印响应信息"""
        print(f"\n{'='*60}")
        print(f"测试: {title}")
        print(f"{'='*60}")
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        try:
            print(f"响应体: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        except:
            print(f"响应体: {response.text}")
    
    def test_register(self, username: str = "testuser", email: str = "test@example.com", password: str = "Test1234"):
        """测试用户注册"""
        url = f"{self.api_base}/register"
        data = {
            "username": username,
            "email": email,
            "password": password
        }
        response = requests.post(url, json=data)
        self.print_response("用户注册", response)
        return response.status_code == 201
    
    def test_login(self, username: str = "admin", password: str = "admin123"):
        """测试用户登录"""
        url = f"{self.api_base}/login"
        data = {
            "username": username,
            "password": password
        }
        response = requests.post(url, json=data)
        self.print_response("用户登录", response)
        
        if response.status_code == 200:
            result = response.json()
            self.access_token = result.get("access_token")
            self.refresh_token = result.get("refresh_token")
            print(f"\n✓ 登录成功！")
            print(f"Access Token: {self.access_token[:50]}...")
            print(f"Refresh Token: {self.refresh_token[:50]}...")
            return True
        return False
    
    def test_refresh_token(self):
        """测试刷新访问令牌"""
        if not self.refresh_token:
            print("\n✗ 错误: 没有 refresh_token，请先登录")
            return False
        
        url = f"{self.api_base}/refresh"
        data = {
            "refresh_token": self.refresh_token
        }
        response = requests.post(url, json=data)
        self.print_response("刷新访问令牌", response)
        
        if response.status_code == 200:
            result = response.json()
            self.access_token = result.get("access_token")
            print(f"\n✓ Token 刷新成功！")
            print(f"新的 Access Token: {self.access_token[:50]}...")
            return True
        return False
    
    def test_get_current_user(self):
        """测试获取当前用户信息"""
        if not self.access_token:
            print("\n✗ 错误: 没有 access_token，请先登录")
            return False
        
        url = f"{self.api_base}/me"
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        response = requests.get(url, headers=headers)
        self.print_response("获取当前用户信息", response)
        return response.status_code == 200
    
    def test_get_sessions(self):
        """测试获取活跃会话列表"""
        if not self.access_token:
            print("\n✗ 错误: 没有 access_token，请先登录")
            return False
        
        url = f"{self.api_base}/sessions"
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        response = requests.get(url, headers=headers)
        self.print_response("获取活跃会话列表", response)
        return response.status_code == 200
    
    def test_logout(self):
        """测试用户登出"""
        if not self.access_token:
            print("\n✗ 错误: 没有 access_token，请先登录")
            return False
        
        url = f"{self.api_base}/logout"
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        response = requests.post(url, headers=headers)
        self.print_response("用户登出", response)
        
        if response.status_code == 200:
            print(f"\n✓ 登出成功！")
            self.access_token = None
            self.refresh_token = None
            return True
        return False
    
    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*60)
        print("开始测试认证 API")
        print("="*60)
        
        results = {}
        
        # 1. 测试登录
        print("\n[1/5] 测试登录功能...")
        results['login'] = self.test_login()
        
        if not results['login']:
            print("\n✗ 登录失败，无法继续测试其他功能")
            return results
        
        # 2. 测试获取当前用户信息
        print("\n[2/5] 测试获取当前用户信息...")
        results['get_user'] = self.test_get_current_user()
        
        # 3. 测试获取活跃会话
        print("\n[3/5] 测试获取活跃会话...")
        results['get_sessions'] = self.test_get_sessions()
        
        # 4. 测试刷新令牌
        print("\n[4/5] 测试刷新访问令牌...")
        results['refresh'] = self.test_refresh_token()
        
        # 5. 测试登出
        print("\n[5/5] 测试用户登出...")
        results['logout'] = self.test_logout()
        
        # 打印测试总结
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)
        for test_name, result in results.items():
            status = "✓ 通过" if result else "✗ 失败"
            print(f"{test_name:20s}: {status}")
        
        total = len(results)
        passed = sum(results.values())
        print(f"\n总计: {passed}/{total} 通过")
        
        return results


def main():
    """主函数"""
    tester = AuthAPITester()
    
    # 运行所有测试
    results = tester.run_all_tests()
    
    # 返回退出码
    if all(results.values()):
        print("\n✓ 所有测试通过！")
        exit(0)
    else:
        print("\n✗ 部分测试失败")
        exit(1)


if __name__ == "__main__":
    main()

