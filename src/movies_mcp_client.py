"""
movies_gradio_client.py

Gradio chatbot UI backed by a Strands agent connected to the Movies MCP server.
Model: OpenRouter via LiteLLM (OpenAI-compatible endpoint).

Environment variables:
    OPENROUTER_API_KEY      - your OpenRouter API key (required)
    OPENROUTER_MODEL        - model slug (default: openai/gpt-4o)
    MOVIES_API_BASE_URL     - Movies FastAPI base URL (default: http://localhost:8080)
"""

import os
import sys
import httpx
import gradio as gr
from strands import Agent
from strands.models.litellm import LiteLLMModel


from mcp.client.streamable_http import streamable_http_client

from strands.tools.mcp import MCPClient

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger()


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL   = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")
MOVIES_API_BASE    = os.getenv("MOVIES_API_BASE_URL", "http://localhost:8080")

if not OPENROUTER_API_KEY:
    logger.error("OPENROUTER_API_KEY environment variable is not set.")
    sys.exit(1)

SYSTEM_PROMPT = """
You are a helpful movie assistant. You have access to a movies database with
thousands of films. You can search movies by title, genre, keyword, actor,
spoken language, and release date.

When a user asks about movies:
1. Use the available tools to fetch accurate data.
2. Present results in a clear, readable format using markdown tables or bullet lists.
3. If asked for recommendations, use search_movies with relevant filters.
4. Always include movie title, release year, and rating in summaries.
5. If a user asks for details about a specific movie, use get_movie_details.
"""

def _check_api_health():
    try:
        r = httpx.get(f"{MOVIES_API_BASE}/genres", timeout=5)
        r.raise_for_status()
        logger.info(f"Movies API reachable at {MOVIES_API_BASE}")
    except Exception as e:
        logger.error(f"Movies API not reachable at {MOVIES_API_BASE}: {e}")
        logger.info("    Start it with: uvicorn movies_api:app --port 8080")
        sys.exit(1)



def _build_model() -> LiteLLMModel:
    """
    LiteLLMModel routes requests to OpenRouter's OpenAI-compatible endpoint.
    Model slug format:  openrouter/<provider>/<model-name>
    e.g.  openrouter/openai/gpt-4o
          openrouter/anthropic/claude-3.5-sonnet
          openrouter/google/gemini-2.0-flash-001
    """
    # LiteLLM expects the prefix "openrouter/" to route to OpenRouter
    litellm_model_id = (
        OPENROUTER_MODEL
        if OPENROUTER_MODEL.startswith("openrouter/")
        else f"openrouter/{OPENROUTER_MODEL}"
    )
    return LiteLLMModel(
        model_id=litellm_model_id,
        params={
            "api_key": OPENROUTER_API_KEY,
            "api_base": "https://openrouter.ai/api/v1",
            "extra_headers": {
                "HTTP-Referer": "http://localhost:7860",
                "X-Title": "Movies AI Assistant",
            },
            "temperature": 0.1,
            "max_tokens": 4096,
        },
    )


def build_agent() -> tuple[Agent, MCPClient]:
    streamable_http_mcp_client = MCPClient(
        lambda: streamable_http_client("http://localhost:8000/mcp")
    )

    agent = Agent(
        model=_build_model(),
        tools=[streamable_http_mcp_client],
        system_prompt=SYSTEM_PROMPT,
    )
    return agent, streamable_http_mcp_client


_check_api_health()
agent, mcp_client = build_agent()
logger.info(f"Strands agent ready — model: {OPENROUTER_MODEL}")


def chat(user_message: str, history: list[dict]) -> tuple[str, list[dict]]:
    if not user_message.strip():
        return "", history

    conversation = "\n".join(
        f"{msg['role'].capitalize()}: {msg['content']}" for msg in history
    )
    full_prompt = f"{conversation}\nUser: {user_message}" if conversation else user_message

    try:
        response = agent(full_prompt)
        assistant_reply = str(response)
    except Exception as e:
        assistant_reply = f"Error: {e}"

    history.append({"role": "user",      "content": user_message})
    history.append({"role": "assistant", "content": assistant_reply})
    return "", history


with gr.Blocks(title="Movies AI Assistant", theme=gr.themes.Soft()) as demo:

    gr.Markdown(
        f"""        # 🎬 Movies AI Assistant        
        Powered by **{OPENROUTER_MODEL}** via OpenRouter.        **Example questions:**        - *Show me top Action movies*        - *Find sci-fi movies with James Cameron*        - *List movies in Spanish released after 2010*        - *Tell me everything about Avatar (movie id 19995)*        - *What genres are available?*        """
    )

    chatbot = gr.Chatbot(
        label="Movies Assistant",
        height=600,
        avatar_images=("🧑", "🎬"),
    )

    with gr.Row():
        user_input = gr.Textbox(
            placeholder="Ask about movies...",
            label="Your question",
            scale=9,
            autofocus=True,
        )
        send_btn = gr.Button("Send 🚀", scale=1, variant="primary")

    clear_btn = gr.Button("🗑️ Clear chat", variant="secondary")

    with gr.Accordion("🔍 Quick search filters", open=False):
        with gr.Row():
            qf_genre    = gr.Textbox(label="Genre",    placeholder="e.g. Action")
            qf_actor    = gr.Textbox(label="Actor",    placeholder="e.g. Tom Hanks")
            qf_language = gr.Textbox(label="Language", placeholder="e.g. en")
        with gr.Row():
            qf_date_from = gr.Textbox(label="Release from", placeholder="YYYY-MM-DD")
            qf_date_to   = gr.Textbox(label="Release to",   placeholder="YYYY-MM-DD")
            qf_keyword   = gr.Textbox(label="Keyword",      placeholder="e.g. space war")
        quick_search_btn = gr.Button("🔎 Search", variant="primary")

    history_state = gr.State([])

    def quick_search(genre, actor, language, date_from, date_to, keyword, history):
        parts = []
        if genre:    parts.append(f"genre '{genre}'")
        if actor:    parts.append(f"actor '{actor}'")
        if language: parts.append(f"language '{language}'")
        if keyword:  parts.append(f"keyword '{keyword}'")
        if date_from or date_to:
            parts.append(f"released between {date_from or '?'} and {date_to or '?'}")
        query = ("Find movies matching: " + ", ".join(parts) + ". Show top results.") if parts \
                else "Show me the top 10 most popular movies."
        return chat(query, history)

    send_btn.click(fn=chat, inputs=[user_input, history_state], outputs=[user_input, history_state])\
            .then(fn=lambda h: h, inputs=[history_state], outputs=[chatbot])

    user_input.submit(fn=chat, inputs=[user_input, history_state], outputs=[user_input, history_state])\
              .then(fn=lambda h: h, inputs=[history_state], outputs=[chatbot])

    quick_search_btn.click(
        fn=quick_search,
        inputs=[qf_genre, qf_actor, qf_language, qf_date_from, qf_date_to, qf_keyword, history_state],
        outputs=[user_input, history_state],
    ).then(fn=lambda h: h, inputs=[history_state], outputs=[chatbot])

    clear_btn.click(fn=lambda: ([], []), outputs=[chatbot, history_state])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)