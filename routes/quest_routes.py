# routes/quest_routes.py
import json
import os
from flask import Blueprint, jsonify

def quest_bp():
    bp = Blueprint('quest', __name__)

    DATA_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    os.makedirs(DATA_FOLDER, exist_ok=True)

    def load_claim_data(quest_name):
        file_path = os.path.join(DATA_FOLDER, f'quest_{quest_name}.json')
        if not os.path.exists(file_path):
            return {"claimed_wallets": {}, "last_played": {}} # Estrutura corrigida
        with open(file_path, 'r') as f:
            return json.load(f)

    @bp.route('/claim_status/<quest_name>/<wallet_address>', methods=['GET'])
    def claim_status(quest_name, wallet_address):
        claim_data = load_claim_data(quest_name)
        claimed = wallet_address in claim_data.get('claimed_wallets', {})
        last_played = claim_data.get('last_played', {}).get(wallet_address, 0)

        response = {
            'claimed': claimed,
            'last_played': last_played,
            'cooldown': 12 * 3600  # 12 horas em segundos
        }
        return jsonify(response)

    return bp
