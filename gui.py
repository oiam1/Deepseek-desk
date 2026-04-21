import json
from html import escape
from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from api_client import DeepSeekAPI, REASONER_DISABLED_PARAMS
from config import DEFAULT_API_URL, DEFAULT_FEATURE_SETTINGS, DEFAULT_MODEL, load_runtime_config, merge_feature_settings, save_runtime_config
from data_manager import DataManager
from utils import append_settings_change_log, format_time

try:
    import markdown as mdlib
except ImportError:
    mdlib = None

try:
    from tkhtmlview import HTMLScrolledText
except ImportError:
    HTMLScrolledText = None

TEXT_FILE_EXTENSIONS = {".txt", ".md", ".py", ".json", ".csv", ".log", ".yaml", ".yml", ".ini"}
MARKDOWN_EXTENSIONS = ["fenced_code", "tables", "sane_lists"]

THEME = {
    "font": "Microsoft YaHei UI",
    "font_display": "Microsoft YaHei UI",
    "bg_app": "#ECECF1",
    "bg_panel": "#F6F6F2",
    "bg_panel_muted": "#ECECE6",
    "bg_card": "#FFFFFF",
    "bg_card_alt": "#F7F7F8",
    "bg_chat": "#FFFFFF",
    "bg_muted": "#F7F7F8",
    "bg_input": "#FFFFFF",
    "text_primary": "#202123",
    "text_secondary": "#565869",
    "text_muted": "#8E8EA0",
    "text_light": "#3B3D39",
    "border": "#E5E5EA",
    "border_soft": "#D9D9E3",
    "panel_border": "#DEDED6",
    "primary": "#10A37F",
    "primary_active": "#0E8C6D",
    "success": "#19C37D",
    "success_active": "#10A76A",
    "danger": "#EF4444",
    "danger_active": "#DC2626",
    "warning": "#F59E0B",
    "warning_active": "#D97706",
    "secondary": "#343541",
    "secondary_active": "#2B2C37",
    "accent_soft": "#E7F8F3",
    "user_bubble": "#F7F7F8",
    "assistant_bubble": "#FFFFFF",
    "user_border": "#E5E7EB",
    "assistant_border": "#E5E7EB",
}


def style_button(button, bg, active, fg="#FFFFFF"):
    button.configure(
        bg=bg,
        fg=fg,
        activebackground=active,
        activeforeground=fg,
        relief=tk.FLAT,
        bd=0,
        cursor="hand2",
        font=(THEME["font"], 9, "bold"),
        padx=12,
        pady=7,
    )


def style_selection(widget):
    try:
        widget.configure(
            selectbackground="#2B7FFF",
            selectforeground="#FFFFFF",
            inactiveselectbackground="#B8D3FF",
            exportselection=False,
        )
    except tk.TclError:
        pass


def style_input(widget, bg=None):
    widget.configure(
        relief=tk.FLAT,
        bd=0,
        bg=bg or THEME["bg_input"],
        fg=THEME["text_primary"],
        insertbackground=THEME["text_primary"],
        highlightthickness=1,
        highlightbackground=THEME["border_soft"],
        highlightcolor=THEME["primary"],
        font=(THEME["font"], 10),
    )
    style_selection(widget)


def create_chip(parent, textvariable, bg, fg):
    return tk.Label(
        parent,
        textvariable=textvariable,
        bg=bg,
        fg=fg,
        padx=10,
        pady=5,
        font=(THEME["font"], 8, "bold"),
    )


def markdown_to_html(text):
    source = text or ""
    if mdlib:
        html = mdlib.markdown(source, extensions=MARKDOWN_EXTENSIONS, output_format="html5")
        html = re.sub(r"(<h[1-6][^>]*>.*?</h[1-6]>)\s*<br\s*/?>", r"\1", html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r"<br\s*/?>\s*(<h[1-6][^>]*>)", r"\1", html, flags=re.IGNORECASE)
        return apply_compact_inline_styles(html)
    return f"<pre>{escape(source)}</pre>"


