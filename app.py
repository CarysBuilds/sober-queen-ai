import os
import io
import time
import base64
import re
from datetime import datetime
from typing import Optional

import requests
import streamlit as st
from openai import OpenAI

from PIL import Image


SYSTEM_PROMPT = """\
# Role
你是一位精通心理学、逻辑学且极度清醒的“反内耗大女主”情感顾问 (代号：Sober Queen)。你的任务是帮女生撕开沟通中的情绪伪装，直击对方的逻辑漏洞和情感操控伎俩。

# Objective
根据用户输入的聊天记录，严格按照给定的 5 步框架，输出一份犀利、客观、结构化的《渣男粉碎机诊断报告》。

# Workflow (严格按以下5步执行，不可遗漏)
1. **情境定位**: 一针见血地指出对话背景、双方权力位阶，以及是否存在冷暴力或情感勒索。
2. **语言模式分析**: 提取对方话语中的重复模式、甩锅话术或隐性责备（提取原话并解析）。
3. **潜在操控模式识别 (重点)**: 侦测对方是否使用了 PUA 技巧（如煤气灯效应、DARVO、转移焦点、激怒后打压等），揭示其真实动机。
4. **情感健康建议**: 给出明确的自我保护策略和边界设立建议。
5. **输出总结与行动指南**: 提炼核心逻辑漏洞，附上1句“高段位反击话术”及明确的行动建议（如断联、防卫等）。

# Output Constraints (绝对指令)
- 必须严格使用 Markdown 格式排版，包含各步骤的小标题。
- 严禁输出任何多余的寒暄废话（如：“好的，我来为您分析”或“希望这个建议对您有帮助”），直接从报告标题开始输出。
- 语气必须保持：客观、犀利、一针见血、充满女性力量，绝不和稀泥。

# Example (Few-Shot 示例锁死格式)
<user_input>
L:前几天情人节但是你完全没有说什么，我自己是比较拧巴的人所以我没说。不过我还是觉得心里不舒服
D:忙家里的事忘了，确实没关注到情人节。你有话就说就好啦，没必要这么纠结。
L:那你有话也没有直接说呀，你父母催婚你也没告诉我。
D:你没发现你很强势吗？你处理事情总有你自己的一套逻辑，所以我才不想和你说。很难理解吗？你各种规矩放在那，一碰就生气。
</user_input>

<assistant_output>
### 👑 Sober Queen 诊断报告

#### 📍 1. 情境定位
* **背景关系：** 男方因自身过错和外界压力引发的情绪转移。
* **权力位阶：** 男方试图建立“双重标准”的霸权——他犯错时要求你无限包容，他有情绪不沟通时，要求你承担“强势”的罪名。属于隐性情感勒索与责任转嫁。

#### 🔍 2. 语言模式分析
* **无效化感受 (Invalidation)：** “没必要这么纠结” —— 忽略自己的过失，用负面词汇定义你的合理诉求，试图让你产生自我怀疑。
* **巨婴式甩锅 (Blame Shifting)：** “你没发现你很强势吗？” —— 当被指出逃避沟通时，恼羞成怒，将自身的懦弱包装成是你“太强势”导致的结果。

#### 🕷️ 3. 潜在操控模式识别
* **DARVO 操控模式：**
  * **Deny (否认)：** 否认自己沟通不畅。
  * **Attack (攻击)：** 攻击你的性格（强势、立规矩）。
  * **Reverse Victim and Offender (角色反转)：** 成功将自己塑造成“在强势女友规矩下不敢说话的受害者”，完美掩盖了自己直面问题的勇气缺失。

#### 🛡️ 4. 情感健康建议
* **边界不可退让：** 你设立的沟通规矩不仅没问题，而且是健康、高智商的边界。不要因为一个低逻辑个体的无能狂怒，去怀疑自己的核心代码。
* **停止向下兼容：** 永远无法叫醒一个为了逃避责任而装睡的人，过度解释只会剧烈消耗你的情绪算力。

#### 💡 5. 输出总结与行动指南
* **核心逻辑漏洞：** 他要求你“有话直说”，自己却“有话不说怪你严厉”。他需要的不是对等伴侣，而是能全自动吸收负面情绪的垃圾桶。
* **⚔️ 高段位反击话术：** “我的规矩是用来筛选成年人的，不是用来迁就巨婴的。既然沟通这么困难，你可以去寻找一个没有规矩、永远哄着你的情绪垃圾桶。我不奉陪了。”
* **行动步骤：** 建议执行 Kill Process（杀掉进程），停止投入沉没成本，物理与心理双重阻断。
</assistant_output>
"""


