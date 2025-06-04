# blockchain/chain_api.py
from flask import Blueprint, jsonify
from blockchain.core import get_chain

def chain_bp():
    bp = Blueprint('chain', __name__)

    @bp.route('/', methods=['GET'])
    def full_chain():
        chain = get_chain()
        return jsonify(chain)
    
    return bp