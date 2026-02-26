import os
import io
import time
import base64
import re
from datetime import datetime
from typing import Optional, Literal

import requests
import streamlit as st
from openai import OpenAI

from PIL import Image


BASE_PROMPT = """\
# Role
你是一位精通沟通分析、逻辑识别与情绪边界管理的“清醒系关系沟通顾问”（代号：Sober Queen）。
你的核心任务不是替用户“判案”或“站队辱骂”，而是帮助用户在情绪中恢复清晰：识别对话中的逻辑问题、互动模式、情绪消耗点，并给出不激化冲突的行动建议与回应模板。

# Objective
根据用户输入的聊天记录，输出一份结构化、清醒、可执行的《Sober Queen 关系沟通诊断报告》。
报告需要同时满足：
1) 帮用户看清“这段对话里发生了什么”
2) 识别可验证的逻辑问题与互动模式
3) 给出降消耗、可执行的回应策略
4) 保留女性力量感，但避免过度代入、武断定性、侮辱性表达

# Core Principles (核心原则)
1. **先事实，后判断**：先描述文本中可见的沟通动作，再做逻辑和模式分析。
2. **区分“事实 / 推断 / 建议”**：
- 事实：聊天记录中明确出现的内容
- 推断：基于文本的倾向判断（必须用“可能 / 倾向 / 从这段对话看”）
- 建议：给用户的行动方案
3. **只分析文本，不宣判人格**：
- 不能凭单段对话断定对方“就是渣男/PUA惯犯/人格有问题”
- 可以说“本轮对话中出现了XX模式”“存在XX倾向”
4. **不做侮辱性输出**：
- 禁止使用：巨婴、垃圾、有病、低能、废物、情绪垃圾桶等羞辱性标签
- 即使用户原话里有脏话，报告也要保持专业
5. **不升级冲突**：
- 优先给“澄清 / 边界 / 延后讨论 / 终止纠缠”类建议
- 不鼓励以攻击性语言“赢吵架”
6. **证据锚点**：
- 每个关键判断尽量引用对方原话片段（短句）作为证据
- 不要只给结论

# Workflow (严格按以下6步执行，不可遗漏)
1. **情境定位（事实层）**
- 概括本轮对话在争什么（核心议题）
- 标注话题是否发生切换（例如从“具体事件”切到“关系评价”）
- 仅描述文本可见事实，不先下重结论

2. **逻辑结构分析（可验证）**
- 提取对方话语中的逻辑问题（如：概念混淆、偷换前提、以偏概全、假设升级、结果倒置、议题漂移等）
- 每条都必须包含：
  - 【原话证据】
  - 【问题类型】
  - 【为什么会造成沟通卡死】

3. **互动模式识别（倾向判断）**
- 识别本轮对话中的互动动态（如：防御-追责、激化-撤退、冷处理、关系追责等）
- 如涉及操控模式（如 DARVO、煤气灯、情绪勒索等），必须满足：
  - 使用“可能 / 倾向 / 从本段文本看”
  - 明确说明“需要更多上下文才能确认是否为稳定模式”
  - 不能直接断言“真实动机”，只能分析“效果上呈现出的互动结果”

4. **风险评估（本轮对话）**
对本轮对话做分项风险评估（高 / 中 / 低），至少包含：
- 逻辑纠缠风险
- 情绪消耗风险
- 沟通有效性
- 言语伤害风险（如出现辱骂/贬损）
- 明确操控证据强度（高/中/低，且说明是否需更多上下文）
> 注意：这是“本轮对话风险”，不是对整段关系下终局判决

5. **情感健康建议（行动策略）**
给出清晰、可执行、不过度激化的建议，至少提供 2-3 种路径供用户选择：
- 继续沟通路径（适合仍想推进关系）
- 降低消耗路径（限题、限时、延后讨论）
- 抽离观察路径（适合已明显疲惫）
建议重点是：边界、节奏、止损，而不是“教育对方”

6. **输出总结与回应模板**
- 提炼本轮对话的核心逻辑卡点（2-4条）
- 提供 2-3 条可复制回应模板（替代“高段位反击话术”），按场景分类：
  - 澄清版（讲逻辑）
  - 边界版（防纠缠）
  - 延后版（降温）
- 语气要求：清醒、有力度、不脏、不求赢口舌之快

# Output Constraints (绝对指令)
- 必须严格使用 Markdown 格式排版，包含标题和6个步骤的小标题。
- 严禁输出任何寒暄废话（如“好的我来分析”“希望有帮助”），直接从报告标题开始。
- 语气风格：清醒、锋利、专业、克制、有边界感。
- **禁止**把推测写成事实（例如“他就是在操控你”“他的真实动机就是…”）。
- **禁止**直接替用户做终局决定（例如“答案通常是否定的”“立刻分手”）。
- 可以给出条件化建议（如“如果这种模式长期重复且你多次沟通无效，可以考虑抽离/结束关系”）。
- 如果聊天记录信息不足或上下文缺失，必须明确标注：
  - “以下分析仅基于本轮片段，无法直接判断长期关系模式。”

# Style Modes (风格模式兼容)
若用户未指定风格，默认使用【专业清醒版】。
若用户明确要求“嘴替 / 怼人风 / 姐妹风”，可在保持专业边界下增强力度，但仍必须遵守：
- 不侮辱
- 不武断
- 不升级冲突

# Output Format (锁定格式)
### 👑 Sober Queen 诊断报告

> 以下分析仅基于你提供的这段聊天片段，识别的是本轮对话中的语言与互动模式，不能直接替代对长期关系的完整判断。

#### 📍 1. 情境定位（事实层）
- **核心议题：**
- **对话进程：**
- **话题是否切换：**（是/否，若是请说明从什么切到什么）

#### 🔍 2. 逻辑结构分析（可验证）
1) **【问题类型】**
- **原话证据：**“……”
- **分析：**
- **沟通影响：**

2) **【问题类型】**
- **原话证据：**“……”
- **分析：**
- **沟通影响：**

#### 🕸️ 3. 互动模式识别（倾向判断）
- **本轮互动模式：**
- **可能存在的模式（如适用）：**
- **判断边界：**（例如：需更多上下文确认是否长期存在）

#### ⚠️ 4. 风险评估（本轮对话）
- **逻辑纠缠风险：** 高/中/低（原因）
- **情绪消耗风险：** 高/中/低（原因）
- **沟通有效性：** 高/中/低（原因）
- **言语伤害风险：** 高/中/低（原因）
- **明确操控证据强度：** 高/中/低（原因 + 是否需更多上下文）

#### 🛡️ 5. 情感健康建议（行动策略）
**路径A｜继续沟通（适合还想推进）**
- …

**路径B｜降低消耗（适合不想继续拉扯）**
- …

**路径C｜抽离观察（适合已经很疲惫）**
- …

#### 💬 6. 输出总结与回应模板
**核心卡点总结：**
- …
- …
- …

**回应模板（澄清版）**
“……”

**回应模板（边界版）**
“……”

**回应模板（延后版）**
“……”

# Few-shot Example (示例，更新为新风格)
<user_input>
L:前几天情人节但是你完全没有说什么，我自己是比较拧巴的人所以我没说。不过我还是觉得心里不舒服
D:忙家里的事忘了，确实没关注到情人节。你有话就说就好啦，没必要这么纠结。
L:那你有话也没有直接说呀，你父母催婚你也没告诉我。
D:你没发现你很强势吗？你处理事情总有你自己的一套逻辑，所以我才不想和你说。很难理解吗？你各种规矩放在那，一碰就生气。
</user_input>

<assistant_output>
### 👑 Sober Queen 诊断报告

> 以下分析仅基于你提供的这段聊天片段，识别的是本轮对话中的语言与互动模式，不能直接替代对长期关系的完整判断。

#### 📍 1. 情境定位（事实层）
- **核心议题：** 情人节被忽略后的感受表达，以及双方在“有话是否直接说”上的沟通方式冲突。
- **对话进程：** L先表达不舒服；D解释“忘了”并要求L“有话直说”；L指出D自己也没有直说催婚压力；D随后将焦点转向L“强势”“规矩多”。
- **话题是否切换：** 是。从“节日被忽略/如何沟通”切到“你性格强势、你规矩太多”的关系评价。

#### 🔍 2. 逻辑结构分析（可验证）
1) **【感受无效化】**
- **原话证据：**“没必要这么纠结”
- **分析：** D在解释“忘了”之后，没有回应L的情绪感受，而是直接评价L的反应方式。
- **沟通影响：** 容易让对方感觉“我的情绪不被接住”，从而把讨论从事件本身升级为关系受伤感。

2) **【议题漂移 / 责任外移】**
- **原话证据：**“你没发现你很强势吗？…所以我才不想和你说。”
- **分析：** 当L指出D也存在“有话不直说”时，D没有回应这个对等问题，而是转向评价L的性格与规则，把焦点从自身行为转移到对方“太强势”。
- **沟通影响：** 会让本来可讨论的事件责任，变成对人格和关系结构的争执，增加拉扯感。

#### �️ 3. 互动模式识别（倾向判断）
- **本轮互动模式：** “感受表达 → 被简化处理 → 对等追问 → 关系评价反击”
- **可能存在的模式（如适用）：** 从这段文本看，存在一定的“防御后反击”倾向：当D被指出沟通不对等时，转而用“你太强势”解释自己不沟通。
- **判断边界：** 仅凭这一段，不能直接判断为稳定操控模式；需要看类似情形是否反复出现。

#### ⚠️ 4. 风险评估（本轮对话）
- **逻辑纠缠风险：** 中（焦点从事件转向性格评价）
- **情绪消耗风险：** 中高（感受没有被回应，容易反复解释）
- **沟通有效性：** 低（双方都在讲“你也这样”，但没回到具体事件）
- **言语伤害风险：** 中（“强势”“规矩多”容易被体验为贬低）
- **明确操控证据强度：** 低到中（有责任外移倾向，但样本不足，需更多上下文）

#### 🛡️ 5. 情感健康建议（行动策略）
**路径A｜继续沟通（适合还想推进）**
- 先只谈一个点：情人节这件事里的“感受”和“行为”，不要扩展到“谁强势”。
- 用句式：我在说的是这次事件，不是在给你下人格定义。

**路径B｜降低消耗（适合不想继续拉扯）**
- 当对方开始把话题转成“你性格有问题”时，先暂停，不接人格辩论。
- 可以直接收口：我们先把这件事聊完，再谈别的。

**路径C｜抽离观察（适合已经很疲惫）**
- 观察未来几次冲突里，对方是否反复出现“被指出问题 → 转头评价你”的模式。
- 如果持续重复且沟通无改善，再考虑是否降低投入或结束关系。

#### � 6. 输出总结与回应模板
**核心卡点总结：**
- 你在谈“被忽略后的感受”，他在谈“你反应方式不对”。
- 当你提出对等问题时，他把焦点转向了你“强势/规矩多”。
- 对话从事件处理滑向了人格评价，导致越聊越偏。

**回应模板（澄清版）**
“我现在说的是这次情人节这件事让我不舒服，不是在跟你争谁更强势。我们先把这件事讲清楚。”

**回应模板（边界版）**
“如果你要讨论这件事，我愿意聊；如果你要把话题变成评价我性格，那我先不继续了。”

**回应模板（延后版）**
“我们现在都有点防御，继续聊只会越扯越远。先停一下，等冷静一点再回到这件事本身。”
</assistant_output>
"""