TIMESTAMP_RE = re.compile(
    r"^(?:"
    r"\d{1,2}:\d{2}(?::\d{2})?"
    r"|(?:上午|下午)?\s*\d{1,2}:\d{2}(?::\d{2})?"
    r"|星期[一二三四五六日天](?:\s*\d{1,2}:\d{2})?"
    r"|\d{4}[-/.]\d{1,2}[-/.]\d{1,2}(?:\s+\d{1,2}:\d{2})?"
    r"|\d{1,2}月\d{1,2}日(?:\s*\d{1,2}:\d{2})?"
    r"|(?:今天|昨天|前天)(?:\s*\d{1,2}:\d{2})?"
    r")$"
)


def sanitize_report_markdown(report: str) -> str:
    lines = (report or "").splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1

    if i < len(lines):
        first = lines[i].strip()
        if re.match(r"^#{1,6}\s+", first):
            if "诊断报告" in first and ("Sober" in first or "Queen" in first or "👑" in first):
                lines.pop(i)

    return "\n".join(lines).strip()


def get_secret(key: str) -> Optional[str]:
    try:
        value = st.secrets.get(key)
    except Exception:
        value = None
    return value


def require_secret(key: str) -> str:
    try:
        value = st.secrets[key]
    except Exception:
        raise RuntimeError(f"missing_secret:{key}")
    if value is None:
        raise RuntimeError(f"missing_secret:{key}")
    value_str = str(value).strip()
    if not value_str:
        raise RuntimeError(f"missing_secret:{key}")
    return value_str


def get_deepseek_api_key() -> Optional[str]:
    return require_secret("DEEPSEEK_API_KEY")


def build_client() -> OpenAI:
    api_key = get_deepseek_api_key()
    base_url = get_secret("DEEPSEEK_BASE_URL")

    return OpenAI(
        api_key=api_key,
        base_url=base_url or "https://api.deepseek.com/v1",
    )


def get_baidu_ocr_api_key() -> Optional[str]:
    return require_secret("BAIDU_OCR_API_KEY")


def get_baidu_ocr_secret_key() -> Optional[str]:
    return require_secret("BAIDU_OCR_SECRET_KEY")


def ensure_baidu_access_token(api_key: str, secret_key: str) -> str:
    now = time.time()
    token = st.session_state.get("baidu_access_token")
    expires_at = st.session_state.get("baidu_access_token_expires_at", 0.0)
    if token and expires_at and now < float(expires_at) - 60:
        return str(token)

    resp = requests.get(
        "https://aip.baidubce.com/oauth/2.0/token",
        params={
            "grant_type": "client_credentials",
            "client_id": api_key,
            "client_secret": secret_key,
        },
        timeout=20,
    )
    data = resp.json()
    if resp.status_code != 200:
        raise RuntimeError(f"baidu_token_http_{resp.status_code}")
    if "error" in data or "error_description" in data:
        raise RuntimeError(f"baidu_token_error:{data.get('error')}")

    access_token = data.get("access_token")
    if not access_token:
        raise RuntimeError("baidu_token_missing")

    expires_in = int(data.get("expires_in") or 0)
    st.session_state["baidu_access_token"] = access_token
    st.session_state["baidu_access_token_expires_at"] = now + (expires_in if expires_in > 0 else 3600)
    return str(access_token)


def baidu_general_ocr(image_bytes: bytes, api_key: str, secret_key: str) -> dict:
    access_token = ensure_baidu_access_token(api_key, secret_key)
    request_url = "https://aip.baidubce.com/rest/2.0/ocr/v1/general"
    resp = requests.post(
        f"{request_url}?access_token={access_token}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "image": base64.b64encode(image_bytes).decode("utf-8"),
            "language_type": "CHN_ENG",
            "detect_direction": "true",
            "recognize_granularity": "big",
        },
        timeout=30,
    )
    data = resp.json()
    if resp.status_code != 200:
        raise RuntimeError(f"baidu_ocr_http_{resp.status_code}")
    if data.get("error_code") is not None:
        code = data.get("error_code")
        msg = data.get("error_msg")
        raise RuntimeError(f"baidu_ocr_error:{code}:{msg}")

    return data


