from __future__ import annotations

import json
import os
from dataclasses import dataclass
from io import BytesIO
from typing import Dict, List
from pathlib import Path

from flask import Flask, g, redirect, render_template, request, send_file, url_for
from fpdf import FPDF
from fpdf.enums import XPos, YPos

app = Flask(__name__)
app.config["SECRET_KEY"] = "replace-this-with-a-random-value"

BASE_DIR = Path(__file__).resolve().parent
PERSONA_CONTENT_PATH = BASE_DIR / "data" / "persona_content.json"
FONT_DIR = BASE_DIR / "fonts"
PDF_FONT_FAMILY = "NotoSansSC"
PDF_FONT_REGULAR_PATH = FONT_DIR / "NotoSansSC-Regular.ttf"
PDF_FONT_BOLD_PATH = FONT_DIR / "NotoSansSC-Bold.ttf"
try:
    PERSONA_CONTENT = json.loads(PERSONA_CONTENT_PATH.read_text(encoding="utf-8"))
except FileNotFoundError:
    PERSONA_CONTENT = {}
except json.JSONDecodeError:
    PERSONA_CONTENT = {}


@dataclass(frozen=True)
class Question:
    id: int
    dimension: str  # The letter that receives positive scoring before reverse handling
    prompt_cn: str
    prompt_en: str
    reverse: bool = False

    @property
    def field_name(self) -> str:
        return f"q{self.id}"


LANGUAGES: Dict[str, Dict[str, str]] = {
    "zh": {"label": "中文"},
    "en": {"label": "English"},
}
DEFAULT_LANGUAGE = "zh"

LETTER_TO_AXIS: Dict[str, str] = {
    "A": "AV",
    "V": "AV",
    "F": "FE",
    "E": "FE",
    "R": "RQ",
    "Q": "RQ",
    "P": "PC",
    "C": "PC",
}

LETTER_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "en": {
        "A": "A - Abstract",
        "V": "V - Visual",
        "F": "F - Familiar",
        "E": "E - Exploration",
        "R": "R - Rapid",
        "Q": "Q - Quality",
        "P": "P - Performance",
        "C": "C - Code Readability",
    },
    "zh": {
        "A": "A - 抽象",
        "V": "V - 视觉",
        "F": "F - 熟悉领域",
        "E": "E - 探索",
        "R": "R - 速成",
        "Q": "Q - 质量",
        "P": "P - 性能",
        "C": "C - 代码可读性",
    },
}

AXES: Dict[str, Dict[str, str]] = {
    "RQ": {
        "positive": "R",
        "negative": "Q",
        "title": "Rapid vs Quality",
    },
    "PC": {
        "positive": "P",
        "negative": "C",
        "title": "Performance vs Code Readability",
    },
    "FE": {
        "positive": "F",
        "negative": "E",
        "title": "Familiar vs Exploration",
    },
    "AV": {
        "positive": "A",
        "negative": "V",
        "title": "Abstract vs Visual",
    },
}

AXIS_SEQUENCE: List[str] = ["RQ", "PC", "FE", "AV"]

PERSONA_MAP: Dict[str, Dict[str, Dict[str, str]]] = {
    "RPFA": {"title": {"en": "Algorithm Engineer", "zh": "算法工程师"}},
    "QPFA": {"title": {"en": "Data Analyst", "zh": "数据分析师"}},
    "RPEA": {"title": {"en": "Algorithm Competitor", "zh": "算法竞赛人"}},
    "QPEA": {"title": {"en": "System Optimizer", "zh": "系统优化师"}},
    "RCFA": {"title": {"en": "Backend Engineer", "zh": "后端工程师"}},
    "QCFA": {"title": {"en": "Backend Architect", "zh": "后端架构师"}},
    "RCEA": {"title": {"en": "Data Miner", "zh": "数据挖掘师"}},
    "QCEA": {"title": {"en": "Backend Developer", "zh": "后端开发者"}},
    "RCFV": {"title": {"en": "Frontend CI/CD Specialist", "zh": "前端 CICD 专家"}},
    "QCFV": {"title": {"en": "Frontend Architect", "zh": "前端架构师"}},
    "RCEV": {"title": {"en": "Frontend Engineer", "zh": "前端工程师"}},
    "QCEV": {"title": {"en": "Framework Innovator", "zh": "前端框架开拓者"}},
    "RPFV": {"title": {"en": "Game Developer", "zh": "游戏开发者"}},
    "QPFV": {"title": {"en": "Game Optimizer", "zh": "游戏优化师"}},
    "RPEV": {"title": {"en": "Full-Stack Engineer", "zh": "全栈工程师"}},
    "QPEV": {"title": {"en": "Visualization Engineer", "zh": "可视化工程师"}},
}

