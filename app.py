import os
import stripe
from flask import Flask, request, render_template, redirect, url_for
import uuid

app = Flask(__name__)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# In-memory store of connected oracles: {oracle_id: stripe_account_id}
oracles = {}

@app.route("/")
def home():
    return render_template("index.html", oracles=oracles)

@app.route("/onboard-oracle")
def onboard_oracle():
    oracle_id = str(uuid.uuid4())  # Generate a unique Oracle ID
    account = stripe.Account.create(type="express")

    # Temporarily store the Stripe account ID
    oracles[oracle_id] = account.id

    account_link = stripe.AccountLink.create(
        account=account.id,
        refresh_url=url_for("onboard_oracle", _external=True),
        return_url=url_for("oracle_success", oracle_id=oracle_id, _external=True),
        type="account_onboarding"
    )

    return redirect(account_link.url)

@app.route("/oracle-success")
def oracle_success():
    oracle_id = request.args.get("oracle_id")
    return f"✅ You are now an Oracle! Your ID is: {oracle_id}. Share it so people can pay you."

@app.route("/pay/<oracle_id>", methods=["POST"])
def pay_oracle(oracle_id):
    if oracle_id not in oracles:
        return "❌ Oracle not found", 404

    try:
        account_id = oracles[oracle_id]

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
            mode="payment",
            success_url=url_for("thank_you", _external=True),
            cancel_url=url_for("home", _external=True),
            payment_intent_data={
                "application_fee_amount": 10,  # You keep 10 cents
                "transfer_data": {
                    "destination": account_id,
                },
            }
        )

        return redirect(session.url, code=303)
    except Exception as e:
        return f"Error: {str(e)}"

@app.route("/thank-you")
def thank_you():
    return "✨ Thank you for consulting the Oracle."
