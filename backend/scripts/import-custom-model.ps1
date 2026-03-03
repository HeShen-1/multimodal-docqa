# 导入本地微调模型到 Ollama Docker

Write-Host "=========================================="
Write-Host "  导入本地微调模型到 Ollama"
Write-Host "=========================================="
Write-Host ""

# 配置
$MODEL_NAME = "qwen3-vl:2b-thinking-q4_K_M"
$LOCAL_MODEL_PATH = "D:\path\to\your\model\qwen3-vl-2b-thinking-q4_K_M.gguf"  # 修改为你的模型路径
$MODELFILE_PATH = ".\models\Modelfile.qwen3-vl-custom"

# 检查模型文件是否存在
if (-not (Test-Path $LOCAL_MODEL_PATH)) {
    Write-Host "❌ 模型文件不存在: $LOCAL_MODEL_PATH" -ForegroundColor Red
    Write-Host "请修改脚本中的 LOCAL_MODEL_PATH 变量" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ 找到模型文件: $LOCAL_MODEL_PATH" -ForegroundColor Green
$fileSize = (Get-Item $LOCAL_MODEL_PATH).Length / 1GB
Write-Host "  文件大小: $([math]::Round($fileSize, 2)) GB" -ForegroundColor Cyan
Write-Host ""

# 检查 Ollama 容器是否运行
Write-Host "检查 Ollama 容器状态..." -ForegroundColor Yellow
$containerStatus = docker ps --filter "name=multimodal-docqa-ollama" --format "{{.Status}}"

if (-not $containerStatus) {
    Write-Host "❌ Ollama 容器未运行" -ForegroundColor Red
    Write-Host "请先启动容器: docker-compose up -d ollama" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Ollama 容器运行中" -ForegroundColor Green
Write-Host ""

# 方法选择
Write-Host "请选择导入方法:" -ForegroundColor Cyan
Write-Host "1. 从 GGUF 文件创建（推荐）" -ForegroundColor White
Write-Host "2. 从 Modelfile 创建" -ForegroundColor White
Write-Host "3. 直接复制到容器" -ForegroundColor White
$choice = Read-Host "请输入选项 (1-3)"

switch ($choice) {
    "1" {
        # 方法 1: 从 GGUF 文件创建
        Write-Host ""
        Write-Host "=========================================="
        Write-Host "  方法 1: 从 GGUF 文件创建"
        Write-Host "=========================================="
        Write-Host ""
        
        # 复制模型文件到容器
        Write-Host "📦 复制模型文件到容器..." -ForegroundColor Yellow
        docker cp $LOCAL_MODEL_PATH multimodal-docqa-ollama:/tmp/model.gguf
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ 复制失败" -ForegroundColor Red
            exit 1
        }
        Write-Host "✓ 复制成功" -ForegroundColor Green
        Write-Host ""
        
        # 创建 Modelfile
        Write-Host "📝 创建 Modelfile..." -ForegroundColor Yellow
        $modelfileContent = @"
FROM /tmp/model.gguf
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
"@
        
        $modelfileContent | docker exec -i multimodal-docqa-ollama sh -c "cat > /tmp/Modelfile"
        Write-Host "✓ Modelfile 创建成功" -ForegroundColor Green
        Write-Host ""
        
        # 创建模型
        Write-Host "🔨 创建模型: $MODEL_NAME" -ForegroundColor Yellow
        Write-Host "这可能需要几分钟..." -ForegroundColor Cyan
        docker exec multimodal-docqa-ollama ollama create $MODEL_NAME -f /tmp/Modelfile
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ 模型创建成功" -ForegroundColor Green
        } else {
            Write-Host "❌ 模型创建失败" -ForegroundColor Red
            exit 1
        }
        
        # 清理临时文件
        Write-Host ""
        Write-Host "🧹 清理临时文件..." -ForegroundColor Yellow
        docker exec multimodal-docqa-ollama rm /tmp/model.gguf /tmp/Modelfile
        Write-Host "✓ 清理完成" -ForegroundColor Green
    }
    
    "2" {
        # 方法 2: 从 Modelfile 创建
        Write-Host ""
        Write-Host "=========================================="
        Write-Host "  方法 2: 从 Modelfile 创建"
        Write-Host "=========================================="
        Write-Host ""
        
        if (-not (Test-Path $MODELFILE_PATH)) {
            Write-Host "❌ Modelfile 不存在: $MODELFILE_PATH" -ForegroundColor Red
            exit 1
        }
        
        # 复制模型文件和 Modelfile
        Write-Host "📦 复制文件到容器..." -ForegroundColor Yellow
        docker cp $LOCAL_MODEL_PATH multimodal-docqa-ollama:/tmp/model.gguf
        docker cp $MODELFILE_PATH multimodal-docqa-ollama:/tmp/Modelfile
        
        # 修改 Modelfile 中的路径
        docker exec multimodal-docqa-ollama sed -i 's|FROM .*|FROM /tmp/model.gguf|' /tmp/Modelfile
        
        Write-Host "✓ 文件复制成功" -ForegroundColor Green
        Write-Host ""
        
        # 创建模型
        Write-Host "🔨 创建模型: $MODEL_NAME" -ForegroundColor Yellow
        docker exec multimodal-docqa-ollama ollama create $MODEL_NAME -f /tmp/Modelfile
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ 模型创建成功" -ForegroundColor Green
        } else {
            Write-Host "❌ 模型创建失败" -ForegroundColor Red
            exit 1
        }
        
        # 清理
        docker exec multimodal-docqa-ollama rm /tmp/model.gguf /tmp/Modelfile
    }
    
    "3" {
        # 方法 3: 直接复制
        Write-Host ""
        Write-Host "=========================================="
        Write-Host "  方法 3: 直接复制到容器"
        Write-Host "=========================================="
        Write-Host ""
        
        Write-Host "📦 复制模型到 Ollama 数据目录..." -ForegroundColor Yellow
        
        # 获取模型存储路径
        $modelDir = "/root/.ollama/models/blobs"
        
        # 复制文件
        docker cp $LOCAL_MODEL_PATH "multimodal-docqa-ollama:$modelDir/sha256-custom"
        
        Write-Host "✓ 复制完成" -ForegroundColor Green
        Write-Host ""
        Write-Host "⚠️  注意: 你需要手动创建模型清单" -ForegroundColor Yellow
        Write-Host "   参考: https://github.com/ollama/ollama/blob/main/docs/import.md" -ForegroundColor Cyan
    }
    
    default {
        Write-Host "❌ 无效的选项" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "  验证安装"
Write-Host "=========================================="
Write-Host ""

# 列出模型
Write-Host "📋 已安装的模型:" -ForegroundColor Yellow
docker exec multimodal-docqa-ollama ollama list

Write-Host ""
Write-Host "=========================================="
Write-Host "  完成！"
Write-Host "=========================================="
Write-Host ""
Write-Host "模型名称: $MODEL_NAME" -ForegroundColor Green
Write-Host ""
Write-Host "测试模型:" -ForegroundColor Yellow
Write-Host "  docker exec multimodal-docqa-ollama ollama run $MODEL_NAME" -ForegroundColor Cyan
Write-Host ""
Write-Host "在代码中使用:" -ForegroundColor Yellow
Write-Host "  OLLAMA_EMBEDDING_MODEL=$MODEL_NAME" -ForegroundColor Cyan
Write-Host ""

