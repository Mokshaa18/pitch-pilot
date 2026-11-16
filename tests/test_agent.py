import json
from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError

from agent.agent import Agent, Provider, standard_only
