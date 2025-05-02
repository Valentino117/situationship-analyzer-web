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
    return render_template("oracle_success.html")

@app.route('/oracle-analysis', methods=['GET', 'POST'])
def oracle_analysis():
    if request.method == 'POST':
        screenshot = request.files['screenshot']
        oracle_id = request.form['oracle_id']

        image = Image.open(screenshot.stream)
        text = pytesseract.image_to_string(image)

        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a wise oracle. Give your insight about this relationship situation."},
                {"role": "user", "content": text}
            ]
        )

        analysis = response.choices[0].message.content

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "Situationship Reading"
                    },
                    "unit_amount": 100,
                },
                "quantity": 1,
            }],
            mode="payment",
            payment_intent_data={
                "application_fee_amount": 10,
                "transfer_data": {
                    "destination": oracle_id
                }
            },
            success_url="https://situationship-analyzer-web.onrender.com",
            cancel_url="https://situationship-analyzer-web.onrender.com",
        )

        return render_template("oracle_analysis.html", analysis=analysis, session_url=session.url)

    return render_template("oracle_analysis.html")

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

        if connected_account_id:
            try:
                with open('oracles.json', 'r') as f:
                    oracles = json.load(f)
            except FileNotFoundError:
                oracles = {}

            # Fetch name from Stripe if not stored
            if connected_account_id not in oracles:
                acct_info = stripe.Account.retrieve(connected_account_id)
                name = acct_info.get("business_profile", {}).get("name") or \
                       acct_info.get("individual", {}).get("first_name", "Unknown Oracle")
                oracles[connected_account_id] = {
                    "name": name,
                    "earned": 0.0,
                    "platform_cut": 0.0
                }

            oracles[connected_account_id]['earned'] += amount / 100
            oracles[connected_account_id]['platform_cut'] += round((amount / 100) * 0.1, 2)

            with open('oracles.json', 'w') as f:
                json.dump(oracles, f, indent=2)

    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    app.run(debug=True)
