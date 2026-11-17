Pitch Pilot

AI assistant that configures LED video walls from plain-language requests, where every number comes from a tested calculation engine, not the language model

Live demo: https://pitchipilot.streamlit.app/

What is does -
Describe your space in your own words:
My wall is 6m wide and 3.4m high, people sut 1m away.

PitchPilot replies with:
- the cabinet grid that fits(10 * 10 = 100 cabinets)
- the actual screen size, area and diagonal (6.0 * 3.375m, 20.25 m^2, 271)
- how much space is left over
- which pixel pitches are sharp enough at that viewing distance, with their resolutions

It can also:
- work backworks from a resolution: "What's the smallest 4k screen?"
- compare spaces: "Compare a 6 * 3.4m wall with a 4 * 2.5m wall"
- answer follow-ups: "what if I want to increase the length or width?"
- explain concepts: "what is pixel pitch?"
- convert units and ask when information is missing

How it works:
1) The interface passes the user's text to the agent.
2) The agent sends the conversation and a tool menu(JSON Schema) to the LLM.
3) The LLM replies with a tool call, e.g. recommend_screen(width_m = 6, height_m = 3.4, viewing_distance_m = 1).
4) The tool layer validates the request and runs the engine function.
5) The result then goes back to the LLM, which writes the answer.
6) The interface shows it. In the web app, "How this was calculated" lists the tool calls behing each answer.


Tech stack:
Python 3.12, OpenAI Python SDK (OpenAI-compatible APIs), Google Gemini, Groq, Streamlit, pytest, JSON Schema (jsonschema), python-dotenv

Running it locally:
Requirements: Python 3.10+, and a free API key from Google AI Studio and/or Groq. Either one is enough.

In command terminal -
git clone https://github.com/Mokshaa18/pitch-pilot.git
cd pitch-pilot
python -m venv .venv
#windows: .venv\Scripts\activate
#macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

Copy .env.example to .enc and add your key(s):
GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL=gemini-flash-latest
GROQ_API_KEY=your-groq-key
GROQ_MODEL=openai/gpt-oss-120b

Then run the either interface:
python cli.py
stream run app.py

Tests:
python -m pytest