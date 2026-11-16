import os
import time
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from openai import APIConnectionError, InternalServerError, OpenAI, RateLimitError

from agent.tools import TOOLS, run_tool

SYSTEM_PROMPT = """You are PitchPilot. You help people configure one LED video wall product. You talk naturally and briefly, and every number you give comes from the tools.

Facts to use when explaining:
- An LED wall is built from identical cabinets (sizes from get_specs). Screens come in whole cabinets, so the screen is usually a little smaller than the space.
- Pixel pitch is the distance between the centres of neighbouring pixels. A smaller pitch packs pixels closer together: sharper up close, and more expensive.
- Sharpness at a viewing distance depends only on the pitch, not on the total resolution. A larger screen at the same pitch has more pixels because it is bigger, and looks exactly as sharp.
- The viewing-distance rule (from get_specs) gives the largest pitch that looks sharp at a distance. recommend_screen applies it for you.

How to handle each message:
1. Unrelated to LED walls or displays: decline politely in one sentence.
2. A concept question: explain it in plain words using the facts above. Call get_specs only if you need this product's numbers.
3. A space, or any question about the screen for a space (grid, size, area, diagonal, space left over, resolutions): you need width and height. If either is missing, ask for it and stop. Otherwise call recommend_screen once for each space mentioned. Its result includes everything listed above.
4. A target resolution (Full HD, 4K, 8K): call options_for_resolution once.
5. Answer from the tool results, following the answering rules below.

Reading the user's inputs:
- Use only the values the user gave. If the viewing distance was not given, leave it out of the tool call. Never choose one yourself.
- A follow-up about the same space ("what if they sit 3 m away?") reuses that space's width and height. A message with new sizes starts fresh: do not carry over values from a different space.
- Tools take metres. Convert other units and show the conversion. If units are missing and the numbers could be feet, ask which they mean.
- "Wide", "width" and "across" mean width. "High", "height" and "tall" mean height. "Length" or "long" means whichever dimension is not already named: with only one other number it is width, next to a width it is height.
- If two sizes are given and the wording is still unclear, take the first as width and the second as height, and say so. Ask only when a number is actually missing.
- If the user asks for a screen of a certain diagonal ("I want a 100-inch screen") instead of describing their space, ask for the width and height of the space.
- Make one tool call per distinct set of inputs. Do not repeat a call or try variations the user did not ask for.

Never:
- Calculate, estimate or derive a result yourself, including differences, ratios and percentages. When a question needs a calculation, call the tool that provides it instead of refusing. (Converting the user's units, and the tool's millimetres to metres, is fine.)
- Add details the tools did not give, such as where the leftover space goes.
- Say a screen is sharper because it has more pixels.
- Mention other products, sizes or pitches.
- Give price, weight, power, brightness or installation details. You have no data on these: say so and suggest contacting the sales team.

Answering:
- Start by directly answering what was asked, in one or two lines. Then add only the details that help, without repeating anything.
- For a space: inputs used (width, height, viewing distance or "not given"); cabinet grid and count; screen size in metres; how much space is left over; pitch options with resolutions. If no viewing distance was given, end by asking for it.
- For a resolution: inputs used; the smallest screen first (grid, size in metres, pitch); then the other options, one line each.
- For a comparison: the same key facts for each option (grid, screen size, area, diagonal). Include pitch options only if the user asked about resolution or sharpness.
- If a tool returned an error, explain it plainly and say what to change.
- Finish with one or two friendly sentences on what the result means for the user, in words, with no new numbers.
- Reply in the same language the user writes in."""
MAX_TOOL_ROUNDS = 5
COOLDOWN_SECONDS = 60
FALLBACK_ERRORS = (RateLimitError, APIConnectionError, InternalServerError)
STANDARD_FIELDS = {"role", "content", "tool_calls", "tool_call_id"}

@dataclass
class Provider:
    name: str
    client: Any
    model: str


