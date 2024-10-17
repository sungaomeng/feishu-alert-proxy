# 使用官方 Python 镜像作为基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 复制当前目录内容到容器中的 /app 目录
COPY . /app

# 安装依赖项
RUN pip install --no-cache-dir -r requirements.txt

# 设置环境变量
ENV FEISHU_APP_ID=xxx
ENV FEISHU_APP_SECRET=xxx

# 暴露端口
EXPOSE 8000

# 运行 Python 脚本
CMD ["python", "app.py"]
