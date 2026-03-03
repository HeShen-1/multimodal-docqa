# Docker 部署指南

## 概述

使用 Docker 运行 PostgreSQL 和 Redis，简化环境配置和管理。

---

## 快速启动

### 方法一：使用脚本（推荐）

```bash
# 启动 PostgreSQL 和 Redis
start_docker.bat

# 停止服务
stop_docker.bat
```

### 方法二：手动启动

```bash
# 启动所有服务
docker-compose up -d

# 仅启动 PostgreSQL 和 Redis
docker-compose up -d postgres redis

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 停止并删除数据卷（慎用！）
docker-compose down -v
```

---

## 服务配置

### PostgreSQL
- **端口**: 5432
- **数据库**: multimodal_docqa
- **用户名**: postgres
- **密码**: postgres
- **数据持久化**: Docker Volume `postgres_data`

### Redis
- **端口**: 6379
- **持久化**: AOF 模式
- **数据持久化**: Docker Volume `redis_data`

---

## 完整启动流程

### 1. 启动 Docker 服务

```bash
# 启动 PostgreSQL 和 Redis
start_docker.bat
```

等待约 10 秒，确保服务完全启动。

### 2. 初始化数据库

```bash
# 激活 conda 环境
conda activate multimodal-docqa

# 初始化 Phase 4 数据库
python scripts/init_phase4_db.py
```

### 3. 启动 Celery Worker

```bash
start_celery.bat
```

### 4. 启动 FastAPI 服务器

```bash
python -m uvicorn app.main:app --reload
```

---

## 数据管理

### 备份数据库

```bash
# 备份 PostgreSQL
docker exec multimodal-docqa-postgres pg_dump -U postgres multimodal_docqa > backup.sql

# 备份 Redis
docker exec multimodal-docqa-redis redis-cli SAVE
docker cp multimodal-docqa-redis:/data/dump.rdb ./redis_backup.rdb
```

### 恢复数据库

```bash
# 恢复 PostgreSQL
docker exec -i multimodal-docqa-postgres psql -U postgres multimodal_docqa < backup.sql

# 恢复 Redis
docker cp ./redis_backup.rdb multimodal-docqa-redis:/data/dump.rdb
docker-compose restart redis
```

### 清空数据

```bash
# 清空 PostgreSQL 数据库
docker exec -it multimodal-docqa-postgres psql -U postgres -c "DROP DATABASE multimodal_docqa;"
docker exec -it multimodal-docqa-postgres psql -U postgres -c "CREATE DATABASE multimodal_docqa;"

# 清空 Redis
docker exec multimodal-docqa-redis redis-cli FLUSHALL
```

---

## 连接信息

### 从本地连接

**PostgreSQL:**
```
Host: localhost
Port: 5432
Database: multimodal_docqa
User: postgres
Password: postgres
```

**Redis:**
```
Host: localhost
Port: 6379
Password: (无)
```

### 从 Docker 容器内连接

**PostgreSQL:**
```
Host: postgres
Port: 5432
```

**Redis:**
```
Host: redis
Port: 6379
```

---

## 故障排查

### 1. 端口被占用

**问题**: `Error: port is already allocated`

**解决方案**:
```bash
# 查看端口占用
netstat -ano | findstr :5432
netstat -ano | findstr :6379

# 停止占用端口的进程或修改 docker-compose.yml 中的端口映射
```

### 2. 容器无法启动

**问题**: 容器状态为 `Exited`

**解决方案**:
```bash
# 查看容器日志
docker-compose logs postgres
docker-compose logs redis

# 重新创建容器
docker-compose down
docker-compose up -d
```

### 3. 数据库连接失败

**问题**: `could not connect to server`

**解决方案**:
```bash
# 检查容器状态
docker-compose ps

# 检查健康状态
docker inspect multimodal-docqa-postgres | grep Health

# 等待容器完全启动（约 10-15 秒）
```

### 4. Redis 连接失败

**问题**: `Error connecting to Redis`

**解决方案**:
```bash
# 测试 Redis 连接
docker exec multimodal-docqa-redis redis-cli ping

# 应该返回 PONG
```

---

## 高级配置

### 自定义配置

编辑 `docker-compose.yml` 修改配置：

```yaml
# PostgreSQL 配置
postgres:
  environment:
    POSTGRES_USER: myuser          # 自定义用户名
    POSTGRES_PASSWORD: mypassword  # 自定义密码
    POSTGRES_DB: mydb              # 自定义数据库名

# Redis 配置
redis:
  command: redis-server --requirepass mypassword  # 设置密码
```

### 资源限制

```yaml
postgres:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '1'
        memory: 1G

redis:
  deploy:
    resources:
      limits:
        cpus: '1'
        memory: 512M
```

---

## 监控和维护

### 查看资源使用

```bash
# 查看容器资源使用
docker stats multimodal-docqa-postgres multimodal-docqa-redis

# 查看磁盘使用
docker system df
```

### 清理未使用资源

```bash
# 清理未使用的镜像
docker image prune

# 清理未使用的容器
docker container prune

# 清理未使用的卷
docker volume prune

# 清理所有未使用资源
docker system prune -a
```

### 更新镜像

```bash
# 拉取最新镜像
docker-compose pull

# 重新创建容器
docker-compose up -d --force-recreate
```

---

## 生产环境建议

### 1. 安全配置

- ✅ 修改默认密码
- ✅ 限制网络访问
- ✅ 启用 SSL/TLS
- ✅ 定期备份数据

### 2. 性能优化

```yaml
# PostgreSQL 性能优化
postgres:
  environment:
    POSTGRES_SHARED_BUFFERS: 256MB
    POSTGRES_EFFECTIVE_CACHE_SIZE: 1GB
    POSTGRES_WORK_MEM: 16MB

# Redis 性能优化
redis:
  command: >
    redis-server
    --maxmemory 512mb
    --maxmemory-policy allkeys-lru
    --save 900 1
    --save 300 10
```

### 3. 高可用配置

- 使用 Docker Swarm 或 Kubernetes
- 配置主从复制
- 使用负载均衡
- 配置自动故障转移

---

## 完整的 Docker 化部署（可选）

如果想将整个应用 Docker 化，取消 `docker-compose.yml` 中的注释：

```bash
# 构建并启动所有服务
docker-compose up -d --build

# 包括：
# - PostgreSQL
# - Redis
# - FastAPI Backend
# - Celery Worker
```

这样可以实现完全容器化的部署。

---

## 常用命令速查

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f [service_name]

# 进入容器
docker exec -it multimodal-docqa-postgres bash
docker exec -it multimodal-docqa-redis sh

# 查看状态
docker-compose ps

# 查看资源
docker stats
```

---

**更新时间**: 2026-02-27  
**版本**: Docker v1.0

