"""
LLM chat route — only loaded when USE_LLM = True in routes.py.
Adds a POST /api/chat endpoint that performs LLM-driven RAG for relationship advice.

Setup:
  1. Add API_KEY=your_key to .env
  2. Set USE_LLM = True in routes.py
"""
import json
import os
import logging
from flask import request, jsonify, Response, stream_with_context
from infosci_spark_client import LLMClient

logger = logging.getLogger(__name__)

def register_chat_route(app, json_search):
    """Register the /api/chat SSE endpoint. Called from routes.py."""

    @app.route("/api/chat", methods=["POST"])
    def chat():
        data = request.get_json() or {}
        user_message = (data.get("message") or "").strip()
        raw_filters = data.get("filters") or {}
        
        # Ensure all required keys exist and cast types to match json_search expectations
        filters = {
            "tag_ids": raw_filters.get("tag_ids", []),
            "tag_mode": raw_filters.get("tag_mode", "boost"),
            "safe_mode": raw_filters.get("safe_mode", False),
            "extra_block_words": set(raw_filters.get("extra_block_words", [])),
        }
        
        if not user_message:
            return jsonify({"error": "Message is required"}), 400

        api_key = os.getenv("API_KEY")
        if not api_key:
            return jsonify({"error": "API_KEY not set — add it to your .env file"}), 500

        client = LLMClient(api_key=api_key)

        # Retrieve IR results
        episodes = json_search(user_message, filters=filters)
        
        # Build context from the top 5 results to avoid context overflow, although the model can probably handle 10. Let's use 5 for focus.
        context_text = "\n\n---\n\n".join(
            f"Title: {ep['title']}\nSnippet: {ep['descr']}"
            for ep in episodes[:5]
        ) or "No matching advice posts found."

        system_prompt = (
            "You are an empathetic and helpful relationship advice assistant. "
            "You are provided with snippets of relationship advice posts similar to the user's situation. "
            "Your task is to summarize how other people dealt with their problems, based strictly on the provided context. "
            "Reference the different situations where relevant to help the user understand the patterns, but do not hallucinate outside the text."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context posts:\n\n{context_text}\n\nUser's problem: {user_message}"},
        ]

        def generate():
            try:
                for chunk in client.chat(messages, stream=True):
                    if chunk.get("content"):
                        yield f"data: {json.dumps({'content': chunk['content']})}\n\n"
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'error': 'Streaming error occurred'})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
