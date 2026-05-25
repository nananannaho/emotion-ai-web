"""
EmotionAI — 딥러닝 감정 인식 & 맞춤형 챗봇 웹 애플리케이션
"""

from __future__ import annotations

import logging
import os
import sys

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from config import ADMIN_USERNAME, DATABASE_URL, IS_CLOUD, SECRET_KEY, USE_LIGHT_ML
from services.database import get_db
from services.auth_service import AuthService
from services.chatbot_service import ChatbotService
from services.emotion_service import EmotionService
from services.mail_service import MailService

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
    mail_service = MailService()
    logger.info("EmotionAI 서비스 초기화 완료 (light_ml=%s)", USE_LIGHT_ML)
except Exception:
    logger.exception("서비스 초기화 실패 — 배포 설정을 확인하세요")
    raise


@app.context_processor
def inject_globals():
    return {
        "is_cloud": IS_CLOUD,
        "use_light_ml": USE_LIGHT_ML,
        "logged_in": bool(session.get("user")),
        "is_admin": bool(session.get("is_admin")),
    }


def _is_admin_session() -> bool:
    return bool(session.get("is_admin")) and session.get("user") == ADMIN_USERNAME


@app.get("/health")
def health():
    from pathlib import Path

    from config import WEIGHTS_DIR

    db = get_db()
    return jsonify({
        "status": "ok",
        "cloud": IS_CLOUD,
        "light_ml": USE_LIGHT_ML,
        "emotion_ml": (WEIGHTS_DIR / "emotion_clf.joblib").exists(),
        "database": db.backend,
        "database_url_set": bool(DATABASE_URL),
        "api_version": 11,
    })


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register")
def register_page():
    return render_template("register.html")


@app.route("/login")
def login_page():
    if _is_admin_session():
        return redirect(url_for("admin_page"))
    return render_template("login.html")


@app.route("/forgot-password")
def forgot_password_page():
    return render_template("forgot_password.html")


@app.route("/reset-password")
def reset_password_page():
    selector = (request.args.get("selector") or "").strip()
    token = (request.args.get("token") or "").strip()
    verify = auth_service.verify_password_reset_token(selector, token)
    return render_template(
        "reset_password.html",
        selector=selector,
        token=token,
        token_valid=bool(verify.get("success")),
        token_error=verify.get("error", ""),
    )


@app.route("/dashboard")
def dashboard():
    if not session.get("user"):
        return render_template("login.html", error="로그인이 필요합니다.")
    if _is_admin_session():
        return redirect(url_for("admin_page"))
    return render_template("dashboard.html", user=session["user"], app_nav=True)


@app.route("/admin")
def admin_page():
    if not _is_admin_session():
        return render_template("login.html", error="관리자 로그인이 필요합니다.")
    users = auth_service.get_admin_users(limit=300)
    return render_template(
        "admin.html",
        user=session["user"],
        users=users,
        total_users=len(users),
    )


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
            email=(data.get("email") or "").strip(),
            password=data.get("password") or "",
            display_name=(data.get("display_name") or "").strip(),
            preferences=data.get("preferences"),
            face_image_bgr=image,
        )
        if result.get("success"):
            session.clear()
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
        session.clear()
        session["user"] = result["profile"]["username"]
        if result.get("is_admin"):
            session["is_admin"] = True
    status = 200 if result.get("success") else 401
    return jsonify(result), status


