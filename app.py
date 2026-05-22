"""
EmotionAI — 딥러닝 감정 인식 & 맞춤형 챗봇 웹 애플리케이션
"""

from __future__ import annotations

import logging
import os
import sys

from flask import Flask, jsonify, render_template, request, session
from werkzeug.middleware.proxy_fix import ProxyFix

from config import DATABASE_URL, IS_CLOUD, SECRET_KEY, USE_LIGHT_ML
from services.database import get_db
from services.auth_service import AuthService
from services.chatbot_service import ChatbotService
from services.emotion_service import EmotionService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["JSON_AS_ASCII"] = False

if IS_CLOUD:
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

try:
    get_db()
    auth_service = AuthService()
    emotion_service = EmotionService()
    chatbot_service = ChatbotService()
    logger.info("EmotionAI 서비스 초기화 완료 (light_ml=%s)", USE_LIGHT_ML)
except Exception:
    logger.exception("서비스 초기화 실패 — 배포 설정을 확인하세요")
    raise


@app.context_processor
def inject_globals():
    return {
        "is_cloud": IS_CLOUD,
        "use_light_ml": USE_LIGHT_ML,
    }


@app.get("/health")
def health():
    db = get_db()
    return jsonify({
        "status": "ok",
        "cloud": IS_CLOUD,
        "light_ml": USE_LIGHT_ML,
        "database": db.backend,
        "database_url_set": bool(DATABASE_URL),
        "api_version": 2,
    })


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register")
def register_page():
    return render_template("register.html")


@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if not session.get("user"):
        return render_template("login.html", error="로그인이 필요합니다.")
    return render_template("dashboard.html", user=session["user"])


@app.post("/api/register")
def api_register():
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        return jsonify({"success": False, "error": "요청 데이터가 너무 큽니다. 사진을 다시 선택해 주세요."}), 413

    try:
        image = emotion_service.decode_image(data.get("face_image", ""))
        if image is None:
            return jsonify({"success": False, "error": "얼굴 이미지가 필요합니다."}), 400

        result = auth_service.register(
            username=(data.get("username") or "").strip(),
            password=data.get("password") or "",
            display_name=(data.get("display_name") or "").strip(),
            preferences=data.get("preferences"),
            face_image_bgr=image,
        )
        if result.get("success"):
            session["user"] = result["username"]
        status = 200 if result.get("success") else 400
        return jsonify(result), status
    except Exception as exc:
        logger.exception("회원가입 처리 오류: %s", exc)
        return jsonify({
            "success": False,
            "error": "가입 처리 중 서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        }), 500


@app.errorhandler(500)
def handle_500(err):
    if request.path.startswith("/api/"):
        logger.exception("API 500: %s", err)
        return jsonify({
            "success": False,
            "error": "서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        }), 500
    return "서버 오류가 발생했습니다.", 500


@app.post("/api/login/password")
def api_login_password():
    data = request.get_json(silent=True) or {}
    result = auth_service.login_password(
        username=(data.get("username") or "").strip(),
        password=data.get("password") or "",
    )
    if result.get("success"):
        session["user"] = result["profile"]["username"]
    status = 200 if result.get("success") else 401
    return jsonify(result), status


@app.post("/api/login/face")
def api_login_face():
    data = request.get_json(silent=True) or {}
    image = emotion_service.decode_image(data.get("face_image", ""))
    if image is None:
        return jsonify({"success": False, "error": "얼굴 이미지가 필요합니다."}), 400

    result = auth_service.login_face(image)
    if result.get("success"):
        session["user"] = result["profile"]["username"]
    status = 200 if result.get("success") else 401
    return jsonify(result), status


@app.post("/api/emotion/analyze")
def api_analyze_emotion():
    data = request.get_json(silent=True) or {}
    image = emotion_service.decode_image(data.get("image", ""))
    if image is None:
        return jsonify({"success": False, "error": "이미지를 처리할 수 없습니다."}), 400

    # 로그인한 본인 계정에만 감정·대화 이력 저장 (다른 사용자 데이터와 분리)
    username = session.get("user")
    result = emotion_service.analyze_frame(
        image, username=username, message=data.get("message", "")
    )
    status = 200 if result.get("success") else 400
    return jsonify(result), status


@app.post("/api/chat")
def api_chat():
    if not session.get("user"):
        return jsonify({"success": False, "error": "로그인이 필요합니다."}), 401

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    fused_emotion = data.get("fused_emotion", "neutral")
    situation = data.get("situation", "general_support")

    profile = auth_service.get_profile(session["user"]) or {}
    chat_history = auth_service.get_chat_history(session["user"])

    response = chatbot_service.generate(
        user_message=message,
        fused_emotion=fused_emotion,
        situation=situation,
        display_name=profile.get("display_name", session["user"]),
        chat_history=chat_history,
    )

    auth_service.append_chat(session["user"], "user", message)
    auth_service.append_chat(session["user"], "assistant", response["reply"])

    return jsonify({"success": True, **response})


@app.get("/api/session")
def api_session():
    user = session.get("user")
    if not user:
        return jsonify({"logged_in": False})
    profile = auth_service.get_profile(user)
    return jsonify({"logged_in": True, "profile": profile})


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify({"success": True})


def _lan_ip() -> str | None:
    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


if __name__ == "__main__":
    port = 5000
    lan = _lan_ip()
    print("\n" + "=" * 50)
    print("  PC 브라우저:  http://127.0.0.1:%s" % port)
    if lan:
        print("  모바일 접속: http://%s:%s" % (lan, port))
        print("  (휴대폰과 PC가 같은 Wi-Fi에 연결되어 있어야 합니다)")
    print("  이 터미널 창을 닫으면 접속이 끊깁니다.")
    print("=" * 50 + "\n")
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
