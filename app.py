import logging
import os

from flask import Flask, jsonify, request

from config import PORT
from scraper.exceptions import ScraperError
from scraper.services.profile_service import LinkedInProfileService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

ERROR_STATUS = {
    "CREDENTIALS_NOT_CONFIGURED": 503,
    "INVALID_URL": 400,
    "LOGIN_FAILED": 503,
    "LOGIN_VERIFICATION_REQUIRED": 503,
    "SESSION_EXPIRED": 503,
    "SESSION_ERROR": 503,
    "PROFILE_NOT_FOUND": 404,
    "SCRAPER_ERROR": 500,
}


@app.route("/health", methods=["GET"])
def health():
    return jsonify(LinkedInProfileService.health())


@app.route("/profile", methods=["POST"])
def profile():
    body = request.get_json(silent=True) or {}
    url = body.get("url") or body.get("profile_url")

    if not url or not str(url).strip():
        return jsonify(
            {
                "success": False,
                "error": "Missing profile URL. Provide 'url' in the JSON request body.",
                "code": "MISSING_URL",
            }
        ), 400

    try:
        result = LinkedInProfileService.scrape(str(url).strip())
        return jsonify(result)
    except ScraperError as exc:
        status = ERROR_STATUS.get(exc.code, 500)
        return jsonify({"success": False, "error": str(exc), "code": exc.code}), status
    except Exception as exc:
        logger.exception("Unexpected error scraping profile")
        return jsonify(
            {"success": False, "error": str(exc), "code": "INTERNAL_ERROR"}
        ), 500


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=PORT, debug=debug, threaded=False)