@app.post("/api/login/face")
def api_login_face():
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        return jsonify({
            "success": False,
            "error": "요청 데이터가 너무 큽니다. 사진을 다시 선택해 주세요.",
        }), 413

    try:
        image = emotion_service.decode_image(data.get("face_image", ""))
        if image is None:
            return jsonify({"success": False, "error": "얼굴 이미지가 필요합니다."}), 400

        result = auth_service.login_face(
            username=(data.get("username") or "").strip(),
            face_image_bgr=image,
        )
        if result.get("success"):
            session.clear()
            session["user"] = result["profile"]["username"]
        status = 200 if result.get("success") else 401
        return jsonify(result), status
    except Exception as exc:
        logger.exception("얼굴 로그인 API 오류: %s", exc)
        return jsonify({
            "success": False,
            "error": "로그인 처리 중 서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        }), 500


@app.post("/api/password-reset/request")
def api_password_reset_request():
    if not mail_service.configured:
        return jsonify({
            "success": False,
            "error": "비밀번호 재설정 메일 기능이 아직 설정되지 않았습니다.",
        }), 503

    data = request.get_json(silent=True) or {}
    result = auth_service.request_password_reset(data.get("email") or "")
    if not result.get("success"):
        return jsonify(result), 400

    try:
        if result.get("email_sent"):
            reset_url = url_for(
                "reset_password_page",
                selector=result["selector"],
                token=result["token"],
                _external=True,
            )
            mail_service.send_password_reset_email(
                to_email=result["email"],
                display_name=result["display_name"],
                reset_url=reset_url,
                reset_code=result["reset_code"],
            )
    except Exception as exc:
        logger.exception("비밀번호 재설정 메일 발송 실패: %s", exc)
        return jsonify({
            "success": False,
            "error": "비밀번호 재설정 메일을 보내지 못했습니다. 잠시 후 다시 시도해 주세요.",
        }), 500

    return jsonify({
        "success": True,
        "message": "입력한 이메일로 재설정 링크를 보냈습니다. 계정이 없다면 메일이 오지 않을 수 있습니다.",
    })


@app.post("/api/password-reset/confirm")
def api_password_reset_confirm():
    data = request.get_json(silent=True) or {}
    result = auth_service.reset_password(
        selector=data.get("selector") or "",
        token=data.get("token") or "",
        new_password=data.get("password") or "",
    )
    status = 200 if result.get("success") else 400
    return jsonify(result), status


@app.post("/api/password-reset/confirm-code")
def api_password_reset_confirm_code():
    data = request.get_json(silent=True) or {}
    result = auth_service.reset_password_with_code(
        email=data.get("email") or "",
        code=data.get("code") or "",
        new_password=data.get("password") or "",
    )
    status = 200 if result.get("success") else 400
    return jsonify(result), status


@app.post("/api/emotion/analyze")
def api_analyze_emotion():
    if _is_admin_session():
        return jsonify({"success": False, "error": "관리자 계정에서는 표정 분석을 사용할 수 없습니다."}), 403
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
    if _is_admin_session():
        return jsonify({"success": False, "error": "관리자 계정에서는 챗봇을 사용할 수 없습니다."}), 403

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
    return jsonify({"logged_in": True, "is_admin": _is_admin_session(), "profile": profile})


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify({"success": True})


@app.post("/api/account/delete")
def api_delete_account():
    if not session.get("user"):
        return jsonify({"success": False, "error": "로그인이 필요합니다."}), 401
    if _is_admin_session():
        return jsonify({"success": False, "error": "관리자 계정은 삭제할 수 없습니다."}), 403

    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    username = session["user"]

    result = auth_service.delete_account(username, password)
    if result.get("success"):
        session.clear()
    status = 200 if result.get("success") else 400
    return jsonify(result), status


@app.post("/api/admin/users/delete")
def api_admin_delete_user():
    if not _is_admin_session():
        return jsonify({"success": False, "error": "관리자 로그인이 필요합니다."}), 403

    data = request.get_json(silent=True) or {}
    result = auth_service.admin_delete_user(data.get("username") or "")
    status = 200 if result.get("success") else 400
    return jsonify(result), status


@app.post("/api/face/update")
def api_update_face():
    if not session.get("user"):
        return jsonify({"success": False, "error": "로그인이 필요합니다."}), 401
    if _is_admin_session():
        return jsonify({"success": False, "error": "관리자 계정은 얼굴 재등록을 사용할 수 없습니다."}), 403
    data = request.get_json(silent=True) or {}
    image = emotion_service.decode_image(data.get("face_image", ""))
    if image is None:
        return jsonify({"success": False, "error": "얼굴 이미지가 필요합니다."}), 400
    result = auth_service.update_face(session["user"], image)
    status = 200 if result.get("success") else 400
    return jsonify(result), status


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
