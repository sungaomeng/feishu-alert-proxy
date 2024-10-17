import json
import logging
import os
import requests
import time
import uuid
from flask import Flask, request, jsonify
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 从环境变量中读取飞书应用的 app_id 和 app_secret
FEISHU_APP_ID = os.getenv('FEISHU_APP_ID')
FEISHU_APP_SECRET = os.getenv('FEISHU_APP_SECRET')

# 配置文件路径
CONFIG_FILE = 'rules.json'

group_rules = []

def load_rules():
    global group_rules
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as file:
            rules = json.load(file)
            for rule in rules:
                rule['conditions'] = eval(rule['conditions'])
            group_rules = rules
            logging.info("规则加载成功")
    except Exception as e:
        logging.error(f"加载规则失败: {e}")

class ConfigFileEventHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(CONFIG_FILE):
            logging.info("检测到配置文件修改，重新加载规则")
            load_rules()

# 监听配置文件变化
event_handler = ConfigFileEventHandler()
observer = Observer()
observer.schedule(event_handler, path='.', recursive=False)
observer.start()

# 初始加载规则
load_rules()

def get_token(app_id, app_secret, trace_id):
    logging.info(f"[{trace_id}] 获取 tenant_access_token 开始")
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = json.dumps({"app_id": app_id, "app_secret": app_secret})
    headers = {"Content-Type": "application/json; charset=utf-8"}
    response = requests.post(url, headers=headers, data=data)
    response_data = response.json()
    if "tenant_access_token" in response_data:
        logging.info(f"[{trace_id}] 获取 tenant_access_token 成功")
        return response_data["tenant_access_token"]
    else:
        logging.error(f"[{trace_id}] 获取 tenant_access_token 失败: {response_data}")
        raise ValueError(f"[{trace_id}] Failed to get tenant access token: {response_data}")

def get_chat_id_by_name(token, chat_name, trace_id):
    logging.info(f"[{trace_id}] 获取 chat_id 开始")
    url = "https://open.feishu.cn/open-apis/im/v1/chats?page_size=100"
    headers = {"Authorization": "Bearer " + token}
    response = requests.get(url, headers=headers)
    response_data = response.json()

    if "data" in response_data and "items" in response_data["data"]:
        for chat in response_data["data"]["items"]:
            # logging.info(f"[{trace_id}] 检查群聊: {chat['name']}")
            if chat["name"] == chat_name:
                logging.info(f"[{trace_id}] 获取 chat_id 成功: {chat['chat_id']}")
                return chat["chat_id"]

    logging.error(f"[{trace_id}] 获取 chat_id 失败: {response_data}")
    logging.error(f"[{trace_id}] 未找到匹配的群聊名称: {chat_name}")
    raise ValueError(f"[{trace_id}] Failed to get chat id: {response_data}")

def send_message(chat_id, message, token, template_color, trace_id, title):
    logging.info(f"[{trace_id}] 发送消息到飞书群聊: {chat_id}")
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json; charset=utf-8"
    }
    payload = {
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": json.dumps({
            "config": {
                "wide_screen_mode": True,
                "enable_forward": True
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "content": message,
                        "tag": "lark_md"
                    }
                }
            ],
            "header": {
                "title": {
                    "content": title,
                    "tag": "plain_text"
                },
                "template": template_color
            }
        })
    }
    start_time = time.time()
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    end_time = time.time()
    response_data = response.json()
    if response.status_code == 200:
        logging.info(f"[{trace_id}] 消息发送成功, 耗时: {end_time - start_time:.2f}秒")
    else:
        logging.error(f"[{trace_id}] 消息发送失败: {response_data}")
        raise ValueError(f"[{trace_id}] Failed to send message: {response_data}")

def determine_template_color(text_content):
    if '恢复通知' in text_content:
        return 'green'
    elif '报警通知' in text_content:
        return 'red'
    else:
        return 'blue'  # 默认颜色

@app.route('/ping', methods=['GET'])
def ping():
    return "pong", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    trace_id = str(uuid.uuid4())
    alert = request.json  # 假设告警消息是 JSON 格式
    text_content = alert.get('text', '')
    title = alert.get('title', 'AlertCenter')  # 从 JSON 中获取 title，如果不存在则使用默认值
    logging.info(f"[{trace_id}] 接收到告警: {json.dumps(alert, ensure_ascii=False)}")

    # 根据消息内容设置模板颜色
    template_color = determine_template_color(text_content)

    tenant_access_token = get_token(FEISHU_APP_ID, FEISHU_APP_SECRET, trace_id)

    matched_rule = None
    for rule in group_rules:
        if any(keyword in text_content for keyword in rule['keywords']) and rule['conditions'](text_content):
            matched_rule = rule
            logging.info(f"[{trace_id}] 匹配到规则: {rule}")
            try:
                chat_id = get_chat_id_by_name(tenant_access_token, rule['chat_name'], trace_id)
                send_message(chat_id, text_content, tenant_access_token, template_color, trace_id, title)
                logging.info(f"[{trace_id}] Message sent to group: {rule['chat_name']} with chat_id: {chat_id}")
                break  # 满足第一个规则后停止处理后续规则
            except Exception as e:
                logging.error(f"[{trace_id}] Error sending message to group: {rule['chat_name']} with keywords: {rule['keywords']}, error: {e}")

    # 如果没有匹配到任何规则，执行兜底规则
    if matched_rule is None:
        logging.info(f"[{trace_id}] 未匹配到任何规则，执行兜底规则")
        try:
            fallback_rule = group_rules[-1]  # 兜底规则是最后一个
            chat_id = get_chat_id_by_name(tenant_access_token, fallback_rule['chat_name'], trace_id)
            send_message(chat_id, text_content, tenant_access_token, template_color, trace_id, title)
            logging.info(f"[{trace_id}] Message sent to fallback group: {fallback_rule['chat_name']} with chat_id: {chat_id}")
        except Exception as e:
            logging.error(f"[{trace_id}] Error sending message to fallback group: {fallback_rule['chat_name']}, error: {e}")

    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
