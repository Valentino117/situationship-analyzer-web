from flask import Flask, render_template, request, redirect, jsonify
from PIL import Image
import pytesseract
import openai
import stripe
import os
import json

app = Flask(__name__)

openai.api_key = os.getenv("OPENAI_API_KEY")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

# Load oracles from file
def load_oracles():
    if os.path.exists("oracles.json"):
        with open("oracles.json") as f:
            return json.load(f)
    return {}

# Save oracles to file
def save_oracles(data):
    with open("oracles.json", "w") as f:
        json.dump(data, f, indent=2)

@app.route('/')
def index():
    oracles = load_oracles()
    return render_template('index.html', oracles=oracles)

@app.route('/create-oracle-account')
def create_oracle_account():
    account = stripe.Account.create(
        type="express",
        capabilities={"transfers": {"requested": True}}
    )
    account_link = stripe.AccountLink.create(
        account=account.id,
        refresh_url="https://situationship-analyzer-web.onrender.com",
        return_url="https://situationship-analyzer-web.onrender.com/oracle-success",
        type="account_onboarding"
    )
    return redirect(account_link.url)

@app.route('/oracle-success')
def oracle_success():
    return render_template("oracle_success.html")

@app.route('/oracle-dashboard')
def oracle_dashboard():
    account_id = request.args.get("account_id")
    if not account_id:
        return redirect("/")
    return render_template("oracle_analysis.html", account_id=account_id)

@app.route('/oracle-analysis', methods=['GET', 'POST'])
def oracle_analysis():
    if request.method == 'GET':
        return redirect('/')

    account_id = request.form.get("account_id")
    screenshot = request.files.get("screenshot")
    if not screenshot:
        return redirect("/")

    image = Image.open(screenshot.stream)
    text = pytesseract.image_to_string(image)

    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a wise and warm oracle, channeling insights from the divine. Speak directly to the user. You are part sage, part therapist, part goddess. They are seeking guidance on their friend’s situationship."},
            {"role": "user", "content": text}
        ]
    )
    analysis = response.choices[0].message.content

    # Create a Payment Link with application_fee
    price = stripe.Price.create(
        unit_amount=100,  # $1.00
        currency="usd",
        product_data={"name": "Situationship Reading"}
    )
    link = stripe.PaymentLink.create(
        line_items=[{"price": price.id, "quantity": 1}],
        application_fee_amount=10,  # $0.10 fee for platform
        after_completion={"type": "redirect", "redirect": {"url": "https://situationship-analyzer-web.onrender.com"}},
        transfer_data={"destination": account_id}
    )

    return render_template("oracle_analysis.html", analysis=analysis, payment_link=link.url, account_id=account_id)

@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return jsonify({'error': 'Invalid signature'}), 400

    if event['type'] == 'charge.succeeded':
        charge = event['data']['object']
        amount = charge['amount'] / 100
        account_id = charge.get('transfer_data', {}).get('destination')

        if account_id:
            oracles = load_oracles()

            # Try to retrieve Stripe account info for name
            try:
                stripe_account = stripe.Account.retrieve(account_id)
                name = stripe_account.get("individual", {}).get("first_name", "") + " " + stripe_account.get("individual", {}).get("last_name", "")
                name = name.strip() or f"Oracle {account_id[-6:]}"
            except Exception:
                name = f"Oracle {account_id[-6:]}"

            if account_id not in oracles:
                oracles[account_id] = {'name': name, 'earned': 0, 'platform_cut': 0}

            oracles[account_id]['earned'] += round(amount, 2)
            oracles[account_id]['platform_cut'] += round(amount * 0.1, 2)

            save_oracles(oracles)

    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    app.run(debug=True)