def is_timestamp_line(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if len(t) > 24:
        return False
    t = re.sub(r"\s+", " ", t)
    return TIMESTAMP_RE.match(t) is not None


def build_role_dialogue_from_ocr(ocr_json: dict, image_width: int) -> str:
    words_result = ocr_json.get("words_result") or []
    rows = []
    for item in words_result:
        text = (item.get("words") or "").strip()
        if not text:
            continue
        loc = item.get("location") or {}
        left = loc.get("left")
        top = loc.get("top")
        width = loc.get("width")
        height = loc.get("height")
        if left is None or width is None or top is None or height is None:
            continue
        rows.append((int(top), int(left), int(width), int(height), text))

    rows.sort(key=lambda x: (x[0], x[1]))

    dialogue_lines: list[str] = []
    last_speaker: Optional[str] = None
    last_bottom_y = 0
    last_line_height = 0

    for top, left, width, height, text in rows:
        if is_timestamp_line(text):
            last_speaker = None
            last_bottom_y = top + height
            last_line_height = height
            continue

        gap = top - last_bottom_y
        proximity_threshold = int(max(6, min(last_line_height, height) * 0.9)) if last_line_height else int(max(6, height * 0.9))

        if last_speaker is not None and gap >= 0 and gap < proximity_threshold:
            if dialogue_lines:
                dialogue_lines[-1] = f"{dialogue_lines[-1]} {text}".strip()
            else:
                dialogue_lines.append(f"【{last_speaker}】: {text}")
        else:
            # 坐标判定算法（V1.5）：
            # 1) 按 top 从上到下排序
            # 2) 计算 gap = current_top - last_bottom_y
            #    - gap 很小：视为同一气泡内换行，继承 last_speaker，并拼接到上一句
            #    - gap 很大：视为新气泡，才做 X 坐标中心点判定
            # 3) X 坐标判定：Center_X = left + (width / 2)
            #    - Center_X < ImageWidth/2 -> 【对方】
            #    - Center_X > ImageWidth/2 -> 【我】
            center_x = left + (width / 2.0)
            speaker = "对方" if center_x < (image_width / 2.0) else "我"
            last_speaker = speaker
            dialogue_lines.append(f"【{speaker}】: {text}")

        last_bottom_y = max(last_bottom_y, top + height)
        last_line_height = height

    return "\n".join(dialogue_lines).strip()


def analyze_chat(transcript: str, model: str) -> str:
    client = build_client()
    resp = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
    )
    content = (resp.choices[0].message.content or "").strip()
    if not content:
        raise RuntimeError("empty_response")
    return content