def apply_compact_inline_styles(html):
    replacements = {
        "<h1>": "<h1 style='font-size:16px; margin:6px 0 3px; line-height:1.2; color:#172033;'>",
        "<h2>": "<h2 style='font-size:14px; margin:6px 0 3px; line-height:1.2; color:#172033;'>",
        "<h3>": "<h3 style='font-size:13px; margin:5px 0 2px; line-height:1.2; color:#172033;'>",
        "<h4>": "<h4 style='font-size:12px; margin:4px 0 2px; line-height:1.2; color:#172033;'>",
        "<h5>": "<h5 style='font-size:11px; margin:3px 0 2px; line-height:1.2; color:#172033;'>",
        "<h6>": "<h6 style='font-size:10px; margin:3px 0 1px; line-height:1.2; color:#172033;'>",
        "<p>": "<p style='margin:3px 0; color:#2A3447;'>",
        "<pre>": "<pre style='margin:5px 0; background:#F4EEE4; border:1px solid #E4DACD; padding:8px 10px; border-radius:10px;'>",
        "<code>": "<code style='background:#F4EEE4; padding:2px 4px; border-radius:5px;'>",
        "<blockquote>": "<blockquote style='margin:5px 0; padding-left:10px; border-left:3px solid #CBB89A; color:#5A6476;'>",
        "<ul>": "<ul style='margin:3px 0 3px 14px; padding-left:8px;'>",
        "<ol>": "<ol style='margin:3px 0 3px 14px; padding-left:8px;'>",
        "<table>": "<table style='border-collapse:collapse; margin:5px 0; width:100%; background:#FFFDF8;'>",
        "<th>": "<th style='border:1px solid #E4DACD; padding:5px 6px; text-align:left; background:#F7F2EA;'>",
        "<td>": "<td style='border:1px solid #E4DACD; padding:5px 6px; text-align:left;'>",
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    return html


def wrap_html_document(body):
    return (
        "<html><body style=\"margin:0; background:#FFFDF9;\">"
        "<div style=\"font-family:'Microsoft YaHei UI',sans-serif; font-size:12px; line-height:1.45; color:#172033; padding:10px 12px;\">"
        f"{body}</div></body></html>"
    )

class PositionedDialog(tk.Toplevel):
    def init_window(self, parent, title):
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result = None
        self.configure(bg=THEME["bg_app"])

    def position_dialog(self, parent, width=None, height=None):
        self.update_idletasks()
        parent.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        dw = width or self.winfo_width()
        dh = height or self.winfo_height()
        x = px + int(pw * 0.35) - dw // 2
        y = py + (ph - dh) // 2
        if width and height:
            self.geometry(f"{dw}x{dh}+{max(x,0)}+{max(y,0)}")
        else:
            self.geometry(f"+{max(x,0)}+{max(y,0)}")

class SettingsDialog(PositionedDialog):
    def __init__(self, parent, api_url, api_key):
        super().__init__(parent)
        self.init_window(parent, "API 设置")
        self.api_url_var = tk.StringVar(value=api_url)
        self.api_key_var = tk.StringVar(value=api_key)
        self.show_key_var = tk.BooleanVar(value=False)
        box = tk.Frame(self, padx=14, pady=14, bg=THEME["bg_card"], highlightthickness=1, highlightbackground=THEME["border"])
        box.pack(fill=tk.BOTH, expand=True)
        tk.Label(box, text="API URL", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font"], 10, "bold")).grid(row=0, column=0, sticky="w")
        tk.Entry(box, textvariable=self.api_url_var, width=48, relief=tk.FLAT, bg=THEME["bg_muted"], fg=THEME["text_primary"], font=(THEME["font"], 10)).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8), ipady=6)
        tk.Label(box, text="API Key", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font"], 10, "bold")).grid(row=2, column=0, sticky="w")
        self.api_key_entry = tk.Entry(box, textvariable=self.api_key_var, width=48, show="*", relief=tk.FLAT, bg=THEME["bg_muted"], fg=THEME["text_primary"], font=(THEME["font"], 10))
        self.api_key_entry.grid(row=3, column=0, sticky="ew")
        tk.Checkbutton(box, text="显示", variable=self.show_key_var, command=self.toggle_key, bg=THEME["bg_card"], fg=THEME["text_muted"], activebackground=THEME["bg_card"]).grid(row=3, column=1, sticky="w", padx=(8, 0))
        buttons = tk.Frame(box, bg=THEME["bg_card"])
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        cancel_btn = tk.Button(buttons, text="取消", width=10, command=self.cancel)
        ok_btn = tk.Button(buttons, text="确定", width=10, command=self.save)
        reset_btn = tk.Button(buttons, text="恢复默认", width=10, command=self.reset_defaults)
        style_button(cancel_btn, THEME["secondary"], THEME["secondary_active"])
        style_button(ok_btn, THEME["primary"], THEME["primary_active"])
        style_button(reset_btn, THEME["warning"], THEME["warning_active"])
        cancel_btn.pack(side=tk.RIGHT)
        ok_btn.pack(side=tk.RIGHT, padx=(0, 8))
        reset_btn.pack(side=tk.RIGHT, padx=(0, 8))
        self.bind("<Return>", self.save)
        self.bind("<Escape>", lambda _e: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.api_key_entry.focus_set()
        self.position_dialog(parent)

    def toggle_key(self):
        self.api_key_entry.config(show="" if self.show_key_var.get() else "*")

    def reset_defaults(self):
        self.api_url_var.set(DEFAULT_API_URL)
        self.api_key_var.set("")
        self.show_key_var.set(False)
        self.toggle_key()

    def save(self, _event=None):
        self.result = {
            "api_url": self.api_url_var.get().strip() or DEFAULT_API_URL,
            "api_key": self.api_key_var.get().strip(),
        }
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()

class FeatureSettingsDialog(PositionedDialog):
    def __init__(self, parent, model, feature_settings):
        super().__init__(parent)
        self.init_window(parent, "功能设置")
        self.dialog_width = 960
        self.dialog_height = 720
        self.model_var = tk.StringVar(value=model)
        fs = merge_feature_settings(feature_settings)
        self.max_tokens_var = tk.StringVar(value=str(fs["max_tokens"]))
        self.temperature_var = tk.StringVar(value=str(fs["temperature"]))
        self.top_p_var = tk.StringVar(value=str(fs["top_p"]))
        self.frequency_penalty_var = tk.StringVar(value=str(fs["frequency_penalty"]))
        self.presence_penalty_var = tk.StringVar(value=str(fs["presence_penalty"]))
        self.stop_var = tk.StringVar(value=" | ".join(fs["stop"]))
        self.response_format_var = tk.StringVar(value=fs["response_format"].get("type", "text"))
        self.logprobs_var = tk.BooleanVar(value=bool(fs["logprobs"]))
        self.top_logprobs_var = tk.StringVar(value="" if fs["top_logprobs"] is None else str(fs["top_logprobs"]))
        self.prefix_var = tk.BooleanVar(value=bool(fs["prefix"]))
        self.reasoning_content_var = tk.BooleanVar(value=bool(fs["reasoning_content"]))
        self.tool_choice_var = tk.StringVar(value="" if fs["tool_choice"] is None else self.to_json(fs["tool_choice"]))
        self.section_var = tk.StringVar(value="basic")
        self.reasoner_widgets = []
        self.reasoning_output_widgets = []

        outer = tk.Frame(self, padx=12, pady=12)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(0, weight=1)
        canvas = tk.Canvas(outer, highlightthickness=0, width=self.dialog_width - 40)
        scroll = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas)
        content.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        tabs = tk.Frame(content)
        tabs.grid(row=0, column=0, sticky="w", pady=(0, 10))
        tk.Radiobutton(tabs, text="基础参数", value="basic", variable=self.section_var, indicatoron=False, width=14, command=self.refresh_sections).pack(side=tk.LEFT, padx=(0, 8))
        tk.Radiobutton(tabs, text="高级参数", value="advanced", variable=self.section_var, indicatoron=False, width=14, command=self.refresh_sections).pack(side=tk.LEFT)

        self.basic = tk.Frame(content)
        self.advanced = tk.Frame(content)
        self.basic.grid(row=1, column=0, sticky="ew")
        self.advanced.grid(row=1, column=0, sticky="ew")
        self.basic.grid_columnconfigure(0, weight=1)
        self.advanced.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        self.build_basic()
        self.build_advanced(fs)

        buttons = tk.Frame(outer)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        tk.Button(buttons, text="取消", width=10, command=self.cancel).pack(side=tk.RIGHT)
        tk.Button(buttons, text="确定", width=10, command=self.save).pack(side=tk.RIGHT, padx=(0, 8))
        tk.Button(buttons, text="恢复默认", width=10, command=self.reset_defaults).pack(side=tk.RIGHT, padx=(0, 8))

        self._wheel = self.build_mousewheel_handler(canvas)
        canvas.bind("<MouseWheel>", self._wheel)
        content.bind("<MouseWheel>", self._wheel)
        self.bind("<Escape>", lambda _e: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.apply_reasoner_state()
        self.refresh_sections()
        self.position_dialog(parent, self.dialog_width, self.dialog_height)

    def build_basic(self):
        row = 0
        tk.Label(self.basic, text="思考模式：提升答案准确性，处于思考模式下一些参数无效").grid(row=row, column=0, sticky="w")
        menu = tk.OptionMenu(self.basic, self.model_var, "deepseek-chat", "deepseek-reasoner", command=self.on_model_changed)
        menu.config(width=24)
        menu.grid(row=row + 1, column=0, sticky="w")
        row += 2
        row = self.add_entry(self.basic, row, "模型单次回答的最大长度（含思维链输出）", self.max_tokens_var, "max_tokens参数范围: deepseek-chat 为 1~8192，deepseek-reasoner 为 1~65536")
        row = self.add_entry(self.basic, row, "采样温度", self.temperature_var, "temperature参数默认值为1，范围: 0~2", True)
        row = self.add_entry(self.basic, row, "采样温度的替代方案", self.top_p_var, "top_p参数范围: 0~1，默认值为1不建议同时对temperature和top_p进行修改", True)
        row = self.add_entry(self.basic, row, "重复词惩罚", self.frequency_penalty_var, "frequency_penalty参数范围: -2.0~2.0", True)
        row = self.add_entry(self.basic, row, "存在词惩罚", self.presence_penalty_var, "presence_penalty参数范围: -2.0~2.0", True)
        row = self.add_entry(self.basic, row, "停止词", self.stop_var, "stop参数：最多 16 个字符串的list。多个 stop 用 | 分隔，例如：END | STOP")
        tk.Label(self.basic, text="Json格式输出response_format参数").grid(row=row, column=0, sticky="w")
        menu = tk.OptionMenu(self.basic, self.response_format_var, "text", "json_object")
        menu.config(width=24)
        menu.grid(row=row + 1, column=0, sticky="w")
        tk.Label(self.basic, text="可选值: text / json_object", fg="#777777").grid(row=row + 2, column=0, sticky="w")
        row += 3
        reasoning_box = tk.Checkbutton(self.basic, text="输出 reasoning_content（思维链）", variable=self.reasoning_content_var)
        reasoning_box.grid(row=row, column=0, sticky="w", pady=(8, 0))
        self.reasoning_output_widgets.append(reasoning_box)
        tk.Label(self.basic, text="仅在 deepseek-reasoner 下使用，用于显示 reasoning_content 输出。", fg="#777777").grid(row=row + 1, column=0, sticky="w")
        row += 2
        note = "只使用 model 控制思考模式。model=deepseek-reasoner 时视为思考模式，相关不兼容参数会自动禁用且不会发送。"
        self.reasoner_note = tk.Label(self.basic, text=note, fg="#777777", wraplength=680, justify="left")
        self.reasoner_note.grid(row=row, column=0, sticky="w", pady=(8, 0))

    def build_advanced(self, fs):
        row = 0
        box = tk.Checkbutton(self.advanced, text="启用 logprobs", variable=self.logprobs_var)
        box.grid(row=row, column=0, sticky="w")
        self.reasoner_widgets.append(box)
        tk.Label(self.advanced, text="可选值: true / false", fg="#777777").grid(row=row + 1, column=0, sticky="w")
        row += 2
        row = self.add_entry(self.advanced, row, "top_logprobs", self.top_logprobs_var, "范围: 0~20", True)
        ck = tk.Checkbutton(self.advanced, text="启用 prefix", variable=self.prefix_var)
        ck.grid(row=row, column=0, sticky="w")
        tk.Label(self.advanced, text="可选值: true / false", fg="#777777").grid(row=row + 1, column=0, sticky="w")
        row += 2
        tk.Label(self.advanced, text="tool_choice").grid(row=row, column=0, sticky="w")
        tk.Entry(self.advanced, textvariable=self.tool_choice_var, width=52).grid(row=row + 1, column=0, sticky="ew")
        tk.Label(self.advanced, text="可选值: none / auto / required / JSON 对象", fg="#777777").grid(row=row + 2, column=0, sticky="w")
        row += 3
        tk.Label(self.advanced, text="tools(JSON array)").grid(row=row, column=0, sticky="w")
        self.tools_text = tk.Text(self.advanced, width=52, height=6)
        self.tools_text.grid(row=row + 1, column=0, sticky="ew")
        self.tools_text.insert("1.0", self.to_json(fs["tools"]))
        tk.Label(self.advanced, text="最多 128 个 function，使用 JSON 数组格式", fg="#777777").grid(row=row + 2, column=0, sticky="w")

    def add_entry(self, parent, row, label, variable, hint=None, reasoner_sensitive=False):
        tk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=(8, 4))
        entry = tk.Entry(parent, textvariable=variable, width=52)
        entry.grid(row=row + 1, column=0, sticky="ew")
        if reasoner_sensitive:
            self.reasoner_widgets.append(entry)
        if hint:
            tk.Label(parent, text=hint, fg="#777777").grid(row=row + 2, column=0, sticky="w")
            return row + 3
        return row + 2

    def to_json(self, value):
        return "" if value in (None, "") else json.dumps(value, ensure_ascii=False, indent=2)

    def build_mousewheel_handler(self, canvas):
        def handler(event):
            if not canvas.winfo_exists():
                return "break"
            delta = int(-event.delta / 120)
            if delta:
                canvas.yview_scroll(delta, "units")
            return "break"
        return handler

    def reset_defaults(self):
        defaults = merge_feature_settings(DEFAULT_FEATURE_SETTINGS)
        self.model_var.set(DEFAULT_MODEL)
        self.max_tokens_var.set(str(defaults["max_tokens"]))
        self.temperature_var.set(str(defaults["temperature"]))
        self.top_p_var.set(str(defaults["top_p"]))
        self.frequency_penalty_var.set(str(defaults["frequency_penalty"]))
        self.presence_penalty_var.set(str(defaults["presence_penalty"]))
        self.stop_var.set(" | ".join(defaults["stop"]))
        self.response_format_var.set(defaults["response_format"].get("type", "text"))
        self.logprobs_var.set(bool(defaults["logprobs"]))
        self.top_logprobs_var.set("" if defaults["top_logprobs"] is None else str(defaults["top_logprobs"]))
        self.prefix_var.set(bool(defaults["prefix"]))
        self.reasoning_content_var.set(bool(defaults["reasoning_content"]))
        self.tool_choice_var.set("" if defaults["tool_choice"] is None else self.to_json(defaults["tool_choice"]))
        self.tools_text.delete("1.0", tk.END)
        self.tools_text.insert("1.0", self.to_json(defaults["tools"]))
        self.apply_reasoner_state()

    def refresh_sections(self):
        if self.section_var.get() == "basic":
            self.advanced.grid_remove()
            self.basic.grid()
        else:
            self.basic.grid_remove()
            self.advanced.grid()

    def on_model_changed(self, _selected=None):
        self.apply_reasoner_state()

    def apply_reasoner_state(self):
        reasoner = self.model_var.get() == "deepseek-reasoner"
        state = tk.DISABLED if reasoner else tk.NORMAL
        for widget in self.reasoner_widgets:
            widget.config(state=state)
        output_state = tk.NORMAL if reasoner else tk.DISABLED
        for widget in self.reasoning_output_widgets:
            widget.config(state=output_state)
        if reasoner:
            self.reasoner_note.grid()
        else:
            self.reasoner_note.grid_remove()

    def parse_int(self, value, field_name):
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} 必须是整数。") from exc

    def parse_float(self, value, field_name):
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} 必须是数字。") from exc

    def parse_stop(self):
        raw = self.stop_var.get().strip()
        if not raw:
            return []
        if raw.startswith("["):
            data = json.loads(raw)
            if not isinstance(data, list):
                raise ValueError("stop 必须是字符串数组。")
            items = [str(x) for x in data]
        else:
            items = [x.strip() for x in raw.split("|") if x.strip()]
        if len(items) > 16:
            raise ValueError("stop 最多只能设置 16 个字符串。")
        return items

    def parse_tools(self):
        raw = self.tools_text.get("1.0", tk.END).strip()
        if not raw:
            return []
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("tools 必须是 JSON 数组。")
        if len(data) > 128:
            raise ValueError("tools 最多只能设置 128 个 function。")
        return data

    def parse_tool_choice(self):
        raw = self.tool_choice_var.get().strip()
        if not raw:
            return None
        if raw in {"none", "auto", "required"}:
            return raw
        if raw.startswith("{") or raw.startswith("[") or raw.startswith('"'):
            return json.loads(raw)
        return raw

    def validate_ranges(self, settings):
        max_limit = 65536 if settings["model"] == "deepseek-reasoner" else 8192
        if not 1 <= settings["max_tokens"] <= max_limit:
            raise ValueError(f"max_tokens 超出范围，当前模型允许 1~{max_limit}。")
        if settings["model"] != "deepseek-reasoner":
            if not 0 <= settings["temperature"] <= 2:
                raise ValueError("temperature 超出范围，允许 0~2。")
            if not 0 <= settings["top_p"] <= 1:
                raise ValueError("top_p 超出范围，允许 0~1。")
            if not -2 <= settings["frequency_penalty"] <= 2:
                raise ValueError("frequency_penalty 超出范围，允许 -2.0~2.0。")
            if not -2 <= settings["presence_penalty"] <= 2:
                raise ValueError("presence_penalty 超出范围，允许 -2.0~2.0。")
            if settings["top_logprobs"] is not None and not 0 <= settings["top_logprobs"] <= 20:
                raise ValueError("top_logprobs 超出范围，允许 0~20。")

    def save(self):
        try:
            result = {
                "model": self.model_var.get(),
                "max_tokens": self.parse_int(self.max_tokens_var.get().strip(), "max_tokens"),
                "temperature": self.parse_float(self.temperature_var.get().strip(), "temperature"),
                "top_p": self.parse_float(self.top_p_var.get().strip(), "top_p"),
                "frequency_penalty": self.parse_float(self.frequency_penalty_var.get().strip(), "frequency_penalty"),
                "presence_penalty": self.parse_float(self.presence_penalty_var.get().strip(), "presence_penalty"),
                "stop": self.parse_stop(),
                "response_format": {"type": self.response_format_var.get()},
                "reasoning_content": bool(self.reasoning_content_var.get()),
                "logprobs": bool(self.logprobs_var.get()),
                "top_logprobs": None,
                "tools": self.parse_tools(),
                "tool_choice": self.parse_tool_choice(),
                "prefix": bool(self.prefix_var.get()),
            }
            if self.top_logprobs_var.get().strip():
                result["top_logprobs"] = self.parse_int(self.top_logprobs_var.get().strip(), "top_logprobs")
            self.validate_ranges(result)
        except (ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("参数错误", str(exc), parent=self)
            return
        self.result = result
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()

class SettingsMenuDialog(PositionedDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.init_window(parent, "设置")
        box = tk.Frame(self, padx=16, pady=16, bg=THEME["bg_card"], highlightthickness=1, highlightbackground=THEME["border"])
        box.pack(fill=tk.BOTH, expand=True)
        tk.Label(box, text="设置", font=(THEME["font"], 13, "bold"), bg=THEME["bg_card"], fg=THEME["text_primary"]).pack(anchor="w", pady=(0, 10))
        api_btn = tk.Button(box, text="API 设置", width=24, command=lambda: self.select("api"))
        features_btn = tk.Button(box, text="功能设置", width=24, command=lambda: self.select("features"))
        advanced_btn = tk.Button(box, text="高级设置（预留）", width=24, command=lambda: self.select("advanced"))
        help_btn = tk.Button(box, text="本地帮助文档", width=24, command=lambda: self.select("help_doc"))
        close_btn = tk.Button(box, text="关闭", width=24, command=self.cancel)
        style_button(api_btn, THEME["primary"], THEME["primary_active"])
        style_button(features_btn, THEME["secondary"], THEME["secondary_active"])
        style_button(advanced_btn, "#64748B", "#475569")
        style_button(help_btn, THEME["success"], THEME["success_active"])
        style_button(close_btn, "#9CA3AF", "#6B7280")
        api_btn.pack(fill=tk.X, pady=4)
        features_btn.pack(fill=tk.X, pady=4)
        advanced_btn.pack(fill=tk.X, pady=4)
        help_btn.pack(fill=tk.X, pady=4)
        close_btn.pack(fill=tk.X, pady=(12, 0))
        self.bind("<Escape>", lambda _e: self.cancel())
        self.position_dialog(parent)

    def select(self, action):
        self.result = action
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()

class LocalHelpDocDialog(PositionedDialog):
    def __init__(self, parent, help_doc_path):
        super().__init__(parent)
        self.init_window(parent, "本地帮助文档")
        self.dialog_width = 900
        self.dialog_height = 700
        self.help_doc_path_var = tk.StringVar(value=help_doc_path or "")
        self.use_html_view = HTMLScrolledText is not None
        box = tk.Frame(self, padx=12, pady=12, bg=THEME["bg_card"], highlightthickness=1, highlightbackground=THEME["border"])
        box.pack(fill=tk.BOTH, expand=True)
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(2, weight=1)

        tk.Label(box, text="文档路径", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font"], 10, "bold")).grid(row=0, column=0, sticky="w")
        path_entry = tk.Entry(box, textvariable=self.help_doc_path_var, width=90, relief=tk.FLAT, bg=THEME["bg_muted"], fg=THEME["text_primary"], font=(THEME["font"], 10))
        path_entry.grid(row=1, column=0, sticky="ew", pady=(4, 8))

        top_buttons = tk.Frame(box, bg=THEME["bg_card"])
        top_buttons.grid(row=1, column=1, sticky="e", padx=(8, 0), pady=(4, 8))
        choose_btn = tk.Button(top_buttons, text="选择文档", width=10, command=self.choose_file)
        clear_btn = tk.Button(top_buttons, text="清空", width=8, command=self.clear_path)
        refresh_btn = tk.Button(top_buttons, text="刷新", width=8, command=self.refresh_content)
        style_button(choose_btn, THEME["primary"], THEME["primary_active"])
        style_button(clear_btn, THEME["danger"], THEME["danger_active"])
        style_button(refresh_btn, THEME["secondary"], THEME["secondary_active"])
        choose_btn.pack(side=tk.LEFT)
        clear_btn.pack(side=tk.LEFT, padx=(8, 0))
        refresh_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.markdown_note = tk.StringVar(value="")
        if self.use_html_view:
            self.content = HTMLScrolledText(box, html="<p>加载中...</p>")
            if mdlib is None:
                self.markdown_note.set("未安装 markdown 库，当前以纯文本 HTML 展示。")
        else:
            self.content = scrolledtext.ScrolledText(box, wrap=tk.WORD, font=("Microsoft YaHei UI", 10), state=tk.DISABLED)
            self.markdown_note.set("未安装 tkhtmlview，当前以纯文本展示。")
        self.content.grid(row=2, column=0, columnspan=2, sticky="nsew")
        tk.Label(box, textvariable=self.markdown_note, fg=THEME["text_muted"], bg=THEME["bg_card"], font=(THEME["font"], 9)).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        bottom = tk.Frame(box, bg=THEME["bg_card"])
        bottom.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
        close_btn = tk.Button(bottom, text="关闭", width=10, command=self.save)
        style_button(close_btn, THEME["secondary"], THEME["secondary_active"])
        close_btn.pack(side=tk.RIGHT)

        self.bind("<Escape>", lambda _e: self.save())
        self.protocol("WM_DELETE_WINDOW", self.save)
        self.refresh_content()
        self.position_dialog(parent, self.dialog_width, self.dialog_height)

    def set_content(self, text, markdown=False):
        if self.use_html_view:
            body = markdown_to_html(text) if markdown else f"<pre>{escape(text or '')}</pre>"
            self.content.set_html(wrap_html_document(body))
            return
        self.content.config(state=tk.NORMAL)
        self.content.delete("1.0", tk.END)
        self.content.insert("1.0", text)
        self.content.config(state=tk.DISABLED)

    def read_doc_text(self, path):
        errors = []
        for encoding in ("utf-8", "utf-8-sig", "gbk"):
            try:
                with path.open("r", encoding=encoding) as file:
                    text = file.read()
                break
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(str(exc))
        else:
            raise ValueError("无法读取文档，请确认编码为 UTF-8 或 GBK。")
        limit = 400_000
        if len(text) > limit:
            text = text[:limit] + "\n\n[内容过长，已截断显示]"
        return text

    def refresh_content(self):
        raw_path = self.help_doc_path_var.get().strip()
        if not raw_path:
            self.set_content("未配置帮助文档路径。\n\n请点击“选择文档”选择本地 .txt / .md / .json 文件。")
            return
        path = Path(raw_path)
        if not path.exists() or not path.is_file():
            self.set_content(f"文档不存在：\n{path}")
            return
        try:
            text = self.read_doc_text(path)
            is_markdown = path.suffix.lower() == ".md"
            self.set_content(text or "[文档为空]", markdown=is_markdown)
        except ValueError as exc:
            self.set_content(str(exc))

    def choose_file(self):
        selected = filedialog.askopenfilename(
            title="选择本地帮助文档",
            filetypes=[
                ("支持的文档", "*.txt *.md *.json *.log *.yaml *.yml *.ini *.csv"),
                ("所有文件", "*.*"),
            ],
        )
        if not selected:
            return
        self.help_doc_path_var.set(selected)
        self.refresh_content()

    def clear_path(self):
        self.help_doc_path_var.set("")
        self.refresh_content()

    def save(self):
        self.result = {"help_doc_path": self.help_doc_path_var.get().strip()}
        self.destroy()

class DeepSeekGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SeekDesk")
        self.root.geometry("1220x760")
        self.root.minsize(980, 600)
        runtime = load_runtime_config()
        self.api_key = runtime["api_key"]
        self.api_url = runtime["api_url"]
        self.proxy_url = runtime.get("proxy_url", "")
        self.model = runtime["model"]
        self.feature_settings = merge_feature_settings(runtime["feature_settings"])
        self.help_doc_path = (runtime.get("help_doc_path", "") or "").strip() or self.get_default_help_doc_path()
        self.data_mgr = DataManager()
        self.api = DeepSeekAPI(self.api_key, self.api_url, self.model, proxy_url=self.proxy_url)
        self.current_conv_id = None
        self.listbox_ids = []
        self.pending_requests = {}
        self.streaming_buffers = {}
        self.stream_refresh_jobs = {}
        self.stream_pending_follow = {}
        self.chat_auto_follow = True
        self.status_var = tk.StringVar(value=self.build_status_text())
        self.header_title_var = tk.StringVar(value="准备开始新的对话")
        self.header_meta_var = tk.StringVar(value="")
        self.setup_ui()
        self.notify_markdown_dependencies()
        self.load_conversations_list()
        items = self.data_mgr.get_conversation_list()
        if items:
            self.current_conv_id = items[0][0]
            self.display_conversation(self.current_conv_id)
        else:
            self.new_conversation()

    def notify_markdown_dependencies(self):
        missing = []
        if mdlib is None:
            missing.append("markdown")
        if missing:
            messagebox.showwarning(
                "Markdown 依赖缺失",
                "检测到缺少依赖："
                + ", ".join(missing)
                + "\n\n请执行：pip install markdown\n安装后重启应用即可启用完整 Markdown 渲染。",
            )

    def get_default_help_doc_path(self):
        for name in ("README.md", "Readme.md", "readme.md"):
            candidate = Path(name)
            if candidate.exists() and candidate.is_file():
                return str(candidate)
        return "README.md"

    def build_status_text(self):
        key_status = "API Key 已配置" if self.api_key else "等待配置 API Key"
        thinking = "深度推理" if self.model == "deepseek-reasoner" else "标准对话"
        pending = sum(self.pending_requests.values())
        render_mode = "Markdown 渲染" if getattr(self, "use_markdown_chat", False) else "纯文本渲染"
        return f"{self.model} · {thinking} · {render_mode} · {key_status} · {pending} 个请求处理中"

    def persist_runtime_config(self):
        save_runtime_config(
            self.api_key,
            self.api_url,
            model=self.model,
            feature_settings=self.feature_settings,
            proxy_url=self.proxy_url,
            help_doc_path=self.help_doc_path,
        )

    def get_request_options(self):
        options = merge_feature_settings(self.feature_settings)
        if not options.get("logprobs"):
            options["top_logprobs"] = None
        if self.model == "deepseek-reasoner":
            for key in REASONER_DISABLED_PARAMS:
                options.pop(key, None)
            options["reasoning_content"] = bool(options.get("reasoning_content"))
        else:
            options.pop("reasoning_content", None)
        return options

    def refresh_status(self):
        self.status_var.set(self.build_status_text())
        self.refresh_context_labels()

    def refresh_context_labels(self):
        self.header_meta_var.set(self.build_status_text())
        if not self.current_conv_id:
            self.header_title_var.set("准备开始新的对话")
            return
        conversation = self.data_mgr.get_conversation(self.current_conv_id) or {}
        title = conversation.get("title", "未命名对话")
        self.header_title_var.set(title)

    def schedule_on_ui(self, callback):
        self.root.after(0, callback)

    def setup_ui(self):
        self.root.configure(bg=THEME["bg_app"])
        self.root.option_add("*Button.highlightThickness", 0)
        shell = tk.Frame(self.root, bg=THEME["bg_app"])
        shell.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        shell.grid_columnconfigure(0, weight=0)
        shell.grid_columnconfigure(1, weight=1)
        shell.grid_rowconfigure(0, weight=1)

        left = tk.Frame(shell, width=272, bg=THEME["bg_panel"], highlightthickness=1, highlightbackground=THEME["panel_border"])
        left.grid(row=0, column=0, sticky="ns")
        left.grid_propagate(False)

        brand = tk.Frame(left, bg=THEME["bg_panel"])
        brand.pack(fill=tk.X, padx=16, pady=(18, 12))
        tk.Label(brand, text="SeekDesk", bg=THEME["bg_panel"], fg=THEME["text_light"], font=(THEME["font_display"], 15, "bold")).pack(anchor="w")

        actions = tk.Frame(left, bg=THEME["bg_panel"])
        actions.pack(fill=tk.X, padx=16, pady=(0, 10))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)
        new_btn = tk.Button(actions, text="新建对话", command=self.new_conversation)
        setting_btn = tk.Button(actions, text="设置中心", command=self.open_settings_menu)
        del_btn = tk.Button(actions, text="删除当前", command=self.delete_current_conversation)
        clear_btn = tk.Button(actions, text="清空历史", command=self.delete_all_conversations)
        style_button(new_btn, THEME["primary"], THEME["primary_active"])
        style_button(setting_btn, "#E9E8E2", "#DDDCD4", fg=THEME["text_primary"])
        style_button(del_btn, "#F3E4E4", "#EAD4D4", fg="#9F3535")
        style_button(clear_btn, "#EFE9D7", "#E4DBC2", fg="#8A6417")
        new_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=(0, 8))
        setting_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=(0, 8))
        del_btn.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        clear_btn.grid(row=1, column=1, sticky="ew", padx=(6, 0))

        history_card = tk.Frame(left, bg=THEME["bg_panel_muted"], highlightthickness=1, highlightbackground=THEME["panel_border"])
        history_card.pack(fill=tk.BOTH, expand=True, padx=16, pady=(4, 14))
        tk.Label(history_card, text="历史对话", bg=THEME["bg_panel_muted"], fg=THEME["text_light"], font=(THEME["font"], 10, "bold")).pack(anchor="w", padx=12, pady=(12, 8))

        list_frame = tk.Frame(history_card, bg=THEME["bg_panel_muted"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        scrollbar = tk.Scrollbar(list_frame, bg=THEME["bg_panel_muted"], troughcolor="#E2E2DB", activebackground="#CFCFC6")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.conv_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=(THEME["font"], 9),
            bg=THEME["bg_panel"],
            fg=THEME["text_primary"],
            selectbackground="#E3E3DB",
            selectforeground=THEME["text_primary"],
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            activestyle="none",
            selectborderwidth=0,
        )
        self.conv_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.conv_listbox.yview)
        self.conv_listbox.bind("<<ListboxSelect>>", self.on_conversation_selected)

        right = tk.Frame(shell, bg=THEME["bg_app"])
        right.grid(row=0, column=1, sticky="nswe", padx=(12, 0))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        header = tk.Frame(right, bg=THEME["bg_card"], highlightthickness=1, highlightbackground=THEME["border"])
        header.grid(row=0, column=0, sticky="ew")
        title_box = tk.Frame(header, bg=THEME["bg_card"])
        title_box.grid(row=0, column=0, sticky="w", padx=22, pady=16)
        tk.Label(title_box, textvariable=self.header_title_var, bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_display"], 17, "bold")).pack(anchor="w")
        tk.Label(title_box, textvariable=self.header_meta_var, bg=THEME["bg_card"], fg=THEME["text_secondary"], font=(THEME["font"], 9)).pack(anchor="w", pady=(4, 0))

        chat_card = tk.Frame(right, bg=THEME["bg_card"], highlightthickness=1, highlightbackground=THEME["border"])
        chat_card.grid(row=1, column=0, sticky="nswe", pady=(10, 10))
        chat_card.grid_rowconfigure(0, weight=1)
        chat_card.grid_columnconfigure(0, weight=1)
        chat_inner = tk.Frame(chat_card, bg=THEME["bg_chat"])
        chat_inner.grid(row=0, column=0, sticky="nswe", padx=1, pady=1)
        chat_inner.grid_rowconfigure(0, weight=1)
        chat_inner.grid_columnconfigure(0, weight=1)
        self.use_markdown_chat = False
        self.chat_area = scrolledtext.ScrolledText(
            chat_inner,
            wrap=tk.WORD,
            font=(THEME["font"], 9),
            state=tk.DISABLED,
            relief=tk.FLAT,
            bd=0,
            bg=THEME["bg_chat"],
            fg=THEME["text_primary"],
            insertbackground=THEME["text_primary"],
        )
        style_selection(self.chat_area)
        self.chat_area.tag_config("user", foreground=THEME["primary"], font=(THEME["font"], 9, "bold"))
        self.chat_area.tag_config("ai", foreground=THEME["text_primary"], font=(THEME["font"], 9, "bold"))
        self.chat_area.tag_config("reasoning_title", foreground=THEME["text_secondary"], font=(THEME["font"], 9, "bold"))
        self.chat_area.tag_config("reasoning", foreground=THEME["text_secondary"], font=(THEME["font"], 8))
        self.chat_area.tag_config("time", foreground=THEME["text_muted"], font=(THEME["font"], 7))
        self.chat_area.grid(row=0, column=0, sticky="nswe", padx=16, pady=14)
        self.chat_menu = tk.Menu(self.root, tearoff=0)
        self.chat_menu.add_command(label="复制选中", command=self.copy_chat_selection)
        self.chat_menu.add_command(label="复制全部", command=self.copy_all_chat_text)
        self.chat_area.bind("<Control-c>", self.copy_chat_selection)
        self.chat_area.bind("<Button-3>", self.open_chat_context_menu)
        for evt in ("<MouseWheel>", "<Button-4>", "<Button-5>", "<Prior>", "<Next>", "<Key-Up>", "<Key-Down>", "<ButtonRelease-1>"):
            self.chat_area.bind(evt, self.mark_chat_manual_scroll)
        bottom = tk.Frame(right, bg=THEME["bg_card"], highlightthickness=1, highlightbackground=THEME["border"])
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)
        input_shell = tk.Frame(bottom, bg=THEME["bg_input"], highlightthickness=1, highlightbackground=THEME["border_soft"])
        input_shell.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 12))
        input_shell.grid_columnconfigure(0, weight=1)
        self.input_entry = tk.Text(input_shell, height=5, wrap=tk.WORD)
        style_input(self.input_entry)
        self.input_entry.configure(highlightthickness=0, bg=THEME["bg_input"])
        self.input_entry.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        self.input_entry.bind("<Return>", self.handle_input_return)
        self.input_entry.bind("<KP_Enter>", self.handle_input_return)

        actions_bar = tk.Frame(bottom, bg=THEME["bg_card"])
        actions_bar.grid(row=1, column=0, sticky="e", padx=18, pady=(0, 14))
        action_buttons = tk.Frame(actions_bar, bg=THEME["bg_card"])
        action_buttons.grid(row=0, column=0, sticky="e")
        self.attach_button = tk.Button(action_buttons, text="导入文本", width=10, command=self.attach_file)
        style_button(self.attach_button, THEME["bg_card_alt"], THEME["bg_muted"], fg=THEME["text_primary"])
        self.attach_button.pack(side=tk.LEFT, padx=(0, 8))
        copy_btn = tk.Button(action_buttons, text="复制对话", width=10, command=self.copy_all_chat_text)
        style_button(copy_btn, THEME["bg_card_alt"], THEME["bg_muted"], fg=THEME["text_primary"])
        copy_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.send_button = tk.Button(action_buttons, text="发送消息", width=10, command=self.send_message)
        style_button(self.send_button, THEME["primary"], THEME["primary_active"])
        self.send_button.pack(side=tk.LEFT)

        self.refresh_context_labels()

    def handle_input_return(self, event):
        if event.state & 0x1:
            return None
        self.send_message()
        return "break"

    def show_modal_dialog(self, dialog):
        disabled = False
        try:
            self.root.attributes("-disabled", True)
            disabled = True
        except tk.TclError:
            pass
        try:
            self.root.wait_window(dialog)
        finally:
            if disabled:
                try:
                    self.root.attributes("-disabled", False)
                except tk.TclError:
                    pass
            self.root.focus_force()
        return getattr(dialog, "result", None)

    def open_settings_menu(self):
        action = self.show_modal_dialog(SettingsMenuDialog(self.root))
        if action == "api":
            self.open_settings()
        elif action == "features":
            self.open_feature_settings()
        elif action == "advanced":
            messagebox.showinfo("提示", "该设置项暂未实现，已预留入口。")
        elif action == "help_doc":
            self.open_local_help_doc()

    def open_settings(self):
        before = {"api_url": self.api_url, "api_key": self.api_key}
        result = self.show_modal_dialog(SettingsDialog(self.root, self.api_url, self.api_key))
        if not result:
            return
        self.api_url = result["api_url"]
        self.api_key = result["api_key"]
        self.persist_runtime_config()
        append_settings_change_log("api", before, {"api_url": self.api_url, "api_key": self.api_key})
        self.api.update_config(self.api_key, self.api_url, self.model, proxy_url=self.proxy_url)
        self.refresh_status()
        messagebox.showinfo("提示", "API 配置已保存。")

    def open_feature_settings(self):
        before = {"model": self.model, "feature_settings": merge_feature_settings(self.feature_settings)}
        result = self.show_modal_dialog(FeatureSettingsDialog(self.root, self.model, self.feature_settings))
        if not result:
            return
        self.model = result.pop("model", self.model)
        self.feature_settings = merge_feature_settings(result)
        self.persist_runtime_config()
        append_settings_change_log("features", before, {"model": self.model, "feature_settings": merge_feature_settings(self.feature_settings)})
        self.api.update_config(self.api_key, self.api_url, self.model, proxy_url=self.proxy_url)
        self.refresh_status()
        messagebox.showinfo("提示", "功能设置已保存。")

    def open_local_help_doc(self):
        result = self.show_modal_dialog(LocalHelpDocDialog(self.root, self.help_doc_path))
        if not result:
            return
        next_path = result.get("help_doc_path", "").strip()
        if next_path == self.help_doc_path:
            return
        before = {"help_doc_path": self.help_doc_path}
        self.help_doc_path = next_path
        self.persist_runtime_config()
        append_settings_change_log("help_doc", before, {"help_doc_path": self.help_doc_path})

    def load_conversations_list(self):
        self.conv_listbox.delete(0, tk.END)
        self.listbox_ids = []
        for conv_id, title, updated in self.data_mgr.get_conversation_list():
            suffix = f" [处理中:{self.pending_requests.get(conv_id,0)}]" if self.pending_requests.get(conv_id, 0) else ""
            label = f"{title} ({format_time(updated)}){suffix}" if updated else f"{title}{suffix}"
            self.conv_listbox.insert(tk.END, label)
            self.listbox_ids.append(conv_id)
        if self.current_conv_id in self.listbox_ids:
            idx = self.listbox_ids.index(self.current_conv_id)
            self.conv_listbox.selection_clear(0, tk.END)
            self.conv_listbox.selection_set(idx)
            self.conv_listbox.activate(idx)
        self.refresh_context_labels()

    def get_current_conv_id_from_listbox(self):
        sel = self.conv_listbox.curselection()
        if not sel:
            return None
        idx = sel[0]
        return self.listbox_ids[idx] if 0 <= idx < len(self.listbox_ids) else None

    def on_conversation_selected(self, _event):
        conv_id = self.get_current_conv_id_from_listbox()
        if conv_id and conv_id != self.current_conv_id:
            self.current_conv_id = conv_id
            self.display_conversation(conv_id)

    def open_chat_context_menu(self, event):
        self.chat_menu.tk_popup(event.x_root, event.y_root)

    def format_conversation_as_text(self, conv_id):
        conversation = self.data_mgr.get_conversation(conv_id) or {}
        lines = []
        for message in conversation.get("messages", []):
            role = message.get("role", "")
            title = "用户" if role == "user" else "DeepSeek"
            ts = message.get("timestamp", "")
            header = f"{title} ({format_time(ts)})" if ts else title
            lines.append(header)
            reasoning = message.get("reasoning_content", "")
            if role == "assistant" and reasoning:
                lines.append("思维链:")
                lines.append(reasoning)
            lines.append(message.get("content", ""))
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def copy_chat_selection(self, _event=None):
        try:
            selected = self.chat_area.get("sel.first", "sel.last")
        except tk.TclError:
            return "break"
        if selected:
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
        return "break"

    def copy_all_chat_text(self):
        if not self.current_conv_id:
            return
        text = self.format_conversation_as_text(self.current_conv_id)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("提示", "当前对话已复制到剪贴板。")

    def is_chat_near_bottom(self):
        try:
            return self.chat_area.yview()[1] >= 0.995
        except Exception:
            return True

    def scroll_chat_to_end(self):
        try:
            self.chat_area.yview_moveto(1.0)
        except Exception:
            pass

    def mark_chat_manual_scroll(self, _event=None):
        self.root.after(30, self.update_chat_follow_state)

    def update_chat_follow_state(self):
        self.chat_auto_follow = self.is_chat_near_bottom()

    def schedule_stream_refresh(self, conv_id, should_follow):
        self.stream_pending_follow[conv_id] = self.stream_pending_follow.get(conv_id, False) or should_follow
        if conv_id in self.stream_refresh_jobs:
            return

        def do_refresh():
            self.stream_refresh_jobs.pop(conv_id, None)
            follow = self.stream_pending_follow.pop(conv_id, False)
            self.refresh_conversation(conv_id, stick_to_bottom=follow)

        self.stream_refresh_jobs[conv_id] = self.root.after(120, do_refresh)

    def cancel_stream_refresh(self, conv_id):
        job = self.stream_refresh_jobs.pop(conv_id, None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
        self.stream_pending_follow.pop(conv_id, None)

    def build_chat_html(self, messages):
        blocks = []
        for message in messages:
            role = message.get("role", "")
            content = message.get("content", "")
            ts = message.get("timestamp", "")
            reasoning = message.get("reasoning_content", "")
            is_user = role == "user"
            prefix = "用户" if is_user else "DeepSeek"
            time_html = f"<span style='font-size:10px; color:#6f7781; margin-left:6px; font-weight:400;'>({escape(format_time(ts))})</span>" if ts else ""
            content_html = markdown_to_html(content or "")
            reasoning_html = ""
            output_label_html = ""
            if role == "assistant" and reasoning:
                reasoning_html = (
                    "<div style='color:#8a5a00; font-weight:700; margin-top:4px;'>思维链</div>"
                    f"<div style='background:#FFF8E8; border:1px dashed #E6C987; border-radius:12px; padding:8px 10px; margin-top:4px;'>{markdown_to_html(reasoning)}</div>"
                )
                output_label_html = "<div style='color:#8a5a00; font-weight:700; margin-top:8px;'>输出结果</div>"
            align = "margin-left:16%;" if is_user else "margin-right:16%;"
            box_bg = THEME["user_bubble"] if is_user else THEME["assistant_bubble"]
            box_border = THEME["user_border"] if is_user else THEME["assistant_border"]
            label_color = THEME["primary"] if is_user else "#8A5A00"
            blocks.append(
                f"<div style='border-radius:18px; padding:12px 14px; margin:10px 0; border:1px solid {box_border}; background:{box_bg}; box-shadow:0 6px 18px rgba(23,32,51,0.05); {align}'>"
                f"<div style='font-weight:700; margin-bottom:4px; color:{label_color};'>{escape(prefix)}{time_html}</div>"
                f"{reasoning_html}"
                f"{output_label_html}"
                f"<div>{content_html}</div>"
                "</div>"
            )
        return wrap_html_document("".join(blocks))

    def display_conversation(self, conv_id, stick_to_bottom=None, top_index=None):
        conversation = self.data_mgr.get_conversation(conv_id)
        if not conversation:
            return
        self.refresh_context_labels()
        if self.use_markdown_chat:
            if stick_to_bottom is None:
                stick_to_bottom = self.chat_auto_follow
            html_doc = self.build_chat_html(conversation.get("messages", []))
            self.chat_area.set_html(html_doc)
            if stick_to_bottom:
                self.scroll_chat_to_end()
                self.chat_auto_follow = True
            return
        current_view = self.chat_area.yview()
        if top_index is None:
            top_index = self.chat_area.index("@0,0")
        if stick_to_bottom is None:
            stick_to_bottom = current_view[1] >= 0.999
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete("1.0", tk.END)
        for message in conversation.get("messages", []):
            self.insert_message(
                message.get("role", ""),
                message.get("content", ""),
                message.get("timestamp", ""),
                message.get("reasoning_content", ""),
            )
        if stick_to_bottom:
            self.chat_area.see(tk.END)
        else:
            self.chat_area.yview(top_index)
        self.chat_area.config(state=tk.DISABLED)

    def insert_message(self, role, content, timestamp=None, reasoning_content=""):
        tag = "user" if role == "user" else "ai"
        prefix = "用户" if role == "user" else "DeepSeek"
        if timestamp:
            self.chat_area.insert(tk.END, f"{prefix} ({format_time(timestamp)})\n", "time")
        else:
            self.chat_area.insert(tk.END, f"{prefix}\n", tag)
        if role == "assistant" and reasoning_content:
            self.chat_area.insert(tk.END, "思维链\n", "reasoning_title")
            self.chat_area.insert(tk.END, f"{reasoning_content}\n", "reasoning")
        self.chat_area.insert(tk.END, f"{content}\n\n", tag)

    def refresh_conversation(self, conv_id, stick_to_bottom=None):
        top_index = None
        if not self.use_markdown_chat:
            top_index = self.chat_area.index("@0,0")
        self.load_conversations_list()
        self.refresh_status()
        if self.current_conv_id == conv_id:
            self.display_conversation(conv_id, stick_to_bottom=stick_to_bottom, top_index=top_index)

    def new_conversation(self):
        conv_id = self.data_mgr.new_conversation()
        self.current_conv_id = conv_id
        self.load_conversations_list()
        if self.use_markdown_chat:
            self.chat_area.set_html(
                wrap_html_document(
                    "<div style='border-radius:18px; padding:16px 18px; margin:10px 0; border:1px solid #EBCF96; background:#FFF3D9; box-shadow:0 6px 18px rgba(23,32,51,0.05); margin-right:16%;'>"
                    "<div style='font-weight:700; margin-bottom:6px; color:#8A5A00;'>DeepSeek</div>"
                    f"<div>{markdown_to_html('新对话已创建。可以直接开始提问、粘贴需求，或者导入文本文件。')}</div></div>"
                )
            )
            self.scroll_chat_to_end()
            self.chat_auto_follow = True
        else:
            self.chat_area.config(state=tk.NORMAL)
            self.chat_area.delete("1.0", tk.END)
            self.insert_message("assistant", "新对话已创建，可以开始聊天了。")
            self.chat_area.see(tk.END)
            self.chat_area.config(state=tk.DISABLED)
        self.refresh_status()

    def delete_current_conversation(self):
        conv_id = self.get_current_conv_id_from_listbox()
        if not conv_id:
            messagebox.showinfo("提示", "请先选择要删除的对话。")
            return
        if self.pending_requests.get(conv_id, 0):
            messagebox.showwarning("提示", "当前对话仍有请求在处理中，暂时不能删除。")
            return
        title = (self.data_mgr.get_conversation(conv_id) or {}).get("title", "未命名对话")
        if not messagebox.askyesno("确认删除", f"确定删除对话“{title}”吗？"):
            return
        self.data_mgr.delete_conversation(conv_id)
        self.current_conv_id = None if conv_id == self.current_conv_id else self.current_conv_id
        self.streaming_buffers = {k: v for k, v in self.streaming_buffers.items() if k[0] != conv_id}
        items = self.data_mgr.get_conversation_list()
        if items:
            self.current_conv_id = items[0][0]
            self.load_conversations_list()
            self.display_conversation(self.current_conv_id)
        else:
            self.load_conversations_list()
            self.new_conversation()
        self.refresh_status()

    def delete_all_conversations(self):
        if not self.data_mgr.conversations:
            messagebox.showinfo("提示", "没有历史对话可删除。")
            return
        if self.pending_requests:
            messagebox.showwarning("提示", "仍有请求在处理中，暂时不能清空历史。")
            return
        if not messagebox.askyesno("确认删除", "此操作将删除全部历史对话，且无法恢复。是否继续？"):
            return
        self.data_mgr.delete_all()
        self.current_conv_id = None
        self.streaming_buffers.clear()
        self.load_conversations_list()
        self.new_conversation()

    def attach_file(self):
        file_path = filedialog.askopenfilename(title="选择文本文件")
        if not file_path:
            return
        path = Path(file_path)
        if path.suffix.lower() not in TEXT_FILE_EXTENSIONS:
            messagebox.showwarning("不支持的文件", "目前仅支持导入常见文本文件。")
            return
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = path.read_text(encoding="gbk")
            except OSError as exc:
                messagebox.showerror("读取失败", f"无法读取文件：{exc}")
                return
        except OSError as exc:
            messagebox.showerror("读取失败", f"无法读取文件：{exc}")
            return
        if not content.strip():
            messagebox.showinfo("提示", "文件内容为空。")
            return
        self.input_entry.delete("1.0", tk.END)
        self.input_entry.insert("1.0", f"以下是文件 {path.name} 的内容：\n\n{content}"[:5000])
        self.input_entry.focus_set()

    def send_message(self, event=None):
        if event is not None:
            del event
        user_input = self.input_entry.get("1.0", tk.END).strip()
        if not user_input:
            return
        if not self.api_key:
            if messagebox.askyesno("缺少 API Key", "当前未配置 API Key，是否现在去设置？"):
                self.open_settings()
            return
        if not self.current_conv_id:
            self.new_conversation()
        conv_id = self.current_conv_id
        request_options = self.get_request_options()
        self.input_entry.delete("1.0", tk.END)
        self.data_mgr.add_message(conv_id, "user", user_input)
        assistant_index = self.data_mgr.add_message(conv_id, "assistant", "", "")
        history = self.data_mgr.get_messages(conv_id)[:-1]
        self.pending_requests[conv_id] = self.pending_requests.get(conv_id, 0) + 1
        self.streaming_buffers[(conv_id, assistant_index)] = {"content": "", "reasoning_content": ""}
        self.refresh_conversation(conv_id, stick_to_bottom=True)

        def finalize():
            remaining = self.pending_requests.get(conv_id, 0) - 1
            if remaining > 0:
                self.pending_requests[conv_id] = remaining
            else:
                self.pending_requests.pop(conv_id, None)

        def on_chunk(chunk):
            key = (conv_id, assistant_index)
            should_follow = self.current_conv_id != conv_id or self.chat_auto_follow
            buffer = self.streaming_buffers.get(key, {"content": "", "reasoning_content": ""})
            content_piece = chunk.get("content", "")
            reasoning_piece = chunk.get("reasoning_content", "")
            if content_piece:
                buffer["content"] += content_piece
            if reasoning_piece and request_options.get("reasoning_content"):
                buffer["reasoning_content"] += reasoning_piece
            self.streaming_buffers[key] = buffer
            self.data_mgr.update_message(conv_id, assistant_index, buffer["content"], buffer["reasoning_content"])
            if self.use_markdown_chat:
                self.schedule_stream_refresh(conv_id, should_follow)
            else:
                self.refresh_conversation(conv_id, stick_to_bottom=should_follow)

        def on_success(result):
            key = (conv_id, assistant_index)
            should_follow = self.current_conv_id != conv_id or self.chat_auto_follow
            buffer = self.streaming_buffers.get(key, {"content": "", "reasoning_content": ""})
            content = result.get("content") or buffer["content"]
            reasoning = buffer["reasoning_content"]
            if request_options.get("reasoning_content"):
                reasoning = result.get("reasoning_content") or reasoning
            self.data_mgr.update_message(conv_id, assistant_index, content, reasoning)
            self.streaming_buffers.pop(key, None)
            finalize()
            self.cancel_stream_refresh(conv_id)
            self.refresh_conversation(conv_id, stick_to_bottom=should_follow)

        def on_error(error_msg):
            key = (conv_id, assistant_index)
            should_follow = self.current_conv_id != conv_id or self.chat_auto_follow
            self.data_mgr.update_message(conv_id, assistant_index, f"请求失败：{error_msg}")
            self.streaming_buffers.pop(key, None)
            finalize()
            self.cancel_stream_refresh(conv_id)
            self.refresh_conversation(conv_id, stick_to_bottom=should_follow)

        self.api.call(history, on_success, on_error, scheduler=self.schedule_on_ui, stream=True, chunk_callback=on_chunk, request_options=request_options)
