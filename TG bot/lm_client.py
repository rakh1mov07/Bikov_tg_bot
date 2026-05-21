import aiohttp
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class LMStudioClient:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.endpoint = f"{self.base_url}/v1/chat/completions"

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        temperature: float = 0.9,
        max_tokens: int = 350,
    ) -> str:
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "repeat_penalty": 1.3,  # не повторять одни и те же фразы
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"LM Studio error {resp.status}: {error_text}")
                        raise ConnectionError(f"LM Studio вернул статус {resp.status}")

                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return content.strip()

        except aiohttp.ClientConnectorError:
            raise ConnectionError(f"Нет соединения с {self.base_url}")
        except asyncio.TimeoutError:
            raise ConnectionError("Таймаут — LM Studio не ответил за 120 сек")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise ValueError(f"Неожиданный ответ от LM Studio: {e}")