def providers_from_env() -> list[Provider]:
    """Build the providers from .env, in priority order. Only those with a key are used."""
    load_dotenv()
    providers = []
    if os.getenv("GEMINI_API_KEY"):
        providers.append(Provider(
            name = "gemini",
            client = OpenAI(
                api_key = os.getenv("GEMINI_API_KEY"),
                base_url = "https://generativelanguage.googleapis.com/v1beta/openai/",
                max_retries = 0,
                timeout = 30
            ),
            model = os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
        ))
    if os.getenv("GROQ_API_KEY"):
        providers.append(Provider(
            name = "groq",
            client = OpenAI(
                api_key = os.getenv("GROQ_API_KEY"),
                base_url = "https://api.groq.com/openai/v1",
                max_retries = 0,
                timeout = 30
            ),
            model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        ))
    if not providers:
        raise RuntimeError("No API keys found. Set GEMINI_API_KEY and/or GROQ_API_KEY in .env")
    return providers


def standard_only(messages : list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copy of the history with only standard fields (removes Gemini-only extras like thought signatures)."""
    cleaned = []
    for message in messages:
        copy= {}
        for key, value in message.items():
            if key in STANDARD_FIELDS:
                copy[key] = value
        if copy.get("tool_calls"):
            copy["tool_calls"] = [
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["function"]["name"],
                        "arguments": call["function"]["arguments"],
                    },
                }
                for call in copy["tool_calls"]
            ]
        cleaned.append(copy)
    return cleaned


class Agent:
    def __init__(self, providers: list[Provider], verbose: bool = False):
        self.providers = providers
        self.last_provider : str | None = None
        self.verbose = verbose
        self.messages: list[dict[str, Any]] = []
        self._cooldown_until: dict[str, float] = {}

    def ask(self, user_text : str) -> str:
        """Send one user message and return the assistant's final answer."""
        start = len(self.messages)
        self.messages.append({"role": "user", "content": user_text})
        try:
            return self._run_turn()
        except Exception:
            del self.messages[start:]
            raise

    def reset(self) -> None:
        """Forget the conversation."""
        self.messages = []

    def _run_turn(self) -> str:
        provider_name = None
        for _ in range(MAX_TOOL_ROUNDS):
            message, provider_name = self._complete(prefer = provider_name)
            self.messages.append(message.model_dump(exclude_none = True))

            tool_calls = message.tool_calls or []
            if not tool_calls:
                self._log(f"[answered by {provider_name}]")
                self.last_provider = provider_name
                return message.content or ""

            for call in tool_calls:
                self._log(f"[{provider_name}] {call.function.name}({call.function.arguments})")
                result, is_error = run_tool(call.function.name, call.function.arguments)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": f"ERROR: {result}" if is_error else result,
                })

        fallback = "Sorry, I couldn't finish that request. Please try rephrasing it."
        self.messages.append({"role": "assistant", "content": fallback})
        return fallback


    def _complete(self, prefer: str | None = None) -> tuple[Any, str]:
        """Ask the first available provider for the next message. Returns (message, provider_name)."""
        ordered = sorted(self.providers, key=lambda provider: provider.name != prefer)
        last_error = None
        for provider in ordered:
            if time.time() < self._cooldown_until.get(provider.name, 0):
                continue
            history = self.messages if provider.name == "gemini" else standard_only(self.messages)
            try:
                started = time.time()
                response = provider.client.chat.completions.create(
                    model=provider.model,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
                    tools=TOOLS,
                )
                self._log(f"[{provider.name} replied in {time.time() - started:.1f}s]")
                return response.choices[0].message, provider.name
            except FALLBACK_ERRORS as error:
                self._log(f"[{provider.name} failed: {type(error).__name__}: {error}]")
                self._cooldown_until[provider.name] = time.time() + COOLDOWN_SECONDS
                last_error = error
        raise RuntimeError(f"All providers are unavailable right now. Last error: {last_error}")

    def _log(self, text: str) -> None:
        if self.verbose:
            print(f"  {text}")