COPY: Dict[str, Dict[str, Dict[str, str] | str]] = {
    "zh": {
        "site": {
            "tagline": "开发者画像测试",
            "footer": "© 2025 DevSpectrum —— 帮助团队洞察开发者画像。",
        },
        "quiz": {
            "page_title": "开发者画像测评",
            "hero_title": "开发者画像测评",
            "hero_tagline": "测一测，你是什么类型的程序员？",
            "hero_description": "28 道题聚焦于 4 个核心维度，使用 Likert 七级量表（-3 ~ +3）。完成后即可获得匹配的角色画像与建议。",
            "dimensions_title": "维度",
            "dimensions_desc": "A/V · F/E · R/Q · P/C",
            "duration_title": "时长",
            "duration_desc": "约 4-6 分钟",
            "scoring_title": "计分",
            "scoring_desc": "偶数题反向计分，自动平衡回答倾向",
            "positive_dimension": "正向维度",
            "reverse_scoring": "反向计分",
            "direct_scoring": "直接计分",
            "submit_button": "生成我的画像",
        },
        "result": {
            "profile_label": "你的画像",
            "no_persona": "暂未配置对应画像。",
            "lede": "四大坐标系得分。正值偏向第一个特质，负值偏向第二个特质。",
            "download_pdf": "下载 PDF",
            "axis_breakdown": "维度拆解",
            "answer_review": "答题回顾",
            "reverse_hint": "🔁 表示反向计分题目。",
            "start_over": "重新开始",
            "score_label": "得分",
            "favours_label": "倾向",
            "first_trait_label": "第一特质",
            "second_trait_label": "第二特质",
            "answer_label": "回答",
            "adjusted_label": "调整值",
            "contribution_label": "贡献",
            "image_alt": "画像插画",
        },
        "errors": {
            "missing_questions": "请先回答所有题目（缺少: {missing}）。",
            "incomplete_pdf": "无法导出 PDF，因为答案不完整。",
        },
        "pdf": {
            "title": "DevSpectrum 画像报告",
            "profile_code": "画像代码",
            "persona": "角色",
            "persona_sections": "画像洞察",
            "axis_breakdown": "维度拆解",
            "answer_summary": "答题汇总",
            "answer_line": "回答 {raw} · 调整值 {adjusted} · 权重 {weighted}",
        },
    },
    "en": {
        "site": {
            "tagline": "Developer Persona Test",
            "footer": "© 2025 DevSpectrum. Built for teams exploring developer personas.",
        },
        "quiz": {
            "page_title": "Developer Persona Assessment",
            "hero_title": "Developer Persona Assessment",
            "hero_tagline": "Find out what kind of developer you are.",
            "hero_description": "28 questions across four axes using a 7-point Likert scale (-3 ~ +3). Finish to reveal your persona code and insights.",
            "dimensions_title": "Axes",
            "dimensions_desc": "A/V · F/E · R/Q · P/C",
            "duration_title": "Duration",
            "duration_desc": "About 4–6 minutes",
            "scoring_title": "Scoring",
            "scoring_desc": "Even-numbered prompts are reverse scored to balance bias",
            "positive_dimension": "Positive Trait",
            "reverse_scoring": "Reverse scored",
            "direct_scoring": "Direct scored",
            "submit_button": "Generate My Profile",
        },
        "result": {
            "profile_label": "Your Profile",
            "no_persona": "No mapped persona for this combination yet.",
            "lede": "Scores across the four axes. Positive values lean toward the first trait, negative values favor the second.",
            "download_pdf": "Download PDF",
            "axis_breakdown": "Axis Breakdown",
            "answer_review": "Answer Review",
            "reverse_hint": "🔁 indicates a reverse-scored question.",
            "start_over": "Start Over",
            "score_label": "Score",
            "favours_label": "Favours",
            "first_trait_label": "First Trait",
            "second_trait_label": "Second Trait",
            "answer_label": "Answer",
            "adjusted_label": "Adjusted",
            "contribution_label": "Contribution",
            "image_alt": "Persona illustration",
        },
        "errors": {
            "missing_questions": "Please answer every question before submitting. Missing: {missing}",
            "incomplete_pdf": "Unable to export PDF because answers are incomplete.",
        },
        "pdf": {
            "title": "DevSpectrum Profile Report",
            "profile_code": "Profile Code",
            "persona": "Persona",
            "persona_sections": "Persona Insights",
            "axis_breakdown": "Axis Breakdown",
            "answer_summary": "Answer Summary",
            "answer_line": "Answer {raw} · Adjusted {adjusted} · Weighted {weighted}",
        },
    },
}
LIKERT_OPTIONS: List[Dict[str, object]] = [
    {"value": -3, "label": {"zh": "非常反对", "en": "Strongly Disagree"}},
    {"value": -2, "label": {"zh": "反对", "en": "Disagree"}},
    {"value": -1, "label": {"zh": "略反对", "en": "Slightly Disagree"}},
    {"value": 0, "label": {"zh": "中立", "en": "Neutral"}},
    {"value": 1, "label": {"zh": "略同意", "en": "Slightly Agree"}},
    {"value": 2, "label": {"zh": "同意", "en": "Agree"}},
    {"value": 3, "label": {"zh": "非常同意", "en": "Strongly Agree"}},
]

