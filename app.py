import os
import io
from flask import Flask, request, render_template, redirect
from PIL import Image
import pytesseract
import openai
import stripe

app = Flask(__name__)

# Load API keys from environment variables
openai.api_key = os.environ.get("OPENAI_API_KEY")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        files = request.files.getlist("screenshot")
        all_text = []

        for file in files:
            image = Image.open(file.stream)
            extracted_text = pytesseract.image_to_string(image)
            all_text.append(extracted_text.strip())

        full_text = "\n---\n".join(all_text)

        prompt = (
            "You are the Oracle of Delphi, crossed with Esther Perel and Brené Brown. "
            "Your role is to receive confusing screenshots of modern texting situationships, "
            "and help the user understand the emotional truth of what’s going on. "
            "Address the user directly as 'you', speak with mystical, wise tone, and do not reference the fact this is AI.\n\n"
            f"Here is the message(s):\n{full_text}\n\n"
            "What is going on in the heart and mind of the person texting? What do you want the user to know?"
        )

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a wise oracle who gives insight into relationship dynamics."},
                {"role": "user", "content": prompt}
            ]
        )

        analysis = response.choices[0].message.content.strip()

        return render_template("index.html", analysis=analysis, extracted_text=full_text)

    return render_template("index.html")

# === ORACLE ONBOARDING ===
@app.route("/onboard-oracle")
def onboard_oracle():
    account = stripe.Account.create(type="express")

    account_link = stripe.AccountLink.create(
        account=account.id,
        refresh_url="https://situationship-analyzer-web.onrender.com/onboard-oracle",
        return_url="https://situationship-analyzer-web.onrender.com/oracle-success",
        type="account_onboarding",
    )

    return redirect(account_link.url)

@app.route("/oracle-success")
def oracle_success():
    return "🎉 You're now an Oracle! You can receive payments."

if __name__ == "__main__":
    app.run(debug=True)
