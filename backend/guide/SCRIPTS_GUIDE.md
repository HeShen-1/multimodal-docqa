# 脚本使用指南

本目录包含用于快速配置、启动和测试多模态文档问答系统的批处理脚本。

## 📋 脚本列表

### 1. 环境配置脚本

#### `setup.bat` - 统一环境配置脚本

**用法：**
```bash
# 配置指定Phase
setup.bat 1    # 配置Phase 1（用户认证）
setup.bat 2    # 配置Phase 2（对话管理）
setup.bat 3    # 配置Phase 3（缓存优化）
setup.bat 4    # 配置Phase 4（文档管理增强）

# 完整配置所有Phase
setup.bat full
```

**功能：**
- ✅ 激活conda环境
- ✅ 检查并创建.env配置文件
- ✅ 安装Python依赖
- ✅ 检查PostgreSQL和Redis连接
- ✅ 初始化数据库表

---

### 2. 服务管理脚本

#### `start_services.bat` - 启动后台服务

**用法：**
```bash
start_services.bat
```

**功能：**
- 启动PostgreSQL容器（端口5432）
- 启动Redis容器（端口6379）
- 启动Celery Worker容器
- 等待服务健康检查通过

#### `stop_services.bat` - 停止后台服务

**用法：**
```bash
stop_services.bat
```

**功能：**
- 停止所有Docker容器
- 保留数据卷（可选删除）

#### `start_server.bat` - 启动FastAPI服务器

**用法：**
```bash
start_server.bat
```

**功能：**
- 启动FastAPI开发服务器（支持热重载）
- 访问地址：http://localhost:8000
- API文档：http://localhost:8000/docs

---

### 3. 测试脚本

#### `run_tests.bat` - 统一测试运行脚本

**用法：**
```bash
# 运行指定Phase测试
run_tests.bat 2    # 运行Phase 2测试
run_tests.bat 3    # 运行Phase 3测试
run_tests.bat 4    # 运行Phase 4测试

# 运行所有测试
run_tests.bat all
```

**功能：**
- 激活conda环境
- 运行pytest测试
- 显示详细测试结果

---

## 🚀 快速开始流程

### 首次部署

```bash
# 1. 配置环境（选择需要的Phase）
setup.bat 4

# 2. 启动后台服务
start_services.bat

# 3. 启动API服务器
start_server.bat

# 4. 访问API文档
# 浏览器打开: http://localhost:8000/docs
```

### 日常开发

```bash
# 启动服务
start_services.bat

# 启动开发服务器
start_server.bat

# 运行测试
run_tests.bat 4
```

### 停止服务

```bash
# 停止所有服务
stop_services.bat
```

---

## 📝 注意事项

### 前置要求

1. **Conda环境**：需要创建名为`multimodal-docqa`的conda环境
   ```bash
   conda create -n multimodal-docqa python=3.11
   ```

2. **Docker Desktop**：需要安装并启动Docker Desktop

3. **配置文件**：首次运行会自动创建`.env`文件，需要编辑配置

---

## 📚 相关文档

- **快速开始指南**：`Phase/QUICKSTART_PHASE*.md`
- **API文档**：`docs/apiDoc/API接口文档_v2.md`
- **架构文档**：`Phase/ARCHITECTURE.md`

---

**更新时间**：2026-02-27