QUESTIONS: List[Question] = [
    # Abstract vs Visual
    Question(
        id=1,
        dimension="A",
        prompt_cn="我更喜欢通过文字或逻辑推理理解问题，而不是依赖图像或直觉。",
        prompt_en="I prefer understanding problems through words or logical reasoning rather than relying on images or intuition.",
    ),
    Question(
        id=2,
        dimension="A",
        prompt_cn="面对复杂问题时，我习惯先从公式或算法入手，而不是画草图或图表。",
        prompt_en="When facing complex problems, I usually start with formulas or algorithms rather than drawing sketches or diagrams.",
        reverse=True,
    ),
    Question(
        id=3,
        dimension="A",
        prompt_cn="在学习新技术时，我更注重概念和原理，而非界面或外观。",
        prompt_en="When learning new technologies, I focus more on concepts and principles than on interfaces or appearance.",
    ),
    Question(
        id=4,
        dimension="A",
        prompt_cn="我觉得自己擅长用抽象模型来解释现实问题。",
        prompt_en="I’m good at explaining real-world problems using abstract models.",
        reverse=True,
    ),
    Question(
        id=5,
        dimension="A",
        prompt_cn="我会被美观的界面吸引，但内心更关心底层逻辑是否合理。",
        prompt_en="I may be drawn to beautiful interfaces, but I care more about whether the underlying logic makes sense.",
    ),
    Question(
        id=6,
        dimension="A",
        prompt_cn="我更容易记住代码结构而不是界面布局。",
        prompt_en="I find it easier to remember the structure of code than the layout of interfaces.",
        reverse=True,
    ),
    Question(
        id=7,
        dimension="A",
        prompt_cn="我认为“好代码”应当像数学公式一样简洁优雅。",
        prompt_en='I believe good code should be as concise and elegant as a mathematical formula.',
    ),
    # Familiar vs Exploration
    Question(
        id=8,
        dimension="F",
        prompt_cn="我喜欢反复使用熟悉的工具，而不是频繁尝试新框架。",
        prompt_en="I prefer reusing familiar tools rather than frequently trying new frameworks.",
    ),
    Question(
        id=9,
        dimension="E",
        prompt_cn="我在面对未知领域时，会感到兴奋而非焦虑。",
        prompt_en="I feel excited, not anxious, when facing an unknown field.",
        reverse=True,
    ),
    Question(
        id=10,
        dimension="E",
        prompt_cn="我会主动寻找新的技术挑战，而不是在舒适区待太久。",
        prompt_en="I actively look for new technical challenges instead of staying in my comfort zone for too long.",
    ),
    Question(
        id=11,
        dimension="F",
        prompt_cn="我更喜欢在稳定的项目中持续改进，而非频繁换方向。",
        prompt_en="I prefer continuously improving a stable project rather than changing directions frequently.",
        reverse=True,
    ),
    Question(
        id=12,
        dimension="E",
        prompt_cn="学习一种新语言或新框架让我充满动力。",
        prompt_en="Learning a new language or framework gives me strong motivation.",
    ),
    Question(
        id=13,
        dimension="E",
        prompt_cn="我倾向于在掌握细节前先大体试试，而不是等完全了解再动手。",
        prompt_en="I tend to experiment before fully understanding the details, rather than waiting until I know everything.",
        reverse=True,
    ),
    Question(
        id=14,
        dimension="E",
        prompt_cn="对我来说，“玩一玩”新技术的乐趣比“精通”旧技术更重要。",
        prompt_en='For me, the fun of “playing around” with new technology matters more than mastering old ones.',
    ),
    # Rapid vs Quality
    Question(
        id=15,
        dimension="R",
        prompt_cn="我更重视快速完成任务，而不是把每个细节都打磨完美。",
        prompt_en="I value finishing tasks quickly rather than perfecting every detail.",
    ),
    Question(
        id=16,
        dimension="R",
        prompt_cn="我认为“先让它跑起来，再优化”是合理的做法。",
        prompt_en='I believe “get it running first, optimize later” is a reasonable approach.',
        reverse=True,
    ),
    Question(
        id=17,
        dimension="Q",
        prompt_cn="我会为追求性能或精度而延迟交付。",
        prompt_en="I’m willing to delay delivery to pursue better performance or precision.",
    ),
    Question(
        id=18,
        dimension="Q",
        prompt_cn="我宁愿慢一点，也要确保结果稳定可靠。",
        prompt_en="I’d rather take more time to ensure stability and reliability.",
        reverse=True,
    ),
    Question(
        id=19,
        dimension="R",
        prompt_cn="我写代码时更倾向于一次实现多个小功能，而不是完美实现一个大功能。",
        prompt_en="When coding, I tend to implement multiple small features rather than perfecting one big one.",
    ),
    Question(
        id=20,
        dimension="Q",
        prompt_cn="我认为代码的“鲁棒性”比“速度”更重要。",
        prompt_en='I believe code robustness is more important than execution speed.',
        reverse=True,
    ),
    Question(
        id=21,
        dimension="R",
        prompt_cn="如果时间紧迫，我会优先完成整体功能而不是完美调试每个细节。",
        prompt_en="When time is tight, I prioritize completing the overall functionality over perfect debugging.",
    ),
    # Performance vs Code Readability
    Question(
        id=22,
        dimension="P",
        prompt_cn="我喜欢优化每一行代码，哪怕别人看不懂也无所谓。",
        prompt_en="I like optimizing every line of code, even if others can’t easily understand it.",
    ),
    Question(
        id=23,
        dimension="P",
        prompt_cn="我认为高效的算法比易读的结构更重要。",
        prompt_en="I think an efficient algorithm is more important than a readable structure.",
        reverse=True,
    ),
    Question(
        id=24,
        dimension="C",
        prompt_cn="我写代码时，优先考虑别人能否看懂。",
        prompt_en="When I write code, I prioritize whether others can understand it.",
    ),
    Question(
        id=25,
        dimension="C",
        prompt_cn="我更愿意牺牲一点性能换取更清晰的逻辑。",
        prompt_en="I’d rather sacrifice a bit of performance for clearer logic.",
        reverse=True,
    ),
    Question(
        id=26,
        dimension="P",
        prompt_cn="我喜欢挑战性能极限，即使可维护性下降。",
        prompt_en="I enjoy pushing performance limits, even if it reduces maintainability.",
    ),
    Question(
        id=27,
        dimension="C",
        prompt_cn="我会为了团队协作选择规范清晰的写法，而不是最优解。",
        prompt_en="For teamwork, I prefer clean, standardized code over the most optimized solution.",
        reverse=True,
    ),
    Question(
        id=28,
        dimension="C",
        prompt_cn="我认为“代码是给人读的，不是给机器读的”这句话很有道理。",
        prompt_en='I believe the saying “Code is written for humans to read, not for machines to run” makes a lot of sense.',
    ),
]