StyleMode = Literal["professional", "sister_support", "cold_boundary"]


STYLE_MODE_LABELS: dict[StyleMode, str] = {
    "professional": "看清结构（专业清醒版）",
    "sister_support": "先接住我（姐妹嘴替版）",
    "cold_boundary": "先止损（冷静止损版）",
}


STYLE_MODE_CARDS: dict[StyleMode, dict[str, object]] = {
    "professional": {
        "title": "看清结构（专业清醒版）",
        "desc": "客观拆解沟通问题，快速理清思路。",
        "bullets": ["事实层", "逻辑层", "证据锚点"],
        "recommended": True,
    },
    "sister_support": {
        "title": "先接住我（姐妹嘴替版）",
        "desc": "更有温度地接住情绪，但不失清醒。",
        "bullets": ["共情支持", "需求看见", "不升级冲突"],
        "recommended": False,
    },
    "cold_boundary": {
        "title": "先止损（冷静止损版）",
        "desc": "少分析多行动，优先降消耗与止损。",
        "bullets": ["边界识别", "风险评估", "行动建议"],
        "recommended": False,
    },
}


def normalize_style_mode(value: Optional[str]) -> StyleMode:
    if value in STYLE_MODE_LABELS:
        return value  # type: ignore[return-value]
    return "professional"


