#!/bin/bash

echo "🚀 开始部署游戏数据分析引擎..."

if [ ! -f ".env" ]; then
    echo "❌ 未找到 .env 文件。生产部署需要 SECRET_KEY、INITIAL_ADMIN_PASSWORD 和 PAYMENT_WEBHOOK_SECRET。"
    echo "示例："
    echo "  SECRET_KEY=$(openssl rand -hex 32)"
    echo "  INITIAL_ADMIN_PASSWORD=<your-admin-password>"
    echo "  PAYMENT_WEBHOOK_SECRET=$(openssl rand -hex 32)"
    exit 1
fi

echo "1️⃣ 构建Docker镜像..."
docker-compose build

echo "2️⃣ 启动服务..."
docker-compose up -d

echo "3️⃣ 等待服务启动..."
sleep 10

echo "4️⃣ 检查服务状态..."
docker-compose ps

echo "5️⃣ 验证服务健康..."
curl -s http://localhost:8000/api/health

echo ""
echo "✅ 部署完成！"
echo "📍 服务地址: http://localhost:8000"
echo "📖 API文档: http://localhost:8000/docs"
echo "🔧 管理命令:"
echo "   - 查看日志: docker-compose logs -f"
echo "   - 停止服务: docker-compose down"
echo "   - 重启服务: docker-compose restart"