def resolve_language(value: str | None) -> str:
    if not value:
        return DEFAULT_LANGUAGE
    normalized = value.lower()
    return normalized if normalized in LANGUAGES else DEFAULT_LANGUAGE


def get_copy(language: str) -> Dict[str, Dict[str, str] | str]:
    return COPY.get(language, COPY[DEFAULT_LANGUAGE])


def get_letter_descriptions(language: str) -> Dict[str, str]:
    return LETTER_DESCRIPTIONS.get(language, LETTER_DESCRIPTIONS[DEFAULT_LANGUAGE])


def get_persona_content(profile_code: str, language: str):
    persona_entry = PERSONA_CONTENT.get(profile_code)
    if not persona_entry:
        return None

    preferred = persona_entry.get(language)
    if preferred and (preferred.get("sections") or preferred.get("tagline")):
        return preferred

    fallback = persona_entry.get(DEFAULT_LANGUAGE)
    if fallback and (fallback.get("sections") or fallback.get("tagline")):
        return fallback
    return None


def build_language_switcher(language: str):
    links = []
    endpoint = request.endpoint
    view_args = request.view_args.copy() if request.view_args else {}
    keep_query = request.method == "GET" and bool(endpoint)
    for code, meta in LANGUAGES.items():
        if keep_query:
            query_args = request.args.to_dict()
            query_args["lang"] = code
            try:
                url = url_for(endpoint, **view_args, **query_args)
            except Exception:
                url = url_for("questionnaire", lang=code)
        else:
            url = url_for("questionnaire", lang=code)
        links.append({"code": code, "label": meta["label"], "url": url, "active": code == language})
    return links


