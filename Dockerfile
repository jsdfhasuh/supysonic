# 使用 Python 3.11 Alpine 作为基础镜像 (更稳定的选择)
FROM python:3.11-alpine

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apk add --no-cache \
    # 音频处理相关
    ffmpeg \
    # 可选的转码工具
    lame \
    flac \
    # 时区支持
    tzdata \
    # SQLite 支持
    sqlite \
    # 图像处理库依赖
    jpeg-dev \
    zlib-dev \
    # 如果需要 MySQL/MariaDB 支持
    mariadb-connector-c-dev 


# 设置时区为北京时间
RUN cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone

# 拷贝项目文件
COPY . /app/

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt && \
    # 清理缓存
    find /app -type d -name __pycache__ -exec rm -rf {} +

# 暴露端口
EXPOSE 5000

# 启动命令
ENTRYPOINT ["python", "/app/run_supysonic.py"]