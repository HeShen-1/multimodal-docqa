"""
完整的会话管理测试脚本
演示 Token 唯一性和会话管理功能
"""
import requests
import json
from datetime import datetime


class SessionTest:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api/v1/auth"
        self.tokens = []
    
    def print_section(self, title):
        print(f"\n{'='*80}")
        print(f"  {title}")
        print(f"{'='*80}\n")
    
    def test_multiple_logins(self):
        """测试多次登录，验证 Token 唯一性"""
        self.print_section("测试 1: 多次登录验证 Token 唯一性")
        
        print("执行 3 次登录，观察生成的 Token 是否不同...\n")
        
        for i in range(3):
            print(f"第 {i+1} 次登录:")
            response = requests.post(
                f"{self.api_base}/login",
                json={"username": "admin", "password": "admin123"}
            )
            
            if response.status_code == 200:
                data = response.json()
                access_token = data["access_token"]
                refresh_token = data["refresh_token"]
                
                # 保存 token
                self.tokens.append({
                    "access": access_token,
                    "refresh": refresh_token,
                    "time": datetime.now().isoformat()
                })
                
                print(f"  ✓ 登录成功")
                print(f"  Access Token (前50字符):  {access_token[:50]}...")
                print(f"  Access Token (后50字符):  ...{access_token[-50:]}")
                print(f"  Refresh Token (前50字符): {refresh_token[:50]}...")
                print(f"  Refresh Token (后50字符): ...{refresh_token[-50:]}")
                print()
            else:
                print(f"  ✗ 登录失败: {response.status_code}")
                print(f"  {response.text}\n")
        
        # 比较 Token
        print("\n分析 Token 唯一性:")
        print(f"  生成的 Access Token 数量: {len(self.tokens)}")
        
        access_tokens = [t["access"] for t in self.tokens]
        refresh_tokens = [t["refresh"] for t in self.tokens]
        
        # 检查 Access Token
        unique_access = len(set(access_tokens))
        print(f"  唯一的 Access Token 数量: {unique_access}")
        if unique_access == len(access_tokens):
            print("  ✓ 所有 Access Token 都不相同")
        else:
            print("  ✗ 发现重复的 Access Token")
        
        # 检查 Refresh Token
        unique_refresh = len(set(refresh_tokens))
        print(f"  唯一的 Refresh Token 数量: {unique_refresh}")
        if unique_refresh == len(refresh_tokens):
            print("  ✓ 所有 Refresh Token 都不相同")
        else:
            print("  ✗ 发现重复的 Refresh Token")
        
        # 显示 Token 的差异部分
        print("\n  Token 签名部分对比（最后30字符）:")
        for i, token in enumerate(self.tokens, 1):
            print(f"    登录{i} - Access:  ...{token['access'][-30:]}")
            print(f"    登录{i} - Refresh: ...{token['refresh'][-30:]}")
    
    def test_session_management(self):
        """测试会话管理功能"""
        self.print_section("测试 2: 会话管理功能")
        
        if not self.tokens:
            print("错误: 请先执行测试1")
            return
        
        # 使用第一个 token 查询会话
        token = self.tokens[0]["access"]
        headers = {"Authorization": f"Bearer {token}"}
        
        print("1. 查询当前活跃会话:")
        response = requests.get(f"{self.api_base}/sessions", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ 查询成功")
            print(f"  活跃会话数量: {data['total']}")
            print(f"\n  会话详情:")
            
            for i, session in enumerate(data["sessions"], 1):
                print(f"\n  会话 {i}:")
                print(f"    ID: {session['id']}")
                print(f"    创建时间: {session['created_at']}")
                print(f"    最后使用: {session['last_used_at']}")
                print(f"    过期时间: {session['expires_at']}")
                print(f"    设备信息: {session['device_info'][:60]}...")
                print(f"    IP地址: {session['ip_address']}")
        else:
            print(f"  ✗ 查询失败: {response.status_code}")
            print(f"  {response.text}")
        
        print("\n2. 测试刷新 Token:")
        refresh_token = self.tokens[0]["refresh"]
        response = requests.post(
            f"{self.api_base}/refresh",
            json={"refresh_token": refresh_token}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ 刷新成功")
            print(f"  新的 Access Token (后30字符): ...{data['access_token'][-30:]}")
            
            # 再次查询会话，检查 last_used_at 是否更新
            print("\n3. 刷新后再次查询会话（检查 last_used_at 是否更新）:")
            response = requests.get(f"{self.api_base}/sessions", headers=headers)
            if response.status_code == 200:
                data = response.json()
                print(f"  ✓ 查询成功")
                for i, session in enumerate(data["sessions"], 1):
                    print(f"  会话 {i} - 最后使用: {session['last_used_at']}")
        else:
            print(f"  ✗ 刷新失败: {response.status_code}")
            print(f"  {response.text}")
        
        print("\n4. 测试登出（撤销所有会话）:")
        response = requests.post(f"{self.api_base}/logout", headers=headers)
        
        if response.status_code == 200:
            print(f"  ✓ 登出成功")
            
            # 再次查询会话
            print("\n5. 登出后查询会话（应该为空）:")
            response = requests.get(f"{self.api_base}/sessions", headers=headers)
            if response.status_code == 200:
                data = response.json()
                print(f"  活跃会话数量: {data['total']}")
                if data['total'] == 0:
                    print("  ✓ 所有会话已被撤销")
                else:
                    print("  ✗ 仍有活跃会话")
        else:
            print(f"  ✗ 登出失败: {response.status_code}")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*80)
        print("  会话管理完整测试")
        print("="*80)
        
        self.test_multiple_logins()
        self.test_session_management()
        
        print("\n" + "="*80)
        print("  测试完成")
        print("="*80)


if __name__ == "__main__":
    tester = SessionTest()
    tester.run_all_tests()