@app.before_request
def set_language():
    g.language = resolve_language(request.values.get("lang"))


@app.context_processor
def inject_language():
    language = getattr(g, "language", DEFAULT_LANGUAGE)
    return {
        "language": language,
        "copy": get_copy(language),
        "language_switcher": build_language_switcher(language),
    }


def compute_scores(form_data: Dict[str, str]) -> Dict[str, object]:
    axis_scores = {axis_key: 0.0 for axis_key in AXES.keys()}
    responses: List[Dict[str, object]] = []

    for question in QUESTIONS:
        raw_value = int(form_data[question.field_name])
        adjusted_value = -raw_value if question.reverse else raw_value
        axis_key = LETTER_TO_AXIS[question.dimension]
        axis_info = AXES[axis_key]
        orientation = 1 if axis_info["positive"] == question.dimension else -1
        weighted_value = orientation * adjusted_value
        axis_scores[axis_key] += weighted_value

        responses.append(
            {
                "question": question,
                "raw": raw_value,
                "adjusted": adjusted_value,
                "axis": axis_key,
                "orientation": orientation,
                "weighted": weighted_value,
            }
        )

    return {"axis_scores": axis_scores, "responses": responses}


def build_profile_code(axis_scores: Dict[str, float], letter_descriptions: Dict[str, str]):
    breakdown = []
    code_letters: List[str] = []

    for axis_key in AXIS_SEQUENCE:
        info = AXES[axis_key]
        positive_letter = info["positive"]
        negative_letter = info["negative"]
        score = axis_scores.get(axis_key, 0.0)
        selected = positive_letter if score >= 0 else negative_letter
        breakdown.append(
            {
                "axis_key": axis_key,
                "title": info["title"],
                "score": score,
                "selected": selected,
                "magnitude": abs(score),
                "positive_label": letter_descriptions.get(positive_letter, positive_letter),
                "negative_label": letter_descriptions.get(negative_letter, negative_letter),
                "selected_label": letter_descriptions.get(selected, selected),
            }
        )
        code_letters.append(selected)

    return "".join(code_letters), breakdown