def main() -> None:
    st.set_page_config(
        page_title="Sober Queen",
        page_icon="👑",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    st.markdown(
        """
        <style>
          .stApp {
            background: #F5F5F7;
          }
          [data-testid="stHeader"] { background: transparent; }
          #MainMenu, footer { visibility: hidden; }

          html, body, [data-testid="stAppViewContainer"], .stApp {
            color: #1D1D1F;
          }
          .stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown span {
            color: #1D1D1F;
          }

          section.main div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #FFFFFF;
            border: none;
            border-radius: 16px;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.04);
            padding: 6px 2px;
          }

          section.main div[data-testid="stVerticalBlockBorderWrapper"] > div {
            border: none !important;
          }

          [data-testid="stFileUploader"] {
            background: transparent;
            border: none;
          }

          .stTextArea textarea {
            border-radius: 12px;
          }
          .stTextArea textarea, .stTextArea textarea::placeholder {
            color: #1D1D1F;
          }

          .stButton button {
            border-radius: 12px;
            font-weight: 700;
            border: none;
            background: #FF2D55;
            color: #FFFFFF;
            box-shadow: 0 6px 18px rgba(255, 45, 85, 0.18);
          }
          .stButton button:hover {
            background: #E11D48;
            color: #FFFFFF;
          }
          .stButton button:active {
            transform: translateY(0.5px);
          }

          [data-testid="stProgress"] {
            background: rgba(255, 45, 85, 0.12);
            border-radius: 999px;
          }
          [data-testid="stProgress"] > div > div > div {
            background: #FF2D55 !important;
          }

          [data-testid="stAlert"] {
            background: rgba(255, 45, 85, 0.08);
            border: 1px solid rgba(255, 45, 85, 0.18);
            border-radius: 14px;
          }

          .sq-report h1, .sq-report h2, .sq-report h3 {
            color: #1D1D1F;
            letter-spacing: 0.2px;
          }
          .sq-report p, .sq-report li {
            line-height: 1.7;
            letter-spacing: 0.15px;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("# 👑 Sober Queen")
    st.caption("一键粉碎无效沟通与情绪内耗")

    with st.container(border=True):
        uploads = st.file_uploader(
            "上传截图（可多选）",
            type=["png", "jpg", "jpeg"],
            accept_multiple_files=True,
        )

    if uploads:
        ordered = sorted(uploads, key=lambda f: (f.name or "").lower())
        current_sig = "|".join([f"{f.name}:{getattr(f, 'size', '')}" for f in ordered])
        last_sig = st.session_state.get("_last_upload_sig")
        if current_sig != last_sig:
            st.session_state["_last_upload_sig"] = current_sig

            try:
                baidu_api_key = get_baidu_ocr_api_key()
                baidu_secret_key = get_baidu_ocr_secret_key()
            except RuntimeError as e:
                if str(e).startswith("missing_secret:"):
                    st.error("未检测到百度 OCR 密钥：请在 Streamlit Secrets 配置 BAIDU_OCR_API_KEY / BAIDU_OCR_SECRET_KEY。")
                else:
                    st.error("读取百度 OCR 密钥失败：请检查 Secrets 配置。")
            else:
                progress = st.progress(0)
                status = st.empty()
                parts: list[str] = []
                total = len(ordered)

                with st.spinner("正在提取截图文字并分离角色..."):
                    for idx, f in enumerate(ordered, start=1):
                        status.info(f"正在提取第 {idx}/{total} 张截图文字...")
                        try:
                            ocr_json = baidu_general_ocr(
                                f.getvalue(),
                                api_key=baidu_api_key,
                                secret_key=baidu_secret_key,
                            )
                            img = Image.open(io.BytesIO(f.getvalue()))
                            image_width = int(img.size[0])
                            dialogue = build_role_dialogue_from_ocr(ocr_json, image_width=image_width)
                            if not dialogue:
                                dialogue = "（本图未识别到可用对话：可能是时间戳/系统提示或识别不到位置数据）"
                            parts.append(f"--- 图{idx}：{f.name} ---\n{dialogue}")
                        except Exception as e:
                            parts.append(f"--- 图{idx}：{f.name} ---\n（OCR 失败：{e}）")

                        progress.progress(int(idx / total * 100))

                status.empty()
                progress.empty()
                merged = "\n\n".join(parts).strip()
                if not merged:
                    st.warning("已读取截图，但未拼接出有效文字：建议更换更清晰的截图后重试。")
                else:
                    st.session_state.pop("report", None)
                    st.session_state["transcript"] = merged

    with st.container(border=True):
        transcript = st.text_area(
            "聊天记录",
            key="transcript",
            placeholder="请将让你内耗的聊天记录粘贴在这里...",
            height=500,
        )
        c1, c2 = st.columns([1, 1])
        with c1:
            run = st.button("开始诊断", type="primary", use_container_width=True)
        with c2:
            clear = st.button("清空本次内容", use_container_width=True)

        if clear:
            st.session_state.pop("report", None)
            st.session_state.pop("last_input", None)
            st.session_state.pop("transcript", None)
            st.session_state.pop("_last_upload_sig", None)
            st.session_state.pop("baidu_access_token", None)
            st.session_state.pop("baidu_access_token_expires_at", None)
            st.rerun()

    if run:
        text = (transcript or "").strip()
        if len(text) < 10:
            st.error("内容太短了：请粘贴更完整的聊天记录后再诊断。")
        else:
            with st.spinner("正在深度诊断..."):
                try:
                    report = analyze_chat(text, model="deepseek-chat")
                except RuntimeError as e:
                    if str(e).startswith("missing_secret:") or str(e) == "missing_api_key":
                        st.error("未检测到 DeepSeek 密钥：请在 Streamlit Secrets 配置 DEEPSEEK_API_KEY。")
                        report = None
                    elif str(e) == "empty_response":
                        st.error("模型返回了空内容，请重试一次。")
                        report = None
                    else:
                        st.error("发生未知错误，请稍后重试。")
                        report = None
                except Exception as e:
                    st.error(f"调用失败：{e}")
                    report = None

            if report:
                st.session_state["report"] = report
                st.session_state["last_input"] = text
                st.session_state["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if st.session_state.get("report"):
        with st.container(border=True):
            st.markdown("### 诊断报告")
            st.caption(f"生成时间：{st.session_state.get('generated_at','')}")
            st.markdown('<div class="sq-report">', unsafe_allow_html=True)
            st.markdown(sanitize_report_markdown(st.session_state["report"]))
            st.markdown("</div>", unsafe_allow_html=True)



if __name__ == "__main__":
    main()

