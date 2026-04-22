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
        if not user_message:
            return jsonify({"error": "Message is required"}), 400

        api_key = os.getenv("API_KEY")
        if not api_key:
            return jsonify({"error": "API_KEY not set — add it to your .env file"}), 500

        client = LLMClient(api_key=api_key)

        # Pass the full user message directly — json_search uses semantic LSA/SVD,
        # so a full natural language question retrieves better than a single keyword
        posts = json_search(user_message)

        context_parts = []
        for i, post in enumerate(posts, 1):
            context_parts.append(
                f"[Post {i}]\n"
                f"Title: {post['title']}\n"
                f"Content: {post.get('descr', '')}\n"
                f"Upvotes: {int(post.get('upvote_score', 0))} | "
                f"Comments: {post.get('num_comments', 0)}"
            )
        context_text = "\n\n".join(context_parts) or "No relevant posts found."

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a relationship advice assistant. You have been given Reddit posts "
                    "relevant to the user's situation.\n\n"
                    "If the user's message is a question or describes a problem, your job is to "
                    "synthesize actionable advice and solutions from the posts — NOT to list or "
                    "describe the posts themselves.\n\n"
                    "Structure your response as:\n"
                    "1. Direct recommendation (1-2 sentences)\n"
                    "2. What people in similar situations actually did or found helpful\n"
                    "3. One concrete next step the user can take\n\n"
                    "If the user is just browsing or not asking a question, give a brief "
                    "helpful summary of what kinds of posts were found.\n\n"
                    "Never say 'Post 1 says' or list posts. Synthesize, don't report."
                ),
            },
            {
                "role": "user",
                "content": f"Relevant posts:\n\n{context_text}\n\nMy situation: {user_message}"
            },
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