def sanitize_for_pdf(text: str) -> str:
    replacements = {
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "…": "...",
        "💡": "[Idea] ",
        "🏢": "[Industry] ",
        "🌍": "[Trend] ",
        "⚙️": "[Challenge] ",
        "🚀": "[Opportunity] ",
        "📈": "[Growth] ",
        "🌱": "[Development] ",
        "✅": "[Tagline] ",
        "🧮": "[Analytics] ",
        "🏗️": "[Backend] ",
        "💻": "[Frontend] ",
        "🎮": "[Game] ",
        "🖥️": "[Tech] ",
        "🧭": "[Architect] ",
        "🧑‍💻": "[Engineer] ",
        "🧪": "[Innovation] ",
        "⛏️": "[Miner] ",
        "🎯": "[Target] ",
        "📊": "[Data] ",
        "🚦": "[Ops] ",
        "🧠": "[Mindset] ",
        "🤖": "[AI] ",
        "🔁": "[Reverse] ",
        "🌐": "[Global] ",
        "🔧": "[Tool] ",
        "📌": "[Point] ",
        "🔗": "[Link] ",
        "️": "",
        "⃣": "",
        "™": "TM",
    }
    for src, dest in replacements.items():
        text = text.replace(src, dest)
    return text


def generate_pdf_report(
    profile_code: str,
    persona_title: str | None,
    breakdown,
    responses,
    language: str,
    persona_sections=None,
    persona_tagline: str | None = None,
    persona_tagline_heading: str | None = None,
) -> BytesIO:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    base_text_color = (32, 37, 45)
    accent_color = (79, 89, 231)
    muted_color = (110, 116, 132)

    regular_family = "Helvetica"
    regular_style = ""
    bold_family = "Helvetica"
    bold_style = "B"
    try:
        if PDF_FONT_REGULAR_PATH.exists():
            pdf.add_font(PDF_FONT_FAMILY, "", str(PDF_FONT_REGULAR_PATH), uni=True)
            regular_family = PDF_FONT_FAMILY
            bold_family = PDF_FONT_FAMILY
            regular_style = ""
            bold_style = ""
        if PDF_FONT_BOLD_PATH.exists():
            pdf.add_font(PDF_FONT_FAMILY, "B", str(PDF_FONT_BOLD_PATH), uni=True)
            bold_style = "B"
    except RuntimeError:
        regular_family = "Helvetica"
        regular_style = ""
        bold_family = "Helvetica"
        bold_style = "B"

    pdf_text = get_copy(language)["pdf"]  # type: ignore[assignment]
    pdf.set_title(pdf_text["title"])  # type: ignore[index]
    pdf.set_author("DevSpectrum")

    pdf.set_text_color(*base_text_color)

    pdf.set_font(bold_family, bold_style, 16)
    pdf.cell(0, 10, sanitize_for_pdf(pdf_text["title"]))  # type: ignore[index]
    pdf.ln(8)

    pdf.set_font(regular_family, regular_style, 12)
    pdf.cell(0, 8, sanitize_for_pdf(f"{pdf_text['profile_code']}: {profile_code}"))  # type: ignore[index]
    pdf.ln(6)
    if persona_title:
        pdf.cell(0, 8, sanitize_for_pdf(f"{pdf_text['persona']}: {persona_title}"))  # type: ignore[index]
        pdf.ln(6)

    if persona_tagline:
        pdf.set_font(bold_family, bold_style, 11)
        pdf.set_text_color(242, 77, 98)
        tagline_label = ""
        if persona_tagline_heading:
            tagline_label = sanitize_for_pdf(persona_tagline_heading) + " "
        pdf.multi_cell(0, 6, sanitize_for_pdf(f"{tagline_label}{persona_tagline}"), align="L")
        pdf.set_text_color(*base_text_color)
        pdf.ln(4)

    if persona_sections:
        pdf.set_font(bold_family, bold_style, 13)
        section_title = pdf_text.get("persona_sections") or pdf_text.get("persona")  # type: ignore[index]
        pdf.set_fill_color(244, 245, 251)
        pdf.cell(
            0,
            10,
            sanitize_for_pdf(section_title),
            fill=True,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.ln(2)
        for section in persona_sections:
            heading = sanitize_for_pdf(section.get("heading", ""))
            if heading:
                pdf.set_font(bold_family, bold_style, 12)
                pdf.set_fill_color(235, 237, 252)
                pdf.cell(
                    0,
                    8,
                    heading,
                    fill=True,
                    new_x=XPos.LMARGIN,
                    new_y=YPos.NEXT,
                )
                pdf.ln(2)
            pdf.set_font(regular_family, regular_style, 11)
            for paragraph in section.get("paragraphs", []):
                sanitized = sanitize_for_pdf(paragraph)
                bullet = False
                for prefix in ("- ", "• ", "•\u00a0"):
                    if sanitized.startswith(prefix):
                        sanitized = sanitized[len(prefix) :].lstrip()
                        bullet = True
                        break
                if bullet:
                    x = pdf.get_x()
                    pdf.cell(4, 6, "•", align="L")
                    pdf.set_x(x + 6)
                    pdf.multi_cell(0, 6, sanitized, align="L")
                else:
                    pdf.multi_cell(0, 6, sanitized, align="L")
                pdf.ln(1)
            pdf.ln(4)

    pdf.ln(4)
    pdf.set_font(bold_family, bold_style, 14)
    pdf.cell(0, 8, sanitize_for_pdf(pdf_text["axis_breakdown"]))  # type: ignore[index]
    pdf.ln(6)

    pdf.set_font(regular_family, regular_style, 12)
    for axis in breakdown:
        axis_text = sanitize_for_pdf(
            f"{axis['title']}: {axis['score']:.1f} (favours {axis['selected_label']})"
        )
        pdf.multi_cell(0, 6, axis_text, align="L")
        pdf.ln(1)

    pdf.ln(3)
    pdf.set_font(bold_family, bold_style, 14)
    pdf.cell(0, 8, sanitize_for_pdf(pdf_text["answer_summary"]))  # type: ignore[index]
    pdf.ln(6)

    pdf.set_font(regular_family, regular_style, 11)
    for item in responses:
        question = item["question"]
        prompt = question.prompt_cn if language == "zh" else question.prompt_en
        pdf.multi_cell(0, 6, sanitize_for_pdf(f"Q{question.id}: {prompt}"), align="L")
        answer_line = sanitize_for_pdf(
            pdf_text["answer_line"].format(  # type: ignore[index]
                raw=item["raw"],
                adjusted=item["adjusted"],
                weighted=f"{item['weighted']:.1f}",
            )
        )
        pdf.cell(0, 5, answer_line)
        pdf.ln(6)

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer


@app.route("/", methods=["GET", "POST"])
def questionnaire():
    language = getattr(g, "language", DEFAULT_LANGUAGE)
    letter_descriptions = get_letter_descriptions(language)

    if request.method == "POST":
        missing = [
            question.id
            for question in QUESTIONS
            if question.field_name not in request.form
        ]
        if missing:
            error_message = get_copy(language)["errors"]["missing_questions"].format(  # type: ignore[index]
                missing=", ".join(str(q_id) for q_id in missing)
            )
            return render_template(
                "quiz.html",
                questions=QUESTIONS,
                options=LIKERT_OPTIONS,
                error=error_message,
                submitted={field: request.form.get(field) for field in request.form},
                letter_descriptions=letter_descriptions,
            )

        answer_fields = {
            field: request.form[field] for field in request.form if field.startswith("q")
        }
        query_params = {"lang": language}
        query_params.update(answer_fields)
        return redirect(url_for("results", **query_params))

    return render_template(
        "quiz.html",
        questions=QUESTIONS,
        options=LIKERT_OPTIONS,
        error=None,
        submitted={},
        letter_descriptions=letter_descriptions,
    )


@app.get("/results")
def results():
    language = getattr(g, "language", DEFAULT_LANGUAGE)
    letter_descriptions = get_letter_descriptions(language)

    answer_fields: Dict[str, str] = {}
    for question in QUESTIONS:
        value = request.args.get(question.field_name)
        if value is None:
            return redirect(url_for("questionnaire", lang=language))
        answer_fields[question.field_name] = value

    score_data = compute_scores(answer_fields)
    profile_code, breakdown = build_profile_code(score_data["axis_scores"], letter_descriptions)

    persona_meta = PERSONA_MAP.get(profile_code)
    persona_title = None
    if persona_meta:
        persona_title = persona_meta["title"].get(language) or persona_meta["title"].get(DEFAULT_LANGUAGE)

    persona_content = get_persona_content(profile_code, language)
    persona_sections = persona_content["sections"] if persona_content else []
    persona_tagline = persona_content.get("tagline") if persona_content else None
    persona_tagline_heading = persona_content.get("tagline_heading") if persona_content else None

    image_path = f"static/images/personas/{profile_code}.png"
    image_url = image_path if os.path.exists(image_path) else None

    return render_template(
        "result.html",
        profile_code=profile_code,
        persona_title=persona_title,
        breakdown=breakdown,
        axis_scores=score_data["axis_scores"],
        responses=score_data["responses"],
        letter_descriptions=letter_descriptions,
        image_url=image_url,
        persona_sections=persona_sections,
        persona_tagline=persona_tagline,
        persona_tagline_heading=persona_tagline_heading,
    )


@app.post("/export/pdf")
def export_pdf():
    form_values = request.form.to_dict()
    language = resolve_language(form_values.get("lang"))
    answer_fields = {
        field: value for field, value in form_values.items() if field.startswith("q")
    }

    if len(answer_fields) != len(QUESTIONS):
        error_text = get_copy(language)["errors"]["incomplete_pdf"]  # type: ignore[index]
        return (error_text, 400)

    score_data = compute_scores(answer_fields)
    letter_descriptions = get_letter_descriptions(language)
    profile_code, breakdown = build_profile_code(score_data["axis_scores"], letter_descriptions)
    persona_meta = PERSONA_MAP.get(profile_code)
    persona_title = None
    if persona_meta:
        persona_title = persona_meta["title"].get(language) or persona_meta["title"].get(DEFAULT_LANGUAGE)

    persona_content = get_persona_content(profile_code, language)
    persona_sections = persona_content["sections"] if persona_content else []
    persona_tagline = persona_content.get("tagline") if persona_content else None
    persona_tagline_heading = persona_content.get("tagline_heading") if persona_content else None

    pdf_buffer = generate_pdf_report(
        profile_code=profile_code,
        persona_title=persona_title,
        breakdown=breakdown,
        responses=score_data["responses"],
        language=language,
        persona_sections=persona_sections,
        persona_tagline=persona_tagline,
        persona_tagline_heading=persona_tagline_heading,
    )
    pdf_buffer.seek(0)

    filename = f"DevSpectrum_{profile_code}.pdf"
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True, port=5001)
