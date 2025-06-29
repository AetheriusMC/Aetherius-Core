# 快速入门指南

本指南将帮助您在几分钟内启动和运行 Aetherius Core。

## 前提条件

- Python 3.11+
- Java 17+ (用于运行 Minecraft 服务器)
- 一个 Minecraft 服务器 JAR 文件

## 安装步骤

### 1. 获取代码

```bash
git clone https://github.com/AetheriusMC/Aetherius-Core.git
cd Aetherius-Core
```

### 2. 安装依赖

```bash
pip install -e .
```

### 3. 准备服务器

```bash
# 创建服务器目录
mkdir -p server

# 下载或复制您的 Minecraft 服务器 JAR
# 例如：下载 Paper 服务器
wget https://api.papermc.io/v2/projects/paper/versions/1.20.1/builds/196/downloads/paper-1.20.1-196.jar -O server/server.jar

# 或者复制现有的服务器文件
# cp /path/to/your/server.jar server/server.jar
```

### 4. 初始化配置

```bash
# 创建基本配置
mkdir -p config
cat > config/config.yaml << 'EOF'
# Aetherius Core 配置
server:
  jar_path: server/server.jar
  java_executable: java
  java_args:
    - -Xmx2G
    - -Xms1G
    - -XX:+UseG1GC
  working_directory: server
  auto_restart: true
  restart_delay: 5.0

logging:
  level: INFO
  console_output: true

security:
  enable_authentication: false  # 开发时可关闭

monitoring:
  enable_metrics: true
  health_check_interval: 30

web:
  enabled: true
  host: localhost
  port: 8080
EOF
```

## 启动系统

### 选项 1: 开发模式 (推荐用于测试)

```bash
python scripts/start.py
```

### 选项 2: 完整启动

```bash
./bin/aetherius start
```

### 选项 3: 仅启动 Web 控制台

```bash
./bin/aetherius web
```

然后在浏览器中访问 http://localhost:8080

## 基本使用

### 查看系统状态

```bash
./bin/aetherius system info
```

### 执行服务器命令

```bash
./bin/aetherius cmd "say Hello from Aetherius!"
```

### 启动交互式控制台

```bash
./bin/aetherius console
```

在控制台中，您可以：
- 输入服务器命令
- 查看实时日志
- 监控服务器性能

## 故障排除

### 常见问题

1. **端口冲突**
   ```bash
   # 修改 Web 控制台端口
   ./bin/aetherius web --port 8081
   ```

2. **Java 未找到**
   ```bash
   # 指定 Java 路径
   export JAVA_HOME=/path/to/java
   ```

3. **权限问题**
   ```bash
   # 确保脚本可执行
   chmod +x bin/aetherius
   chmod +x scripts/start.py
   ```

### 查看日志

```bash
# 查看系统日志
tail -f data/logs/aetherius.log

# 查看服务器日志
tail -f server/logs/latest.log
```

## 下一步

1. **配置自定义设置**: 编辑 `config/config.yaml`
2. **安装插件**: 将插件放到 `data/plugins/` 目录
3. **启用组件**: 使用 Web 控制台管理组件
4. **监控性能**: 查看内置的性能监控

## 获取帮助

- 查看完整文档: [docs/](../README.md)
- 问题反馈: [GitHub Issues](https://github.com/AetheriusMC/Aetherius-Core/issues)
- 命令帮助: `./bin/aetherius --help`