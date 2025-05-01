# Here's the full updated `app.py` with support for:
# - Screenshot analysis via OpenAI
# - Oracle onboarding via Stripe Connect
# - Stripe webhook to track oracle earnings

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

@app.route('/')
def index():
    oracles = {}
    if os.path.exists("oracles.json"):
        with open("oracles.json") as f:
            oracles = json.load(f)
    return render_template('index.html', oracles=oracles)

@app.route('/', methods=['POST'])
def upload_file():
    if 'screenshots' not in request.files:
        return redirect('/')
    
    files = request.files.getlist('screenshots')
    all_text = ""

    for file in files:
        image = Image.open(file.stream)
        text = pytesseract.image_to_string(image)
        all_text += text + "\n\n"

    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a wise and warm oracle, channeling insights from the divine. Speak directly to the user. You are part sage, part therapist, part goddess. They are seeking guidance on their situationship."},
            {"role": "user", "content": all_text}
        ]
    )

    analysis = response.choices[0].message.content
    return render_template('index.html', analysis=analysis, extracted_text=all_text)

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

@app.route("/oracle-success")
def oracle_success():
    return "✨ You're now an Oracle! You can receive payments."

@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({'error': 'Invalid signature'}), 400

    if event['type'] == 'charge.succeeded':
        charge = event['data']['object']
        amount = charge['amount']
        connected_account_id = charge.get('on_behalf_of') or charge.get('destination')

        try:
            with open('oracles.json', 'r') as f:
                oracles = json.load(f)
        except FileNotFoundError:
            oracles = {}

        if connected_account_id:
            if connected_account_id not in oracles:
                oracles[connected_account_id] = {'earned': 0, 'platform_cut': 0}

            oracles[connected_account_id]['earned'] += amount / 100
            oracles[connected_account_id]['platform_cut'] += round((amount / 100) * 0.1, 2)

            with open('oracles.json', 'w') as f:
                json.dump(oracles, f, indent=2)

    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    app.run(debug=True)
