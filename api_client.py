import json
import threading

import certifi
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils import append_api_request_log


REASONER_DISABLED_PARAMS = {
    "temperature",
    "top_p",
    "presence_penalty",
    "frequency_penalty",
    "logprobs",
    "top_logprobs",
}

LOCAL_ONLY_OPTIONS = {"reasoning_content"}


class DeepSeekAPI:
    def __init__(self, api_key, api_url, model="deepseek-chat", timeout=30, proxy_url=""):
        self.api_key = api_key
        self.url = api_url
        self.model = model
        self.timeout = timeout
        self.proxy_url = (proxy_url or "").strip()
        self.session = self.create_session()

    def create_session(self):
        session = requests.Session()
        session.verify = certifi.where()
        session.headers.update(
            {
                "Accept": "application/json, text/event-stream",
                "User-Agent": "SeekDesk/1.0",
            }
        )
        retry = Retry(
            total=2,
            connect=2,
            read=0,
            status=2,
            backoff_factor=0.6,
            allowed_methods=frozenset({"POST"}),
            status_forcelist=(429, 500, 502, 503, 504),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=8)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        if self.proxy_url:
            session.proxies.update({"http": self.proxy_url, "https": self.proxy_url})
        return session

    def reset_session(self):
        try:
            self.session.close()
        except Exception:
            pass
        self.session = self.create_session()

    def update_config(self, api_key, api_url, model=None, proxy_url=None):
        self.api_key = api_key
        self.url = api_url
        if model:
            self.model = model
        if proxy_url is not None:
            next_proxy = (proxy_url or "").strip()
            if next_proxy != self.proxy_url:
                self.proxy_url = next_proxy
                self.reset_session()

    def prepare_messages(self, messages, request_options=None):
        prepared = list(messages or [])
        response_format = (request_options or {}).get("response_format") or {}
        if response_format.get("type") != "json_object":
            return prepared

        prompt_text = "\n".join(
            message.get("content", "")
            for message in prepared
            if message.get("role") in {"system", "user"} and isinstance(message.get("content"), str)
        )
        if "json" in prompt_text.lower():
            return prepared

        json_guidance = {
            "role": "system",
            "content": (
                "Return the final answer as valid JSON only.\n"
                "EXAMPLE JSON OUTPUT:\n"
                '{\n  "result": "example"\n}\n'
                "Do not wrap the JSON in markdown code fences."
            ),
        }
        return [json_guidance, *prepared]

    def build_payload(self, messages, stream, request_options=None):
        payload = {
            "model": self.model,
            "messages": self.prepare_messages(messages, request_options),
            "stream": stream,
        }

        options = dict(request_options or {})
        if self.model == "deepseek-reasoner":
            for key in REASONER_DISABLED_PARAMS:
                options.pop(key, None)

        for key, value in options.items():
            if value is None:
                continue
            if key in LOCAL_ONLY_OPTIONS:
                continue
            if key in {"stop", "tools"} and value == []:
                continue
            if key == "tool_choice" and value == "":
                continue
            if key == "prefix" and value is False:
                continue
            payload[key] = value

        return payload

    def post_with_recovery(self, payload, headers, stream):
        try:
            return self.session.post(
                self.url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
                stream=stream,
            )
        except requests.exceptions.SSLError:
            self.reset_session()
            retry_headers = dict(headers)
            retry_headers["Connection"] = "close"
            return self.session.post(
                self.url,
                headers=retry_headers,
                json=payload,
                timeout=self.timeout,
                stream=stream,
            )

    def call(
        self,
        messages,
        callback,
        error_callback,
        scheduler=None,
        stream=True,
        chunk_callback=None,
        done_callback=None,
        request_options=None,
    ):
        def deliver(fn, *args):
            if not fn:
                return
            if scheduler:
                scheduler(lambda: fn(*args))
            else:
                fn(*args)

        def extract_error_message(response, fallback):
            try:
                details = response.json()
            except Exception:
                return fallback

            if isinstance(details, dict):
                api_error = details.get("error")
                if isinstance(api_error, dict) and api_error.get("message"):
                    return api_error["message"]
            return fallback

        def stream_response(response):
            content_parts = []
            reasoning_parts = []

            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue

                line = raw_line.strip()
                if not line.startswith("data: "):
                    continue

                payload_text = line[6:]
                if payload_text == "[DONE]":
                    break

                try:
                    chunk = json.loads(payload_text)
                except json.JSONDecodeError:
                    continue

                choices = chunk.get("choices") or []
                if not choices:
                    continue

                delta = choices[0].get("delta") or {}
                reasoning_piece = delta.get("reasoning_content") or ""
                piece = delta.get("content") or ""
                if reasoning_piece:
                    reasoning_parts.append(reasoning_piece)
                    deliver(chunk_callback, {"content": "", "reasoning_content": reasoning_piece})
                if piece:
                    content_parts.append(piece)
                    deliver(chunk_callback, {"content": piece, "reasoning_content": ""})

            final_content = "".join(content_parts)
            final_reasoning = "".join(reasoning_parts)
            deliver(callback, {"content": final_content, "reasoning_content": final_reasoning})
            deliver(done_callback)

        def non_stream_response(response):
            result = response.json()
            message = result["choices"][0]["message"]
            ai_content = message["content"]
            deliver(callback, {"content": ai_content, "reasoning_content": message.get("reasoning_content", "")})
            deliver(done_callback)

        def task():
            if not self.api_key:
                deliver(error_callback, "请先配置 API Key。")
                return

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = self.build_payload(messages, stream, request_options)
            append_api_request_log(self.url, payload)

            response = None
            try:
                response = self.post_with_recovery(payload, headers, stream)
                response.raise_for_status()

                if stream:
                    stream_response(response)
                else:
                    non_stream_response(response)
            except requests.exceptions.SSLError as exc:
                message = (
                    "TLS 握手失败。已自动重试但仍未成功。"
                    "常见原因：代理或抓包软件拦截、公司网络中间证书、系统时间异常，"
                    "或当前网络对 HTTPS 连接做了中断。"
                    f" 原始错误：{exc}"
                )
                if self.proxy_url:
                    message += f" 当前代理：{self.proxy_url}"
                deliver(error_callback, message)
            except requests.RequestException as exc:
                message = extract_error_message(response, str(exc)) if response is not None else str(exc)
                deliver(error_callback, message)
            except (KeyError, IndexError, TypeError, ValueError):
                deliver(error_callback, "API 返回格式异常。")
            finally:
                if response is not None:
                    response.close()

        thread = threading.Thread(target=task, daemon=True)
        thread.start()
