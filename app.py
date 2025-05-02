from flask import Flask, render_template, request, redirect, jsonify, url_for
from PIL import Image
import openai
import stripe
import os
import json
from io import BytesIO

app = Flask(__name__)

openai.api_key = os.getenv("OPENAI_API_KEY")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

ORACLES_JSON = "oracles.json"

# Helper to load oracles
def load_oracles():
    if os.path.exists(ORACLES_JSON):
        with open(ORACLES_JSON) as f:
            return json.load(f)
    return {}

# Home
@app.route('/')
def index():
    return render_template('index.html')

# Create Stripe Express account
@app.route('/create-oracle-account')
def create_oracle_account():
    account = stripe.Account.create(
        type="express",
        capabilities={"transfers": {"requested": True}}
    )
    account_link = stripe.AccountLink.create(
        account=account.id,
        refresh_url=url_for('index', _external=True),
        return_url=url_for('oracle_success', _external=True),
        type="account_onboarding"
    )
    return redirect(account_link.url)

# Confirm onboarding complete
@app.route('/oracle-success')
def oracle_success():
    return render_template('oracle_success.html')

# Oracle dashboard
@app.route('/oracle-dashboard', methods=['POST'])
def oracle_dashboard():
    account_id = request.form.get('account_id')
    if not account_id:
        return redirect('/')
    
    oracles = load_oracles()
    oracle_data = oracles.get(account_id, {"earned": 0, "platform_cut": 0})
    return render_template('oracle_dashboard.html', oracle_id=account_id, oracle_data=oracle_data)

# Payment link generation
@app.route('/generate-payment-link/<oracle_id>', methods=['POST'])
def generate_payment_link(oracle_id):
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "unit_amount": 100,  # $1
                "product_data": {"name": "Situationship Analysis"}
            },
            "quantity": 1
        }],
        mode="payment",
        success_url=url_for('index', _external=True),
        cancel_url=url_for('index', _external=True),
        payment_intent_data={
            "transfer_data": {
                "destination": oracle_id
            },
            "application_fee_amount": 10  # 10¢ to platform
        }
    )
    return jsonify({"url": session.url})

# Oracle analysis
@app.route('/oracle-analysis', methods=['POST'])
def oracle_analysis():
    screenshots = request.files.getlist("screenshots")
    if not screenshots:
        return "No screenshots provided", 400

    combined_text = ""
    for shot in screenshots:
        image_bytes = shot.read()
        response = openai.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {"role": "system", "content": "You are a wise oracle helping someone decode text messages from their situationship. Give compassionate and clear advice in human language."},
                {"role": "user", "content": [
                    {"type": "text", "text": "Please analyze this screenshot for emotional tone and relational insight."},
                    {"type": "image_url", "image_url": {"image": f"data:image/png;base64,{image_bytes.encode('base64').decode()}", "detail": "high"}}
                ]}
            ],
            max_tokens=500
        )
        combined_text += response.choices[0].message.content + "\n\n"

    return render_template('oracle_analysis.html', analysis=combined_text)

# Stripe webhook
@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception:
        return jsonify({"error": "Webhook validation failed"}), 400

    if event["type"] == "charge.succeeded":
        charge = event["data"]["object"]
        connected_account_id = charge.get("transfer_data", {}).get("destination")
        amount = charge["amount"]

        if connected_account_id:
            oracles = load_oracles()
            if connected_account_id not in oracles:
                oracles[connected_account_id] = {"earned": 0, "platform_cut": 0}
            oracles[connected_account_id]["earned"] += amount / 100
            oracles[connected_account_id]["platform_cut"] += round((amount / 100) * 0.1, 2)

            with open(ORACLES_JSON, "w") as f:
                json.dump(oracles, f, indent=2)

    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    app.run(debug=True)
