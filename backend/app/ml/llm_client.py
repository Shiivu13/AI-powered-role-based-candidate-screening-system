import asyncio
import time
from app.config import settings

# Primary: gemini-3.1-flash-lite (high limit), fallbacks below
GEMINI_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-3.1-flash-lite-preview",
]


class LLMClient:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self._init_client()
        self._current_model_idx = 0

    def _init_client(self):
        if self.provider == "gemini":
            from google import genai
            self._gemini = genai.Client(api_key=settings.GEMINI_API_KEY)
        elif self.provider == "openai":
            from openai import AsyncOpenAI
            self._openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        elif self.provider == "anthropic":
            import anthropic
            self._anthropic = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    async def generate(self, prompt: str, system: str = None) -> str:
        if self.provider == "gemini":
            return await self._generate_gemini(prompt, system)
        elif self.provider == "openai":
            return await self._generate_openai(prompt, system)
        elif self.provider == "anthropic":
            return await self._generate_anthropic(prompt, system)

    async def _generate_gemini(self, prompt: str, system: str = None) -> str:
        from google.genai import types
        from google.genai.errors import ClientError

        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        loop = asyncio.get_event_loop()

        last_error = None
        for attempt in range(len(GEMINI_MODELS)):
            model = GEMINI_MODELS[self._current_model_idx % len(GEMINI_MODELS)]
            try:
                def _call(m=model):
                    response = self._gemini.models.generate_content(
                        model=m,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.7,
                            max_output_tokens=1024,
                        ),
                    )
                    return response.text

                result = await loop.run_in_executor(None, _call)
                return result.strip()

            except ClientError as e:
                last_error = e
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    print(f"[LLM] Quota exceeded for {model}, trying next model...")
                    self._current_model_idx += 1
                    await asyncio.sleep(1)
                else:
                    raise

        raise RuntimeError(f"All Gemini models quota exceeded. Last error: {last_error}")

    async def _generate_openai(self, prompt: str, system: str = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = await self._openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    async def _generate_anthropic(self, prompt: str, system: str = None) -> str:
        kwargs = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        response = await self._anthropic.messages.create(**kwargs)
        return response.content[0].text.strip()


_llm_client: LLMClient = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
