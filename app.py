from flask import Flask, render_template, request
import os

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    profile_url = None
    username = ""
    reason = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip().lstrip("@")
        reason = request.form.get("reason", "").strip()

        if username:
            profile_url = f"https://www.instagram.com/{username}/"

    return render_template(
        "index.html",
        profile_url=profile_url,
        username=username,
        reason=reason
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
