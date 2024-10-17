# Feishu Alert Proxy

Feishu Alert Proxy 是一个用于接收Grafana告警消息并将其转发到飞书群聊的代理服务。该服务使用 Flask 框架构建，并通过 Docker 容器化部署。

## 功能描述

- 接收告警消息（消息格式为 JSON）
- 根据配置的规则匹配告警消息内容
- 将匹配到的告警消息转发到指定的飞书群聊
- 支持通过环境变量配置飞书应用的 `app_id` 和 `app_secret`
- 支持监听配置文件变化并动态加载规则

## 项目结构
```bash
.
├── Dockerfile
├── README.md
├── app.py
├── requirements.txt
└── rules.json
```

- `Dockerfile`：用于构建 Docker 镜像的文件
- `README.md`：项目说明文档
- `alert-proxy.py`：主 Python 脚本，包含服务逻辑
- `requirements.txt`：Python 依赖项列表
- `rules.json`：规则配置文件

## 逻辑概述

1. 启动 Flask Web 服务，监听告警消息的 POST 请求。
2. 从环境变量中读取飞书应用的 `app_id` 和 `app_secret`。
3. 加载 `rules.json` 文件中的规则，并对每条规则进行条件解析。
4. 接收到告警消息后，根据规则匹配消息内容。
5. 将匹配到的告警消息转发到指定的飞书群聊。
6. 监听 `rules.json` 文件的变化，并动态加载更新的规则。

## 配置

### 环境变量

需要设置以下环境变量：

- `FEISHU_APP_ID`：飞书应用的 App ID
- `FEISHU_APP_SECRET`：飞书应用的 App Secret

### 规则配置文件

规则配置文件 `rules.json` 的格式如下：

```json
[
    {
        "keywords": ["告警"],
        "conditions": "lambda text: 'info' in text and 'APM' not in text and 'Test1' not in text",
        "chat_name": "【通知】Gitlab系统通知"
    },
    {
        "keywords": ["warning"],
        "conditions": "lambda text: 'warning' in text and 'APM' not in text and 'Test' not in text",
        "chat_name": "【监控告警】【warning】DevOps Group"
    },
    {
        "keywords": ["网关5XX状态码"],
        "conditions": "lambda text: True",
        "chat_name": "【监控告警】【error】Apisix相关"
    },
    {
        "keywords": [],
        "conditions": "lambda text: True",
        "chat_name": "【监控告警】【warning】Apisix相关"
    }
]
```

## 启动步骤

### 使用 Docker 启动

```bash
docker build -t alert-proxy .
docker run -d -p 8000:8000 --name alert-proxy -e FEISHU_APP_ID='your_app_id' -e FEISHU_APP_SECRET='your_app_secret' feishu-alert-proxy
```
请将 your_app_id 和 your_app_secret 替换为实际的飞书应用的 App ID 和 App Secret。


## 示例

### 需求
1. Grafana 告警到飞书
2. 告警要使用飞书卡片(要易读,要好看)
3. 不同的告警需要发送给不同的飞书群
  - 网关4XX告警 发送到 网关4XX告警群
  - 网关5XX告警 发送到 网关5XX告警群
  - 默认兜底给 Grafana告警兜底群

### 环境
[Grafana](https://github.com/grafana/grafana) + [PrometheusAlert](https://github.com/feiyu563/PrometheusAlert) + [feishu-alert-proxy](https://github.com/sungaomeng/feishu-alert-proxy)

### 流程
1. Grafana 触发告警 -> PrometheusAlert (Webhook Url: http://prometheus-alert-svs.ops:8080/prometheusalert?type=fs&tpl=prometheus-fs&fsurl=http://feishu-alert-proxy-svs:8000/webhook)
2. Prometheus 将收到的消息经过自定义模板渲染成消息文本转发给 feishu-alert-proxy
3. feishu-alert-proxy 根据配置文件(rules.json)中定义的规则和群聊对应关系去过滤收到的消息并发送到飞书群聊

PrometheusAlert prometheus-fs 自定义模版(适配Grafana)
```
{{ $var := .externalURL}}{{ range $k,$v:=.alerts }}{{if eq $v.status "resolved"}}✅**[恢复通知]({{$v.generatorURL}})**
**告警名称:** {{$v.labels.alertname}}
**告警级别:** {{$v.labels.level}}
**告警分组:** {{$v.labels.grafana_folder}}
**告警状态:** {{$v.status}}
**开始时间:** {{TimeFormat $v.startsAt "2006-01-02 15:04:05"}}
**结束时间:** {{TimeFormat $v.endsAt "2006-01-02 15:04:05"}} 
**告警详情:**
{{$v.annotations.summary}}
{{$v.annotations.description}}
[屏蔽]({{$v.silenceURL}}) | [面板]({{$v.panelURL}}) | [告警规则]({{$v.generatorURL}})
{{else}}🆘**[报警通知]({{$v.generatorURL}})**
**告警名称:** {{$v.labels.alertname}}
**告警级别:** {{$v.labels.level}}
**告警分组:** {{$v.labels.grafana_folder}}
**告警状态:** {{$v.status}}
**开始时间:** {{TimeFormat $v.startsAt "2006-01-02 15:04:05"}}
{{$v.annotations.summary}}
{{$v.annotations.description}}
[屏蔽]({{$v.silenceURL}}) | [面板]({{$v.panelURL}}) | [告警规则]({{$v.generatorURL}})
{{end}}
{{ end }}  
```
