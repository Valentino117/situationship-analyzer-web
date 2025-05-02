import os
import openai
import stripe
import json
import base64
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Load environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create-oracle-account')
def create_oracle_account():
    account = stripe.Account.create(
        type="express",
        capabilities={"transfers": {"requested": True}}
    )
    account_link = stripe.AccountLink.create(
        account=account.id,
        refresh_url=url_for('index', _external=True),
        return_url=f"https://situationship-analyzer-web.onrender.com/oracle-success?account_id={account.id}",
        type="account_onboarding"
    )
    return redirect(account_link.url)

@app.route('/oracle-success')
def oracle_success():
    account_id = request.args.get("account_id")
    return redirect(f"/oracle-dashboard?account_id={account_id}")

@app.route('/oracle-dashboard')
def oracle_dashboard():
    account_id = request.args.get('account_id')
    return render_template('oracle_dashboard.html', account_id=account_id)

@app.route('/oracle-analysis', methods=['POST'])
def oracle_analysis():
    account_id = request.form.get('account_id')
    file = request.files['screenshot']
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Read image and encode for GPT-4 Vision
    with open(filepath, "rb") as image_file:
        image_data = image_file.read()

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are a wise oracle offering guidance on romantic situations based on screenshots of texts. You channel insight, intuition, and warmth. Speak directly to the user."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What can you divine from this situation?"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64.b64encode(image_data).decode()}"

                        }
                    }
                ]
            }
        ],
        max_tokens=1000
    )

    analysis = response.choices[0].message.content

    # Create a payment link for $1.00
    price = stripe.Price.create(
        unit_amount=100,
        currency='usd',
        product_data={'name': 'Situationship Reading'},
    )
    session = stripe.checkout.Session.create(
        line_items=[{'price': price.id, 'quantity': 1}],
        mode='payment',
        payment_intent_data={
            'application_fee_amount': 10,  # 10 cents for the platform
            'transfer_data': {
                'destination': account_id,
            },
        },
        success_url='https://situationship-analyzer-web.onrender.com',
        cancel_url='https://situationship-analyzer-web.onrender.com',
    )

    return render_template('oracle_dashboard.html', account_id=account_id, analysis=analysis, payment_link=session.url)

@app.route('/webhook', methods=['POST'])
def webhook():
    from flask import request, jsonify

    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception:
        return jsonify(success=False), 400

    if event['type'] == 'charge.succeeded':
        charge = event['data']['object']
        destination = charge.get('destination')
        amount = charge['amount']

        if destination:
            try:
                with open("oracles.json", "r") as f:
                    data = json.load(f)
            except FileNotFoundError:
                data = {}

            if destination not in data:
                acct = stripe.Account.retrieve(destination)
                name = acct.get('individual', {}).get('first_name') or f"Oracle {destination[-4:]}"
                data[destination] = {"name": name, "earned": 0.0, "platform_cut": 0.0}

            data[destination]["earned"] += amount / 100
            data[destination]["platform_cut"] += round((amount / 100) * 0.1, 2)

            with open("oracles.json", "w") as f:
                json.dump(data, f, indent=2)

    return jsonify(success=True)

if __name__ == '__main__':
    app.run(debug=True)
