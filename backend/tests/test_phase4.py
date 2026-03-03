"""
Phase 4 功能测试
测试标签管理、文档分享、批量上传功能
"""
import pytest
from pathlib import Path
import io


class TestTagManagement:
    """标签管理测试"""
    
    def test_create_tag(self, client, auth_headers: dict):
        """测试创建标签"""
        import time
        tag_name = f"测试标签_{int(time.time() * 1000)}"
        
        response = client.post(
            "/api/v1/tags",
            headers=auth_headers,
            json={
                "name": tag_name,
                "color": "#3B82F6",
                "description": "这是一个测试标签"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == 100000
        assert data["data"]["name"] == tag_name
        assert data["data"]["color"] == "#3B82F6"
        
        return data["data"]["id"]
    
    def test_get_tags(self, client, auth_headers: dict):
        """测试获取标签列表"""
        response = client.get(
            "/api/v1/tags?page=1&pageSize=10",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 100000
        assert "items" in data["data"]
        assert "total" in data["data"]
    
    def test_search_tags(self, client, auth_headers: dict):
        """测试搜索标签"""
        import time
        tag_name = f"工作文档_{int(time.time() * 1000)}"
        
        # 先创建标签
        client.post(
            "/api/v1/tags",
            headers=auth_headers,
            json={"name": tag_name, "color": "#3B82F6"}
        )
        
        # 搜索标签
        response = client.get(
            "/api/v1/tags/search?keyword=工作",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 100000
        assert len(data["data"]) > 0
    
    def test_update_tag(self, client, auth_headers: dict):
        """测试更新标签"""
        import time
        tag_name = f"旧标签_{int(time.time() * 1000)}"
        
        # 创建标签
        create_response = client.post(
            "/api/v1/tags",
            headers=auth_headers,
            json={"name": tag_name, "color": "#3B82F6"}
        )
        tag_id = create_response.json()["data"]["id"]
        
        # 更新标签
        response = client.session.patch(
            f"{client.base_url}/api/v1/tags/{tag_id}",
            headers=auth_headers,
            json={"name": f"新标签_{int(time.time() * 1000)}", "color": "#EF4444"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["color"] == "#EF4444"
    
    def test_delete_tag(self, client, auth_headers: dict):
        """测试删除标签"""
        import time
        tag_name = f"待删除标签_{int(time.time() * 1000)}"
        
        # 创建标签
        create_response = client.post(
            "/api/v1/tags",
            headers=auth_headers,
            json={"name": tag_name, "color": "#3B82F6"}
        )
        tag_id = create_response.json()["data"]["id"]
        
        # 删除标签
        response = client.delete(
            f"/api/v1/tags/{tag_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["code"] == 100000


class TestDocumentTags:
    """文档标签操作测试"""
    
    def test_add_tags_to_document(
        self, 
        client, 
        auth_headers: dict,
        test_document_id: str
    ):
        """测试为文档添加标签"""
        import time
        tag_name = f"文档标签1_{int(time.time() * 1000)}"
        
        # 创建标签
        tag_response = client.post(
            "/api/v1/tags",
            headers=auth_headers,
            json={"name": tag_name, "color": "#3B82F6"}
        )
        tag_id = tag_response.json()["data"]["id"]
        
        # 添加标签到文档
        response = client.post(
            f"/api/v1/documents/{test_document_id}/tags",
            headers=auth_headers,
            json={"tagIds": [tag_id]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 100000
        assert len(data["data"]) > 0
    
    def test_get_document_tags(
        self, 
        client, 
        auth_headers: dict,
        test_document_id: str
    ):
        """测试获取文档标签"""
        response = client.get(
            f"/api/v1/documents/{test_document_id}/tags",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 100000
        assert isinstance(data["data"], list)
    
    def test_remove_tags_from_document(
        self, 
        client, 
        auth_headers: dict,
        test_document_id: str
    ):
        """测试从文档移除标签"""
        import time
        tag_name = f"待移除标签_{int(time.time() * 1000)}"
        
        # 先添加标签
        tag_response = client.post(
            "/api/v1/tags",
            headers=auth_headers,
            json={"name": tag_name, "color": "#3B82F6"}
        )
        tag_id = tag_response.json()["data"]["id"]
        
        client.post(
            f"/api/v1/documents/{test_document_id}/tags",
            headers=auth_headers,
            json={"tagIds": [tag_id]}
        )
        
        # 移除标签
        response = client.delete(
            f"/api/v1/documents/{test_document_id}/tags",
            headers=auth_headers,
            json={"tagIds": [tag_id]}
        )
        
        assert response.status_code == 200
        assert response.json()["code"] == 100000


class TestDocumentShare:
    """文档分享测试"""
    
    def test_create_share_link(
        self, 
        client, 
        auth_headers: dict,
        test_document_id: str
    ):
        """测试创建分享链接"""
        response = client.post(
            f"/api/v1/share/documents/{test_document_id}",
            headers=auth_headers,
            json={
                "expiresInHours": 24,
                "password": "1234",
                "allowDownload": True,
                "maxAccessCount": 10
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == 100000
        assert "token" in data["data"]
        assert "shareUrl" in data["data"]
        assert data["data"]["hasPassword"] is True
        
        return data["data"]
    
    def test_access_share_link(
        self, 
        client,
        auth_headers: dict,
        test_document_id: str
    ):
        """测试访问分享链接"""
        # 先创建分享链接
        share_response = client.post(
            f"/api/v1/share/documents/{test_document_id}",
            headers=auth_headers,
            json={
                "expiresInHours": 24,
                "password": "1234",
                "allowDownload": True
            }
        )
        share_token = share_response.json()["data"]["token"]
        
        # 访问分享链接（无需登录）
        response = client.post(
            f"/api/v1/share/{share_token}/access",
            json={"password": "1234"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 100000
        assert "documentId" in data["data"]
    
    def test_access_share_link_wrong_password(
        self, 
        client,
        auth_headers: dict,
        test_document_id: str
    ):
        """测试使用错误密码访问分享链接"""
        # 创建分享链接
        share_response = client.post(
            f"/api/v1/share/documents/{test_document_id}",
            headers=auth_headers,
            json={
                "expiresInHours": 24,
                "password": "1234",
                "allowDownload": True
            }
        )
        share_token = share_response.json()["data"]["token"]
        
        # 使用错误密码访问
        response = client.post(
            f"/api/v1/share/{share_token}/access",
            json={"password": "wrong"}
        )
        
        assert response.status_code == 403
    
    def test_get_document_share_links(
        self, 
        client, 
        auth_headers: dict,
        test_document_id: str
    ):
        """测试获取文档的所有分享链接"""
        response = client.get(
            f"/api/v1/share/documents/{test_document_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 100000
        assert isinstance(data["data"], list)
    
    def test_revoke_share_link(
        self, 
        client, 
        auth_headers: dict,
        test_document_id: str
    ):
        """测试撤销分享链接"""
        # 创建分享链接
        share_response = client.post(
            f"/api/v1/share/documents/{test_document_id}",
            headers=auth_headers,
            json={"expiresInHours": 24}
        )
        share_id = share_response.json()["data"]["id"]
        
        # 撤销分享链接
        response = client.delete(
            f"/api/v1/share/{share_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["code"] == 100000


class TestBatchUpload:
    """批量上传测试"""
    
    def test_batch_upload_documents(
        self, 
        client, 
        auth_headers: dict
    ):
        """测试批量上传文档"""
        # 创建简单的 PDF 测试文件
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
        
        files = []
        for i in range(3):
            files.append(
                ("files", (f"test_doc_{i+1}.pdf", pdf_content, "application/pdf"))
            )
        
        response = client.post(
            "/api/v1/documents/batch-upload",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == 100000
        assert "batchId" in data["data"]
        assert data["data"]["totalFiles"] == 3
        assert len(data["data"]["documentIds"]) > 0
        
        return data["data"]["batchId"]
    
    def test_get_batch_status(
        self, 
        client, 
        auth_headers: dict
    ):
        """测试获取批量上传状态"""
        # 创建简单的 PDF 测试文件
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
        
        files = [
            ("files", ("test1.pdf", pdf_content, "application/pdf")),
            ("files", ("test2.pdf", pdf_content, "application/pdf"))
        ]
        
        upload_response = client.post(
            "/api/v1/documents/batch-upload",
            headers=auth_headers,
            files=files
        )
        batch_id = upload_response.json()["data"]["batchId"]
        
        # 获取状态
        response = client.get(
            f"/api/v1/documents/batch/{batch_id}/status",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 100000
        assert "progress" in data["data"]
        assert "documents" in data["data"]
    
    def test_batch_upload_too_many_files(
        self, 
        client, 
        auth_headers: dict
    ):
        """测试上传超过限制的文件数"""
        # 创建简单的 PDF 内容
        pdf_content = b"%PDF-1.4\n%%EOF"
        
        # 创建11个文件（超过限制）
        files = []
        for i in range(11):
            files.append(
                ("files", (f"test_{i}.pdf", pdf_content, "application/pdf"))
            )
        
        response = client.post(
            "/api/v1/documents/batch-upload",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 400
