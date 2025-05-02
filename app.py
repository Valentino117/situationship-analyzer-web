from flask import Flask, request, render_template, redirect
import openai
import stripe
import base64
import os
import json

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

@app.route('/')
def index():
    oracles = {}
    if os.path.exists("oracles.json"):
        with open("oracles.json") as f:
            oracles = json.load(f)
    return render_template("index.html", oracles=oracles)

@app.route("/create-oracle-account")
def create_oracle_account():
    account = stripe.Account.create(type="express", capabilities={"transfers": {"requested": True}})
    link = stripe.AccountLink.create(
        account=account.id,
        refresh_url="https://situationship-analyzer-web.onrender.com/",
        return_url=f"https://situationship-analyzer-web.onrender.com/oracle-success?account_id={account.id}",
        type="account_onboarding"
    )
    return redirect(link.url)

@app.route("/oracle-success")
def oracle_success():
    account_id = request.args.get("account_id")
    return render_template("oracle_success.html", account_id=account_id)

@app.route("/oracle-dashboard")
def oracle_dashboard():
    account_id = request.args.get("account_id")
    return render_template("oracle_dashboard.html", account_id=account_id)

@app.route("/oracle-analysis", methods=["POST"])
def oracle_analysis():
    file = request.files["screenshot"]
    account_id = request.form["account_id"]
    image_data = base64.b64encode(file.read()).decode("utf-8")

    response = openai.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=[
            {"role": "system", "content": "You are a mystical oracle analyzing screenshots of text messages for romantic subtext. Offer wise, tender, and honest insights to the user who wants to understand what’s really going on."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Please analyze this screenshot of a situationship conversation."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}}
                ]
            }
        ],
        max_tokens=800
    )

    analysis = response.choices[0].message.content
    return render_template("oracle_dashboard.html", analysis=analysis, account_id=account_id)

@app.route("/generate-payment-link", methods=["POST"])
def generate_payment_link():
    account_id = request.form["account_id"]
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": "Situationship Reading"},
                "unit_amount": 100,  # $1.00
            },
            "quantity": 1,
        }],
        payment_intent_data={
            "application_fee_amount": 10,  # $0.10 fee
            "transfer_data": {
                "destination": account_id,
            },
            "on_behalf_of": account_id
        },
        mode="payment",
        success_url="https://situationship-analyzer-web.onrender.com",
    )
    return render_template("oracle_dashboard.html", payment_link=session.url, account_id=account_id)

@app.route("/webhook", methods=["POST"])
def webhook_received():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception as e:
        return str(e), 400

    if event["type"] == "charge.succeeded":
        charge = event["data"]["object"]
        connected_id = charge.get("on_behalf_of") or charge.get("destination")
        amount = charge["amount"]

        try:
            acct = stripe.Account.retrieve(connected_id)
            name = acct.get("business_profile", {}).get("name", "") or acct.get("email", "") or connected_id
        except:
            name = connected_id

        try:
            with open("oracles.json", "r") as f:
                oracles = json.load(f)
        except FileNotFoundError:
            oracles = {}

        if connected_id not in oracles:
            oracles[connected_id] = {"name": name, "earned": 0, "platform_cut": 0}

        oracles[connected_id]["earned"] += amount / 100
        oracles[connected_id]["platform_cut"] += round((amount / 100) * 0.1, 2)

        with open("oracles.json", "w") as f:
            json.dump(oracles, f, indent=2)

    return "", 200

if __name__ == "__main__":
    app.run(debug=True)