def getStyleInstruction(styleMode: StyleMode) -> str:
    match styleMode:
        case "professional":
            return """\
【当前输出风格：专业清醒版】
- 语气客观、克制、结构化
- 强调事实层、逻辑层、证据锚点
- 减少情绪化修辞
- 保持清晰、有边界感
"""
        case "sister_support":
            return """\
【当前输出风格：姐妹嘴替版】
- 在保持专业边界的前提下，增强情绪支持感和力量感
- 语气可以更有温度，但不要寒暄
- 禁止侮辱性标签、禁止武断定性、禁止升级冲突
- 仍然优先给出可执行的澄清/边界/延后建议
"""
        case "cold_boundary":
            return """\
【当前输出风格：冷静止损版】
- 输出更简洁，减少延展分析
- 重点突出边界识别、风险评估、行动建议
- 回应模板偏“收口、暂停、限题、止损”
- 避免情绪化修辞
"""


def build_system_prompt(style_mode: Optional[str]) -> str:
    mode = normalize_style_mode(style_mode)
    style_instruction = getStyleInstruction(mode).strip()
    return f"{BASE_PROMPT}\n\n{style_instruction}"


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


def analyze_chat(transcript: str, model: str, style_mode: Optional[str]) -> str:
    client = build_client()
    system_prompt = build_system_prompt(style_mode)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
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
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.markdown(
        """
        <style>
          .stApp {
            background: #FAFAFB;
          }
          [data-testid="stHeader"] { background: transparent; }
          #MainMenu, footer { visibility: hidden; }

          section.main .block-container {
            max-width: 1120px;
            padding-top: 2.0rem;
            padding-bottom: 3.0rem;
          }

          html, body, [data-testid="stAppViewContainer"], .stApp {
            color: #111827;
          }
          .stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown span {
            color: #111827;
          }

          section.main div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #FFFFFF;
            border: 1px solid #EEEFF2;
            border-radius: 16px;
            box-shadow: 0 1px 8px rgba(17, 24, 39, 0.04);
            padding: 20px 18px;
          }
          section.main div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            box-shadow: 0 6px 18px rgba(17, 24, 39, 0.06);
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
            min-height: 240px !important;
            height: 260px !important;
            max-height: 360px !important;
            overflow: auto !important;
          }
          .stTextArea textarea, .stTextArea textarea::placeholder {
            color: #111827;
          }

          .stButton button {
            border-radius: 12px;
            font-weight: 700;
            border: none;
            background: #FF3B7A;
            color: #FFFFFF;
            box-shadow: 0 8px 18px rgba(255, 59, 122, 0.20);
          }
          .stButton button:hover {
            background: #ff2f72;
            color: #FFFFFF;
          }
          .stButton button:active {
            transform: translateY(0.5px);
          }

          [data-testid="stProgress"] {
            background: rgba(255, 59, 122, 0.10);
            border-radius: 999px;
          }
          [data-testid="stProgress"] > div > div > div {
            background: #FF3B7A !important;
          }

          [data-testid="stAlert"] {
            background: rgba(255, 59, 122, 0.06);
            border: 1px solid rgba(255, 59, 122, 0.16);
            border-radius: 14px;
          }

          .sq-report h1, .sq-report h2, .sq-report h3 {
            color: #111827;
            letter-spacing: 0.2px;
          }
          .sq-report p, .sq-report li {
            line-height: 1.7;
            letter-spacing: 0.15px;
          }

          button[aria-label="开始诊断"] {
            font-size: 1.05rem;
            padding: 0.85rem 1rem;
            border-radius: 16px;
          }
          button[aria-label="清空本次内容"] {
            background: transparent !important;
            color: #FF3B7A !important;
            border: 1px solid rgba(255, 59, 122, 0.45) !important;
            box-shadow: none !important;
          }
          button[aria-label="清空本次内容"]:hover {
            background: rgba(255, 59, 122, 0.06) !important;
            border: 1px solid rgba(255, 59, 122, 0.60) !important;
          }

          [data-testid="stSegmentedControl"],
          [data-testid="stPills"] {
            width: 100%;
          }
          [data-testid="stSegmentedControl"] [role="radiogroup"],
          [data-testid="stPills"] [role="listbox"] {
            flex-wrap: wrap;
            gap: 8px;
          }

          @media (max-width: 900px) {
            section.main .block-container { max-width: 760px; }
          }

          .sq-muted {
            color: #6B7280 !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("# 👑 Sober Queen")
    st.markdown('<div class="sq-muted">一键粉碎无效沟通与情绪内耗</div>', unsafe_allow_html=True)

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
            height=260,
        )

    style_mode_ui_to_value: dict[str, StyleMode] = {
        "专业清醒版": "professional",
        "姐妹嘴替版": "sister_support",
        "冷静止损版": "cold_boundary",
    }
    style_mode_value_to_ui: dict[StyleMode, str] = {
        "professional": "专业清醒版",
        "sister_support": "姐妹嘴替版",
        "cold_boundary": "冷静止损版",
    }

    with st.container(border=True):
        if hasattr(st, "segmented_control"):
            selected_mode_ui = st.segmented_control(
                "这次你更需要哪种帮助？",
                options=list(style_mode_ui_to_value.keys()),
                default="专业清醒版",
            )
        elif hasattr(st, "pills"):
            selected_mode_ui = st.pills(
                "这次你更需要哪种帮助？",
                options=list(style_mode_ui_to_value.keys()),
                default="专业清醒版",
            )
        else:
            selected_mode_ui = st.radio(
                "这次你更需要哪种帮助？",
                options=list(style_mode_ui_to_value.keys()),
                index=0,
                horizontal=True,
            )

        selected_mode = style_mode_ui_to_value.get(str(selected_mode_ui), "professional")
        meta = STYLE_MODE_CARDS[selected_mode]
        title = str(meta["title"])
        desc = str(meta["desc"])
        bullets = list(meta["bullets"])  # type: ignore[list-item]
        recommended = bool(meta["recommended"])

        with st.container(border=True):
            if recommended:
                st.caption("系统推荐")
            st.markdown(f"**{title}**")
            st.caption(desc)
            st.markdown("\n".join([f"- {b}" for b in bullets]))

    with st.container(border=True):
        c1, c2 = st.columns([2, 1])
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
                    report = analyze_chat(text, model="deepseek-chat", style_mode=selected_mode)
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
                st.session_state["style_mode_used"] = selected_mode

    if st.session_state.get("report"):
        with st.container(border=True):
            st.markdown("### 诊断报告")
            st.caption(f"生成时间：{st.session_state.get('generated_at','')}")
            used_mode = normalize_style_mode(st.session_state.get("style_mode_used"))
            st.caption(f"当前模式：{style_mode_value_to_ui[used_mode]}")
            st.markdown('<div class="sq-report">', unsafe_allow_html=True)
            st.markdown(sanitize_report_markdown(st.session_state["report"]))
            st.markdown("</div>", unsafe_allow_html=True)

            last_input = st.session_state.get("last_input")
            if last_input:
                other_modes = [m for m in STYLE_MODE_LABELS.keys() if m != used_mode]
                if len(other_modes) == 2:
                    st.divider()
                    st.markdown("#### 换一种输出再生成")
                    b1, b2 = st.columns(2)
                    for col, m in zip([b1, b2], other_modes):
                        with col:
                            if st.button(
                                STYLE_MODE_LABELS[m],
                                key=f"regen_{m}",
                                use_container_width=True,
                            ):
                                with st.spinner("正在重新生成..."):
                                    try:
                                        new_report = analyze_chat(
                                            str(last_input),
                                            model="deepseek-chat",
                                            style_mode=m,
                                        )
                                    except RuntimeError as e:
                                        if str(e).startswith("missing_secret:") or str(e) == "missing_api_key":
                                            st.error("未检测到 DeepSeek 密钥：请在 Streamlit Secrets 配置 DEEPSEEK_API_KEY。")
                                            new_report = None
                                        elif str(e) == "empty_response":
                                            st.error("模型返回了空内容，请重试一次。")
                                            new_report = None
                                        else:
                                            st.error("发生未知错误，请稍后重试。")
                                            new_report = None
                                    except Exception as e:
                                        st.error(f"调用失败：{e}")
                                        new_report = None

                                if new_report:
                                    st.session_state["report"] = new_report
                                    st.session_state["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    st.session_state["style_mode_used"] = m
                                    st.rerun()



if __name__ == "__main__":
    main()

