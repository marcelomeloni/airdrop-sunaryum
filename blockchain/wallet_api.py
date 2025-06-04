from flask import Blueprint, jsonify, request
from blockchain.wallet import Wallet
from blockchain.core import init_blockchain
from mnemonic import Mnemonic
from ecdsa import SigningKey, SECP256k1


def wallet_bp(utxo_set, mempool):
    bp = Blueprint('wallet', __name__)
    
    @bp.route('/import', methods=['POST'])
    def import_wallet():
        data = request.get_json()
        mnemonic = data.get('mnemonic')
        if not mnemonic:
            return jsonify({'error': 'Mnemonic required'}), 400

        mnemo = Mnemonic('english')
        if not mnemo.check(mnemonic):
            return jsonify({'error': 'Invalid mnemonic'}), 400

        try:
            seed = mnemo.to_seed(mnemonic, passphrase="")
            priv_key_bytes = seed[:32]
            priv = SigningKey.from_string(priv_key_bytes, curve=SECP256k1)
            pub = priv.get_verifying_key()
            address = Wallet.generate_address(pub)

            return jsonify({
                'mnemonic': mnemonic,
                'address': address,
                'public_key': pub.to_string().hex(),
                'private_key': priv.to_string().hex()
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @bp.route('/new', methods=['GET'])
    def new_wallet():
        w = Wallet.create()
        return jsonify({
            'mnemonic': w.mnemonic,
            'address': w.address,
            'public_key': w.public_key.to_string().hex(),
            'private_key': w.private_key.to_string().hex()
        })

    @bp.route('/balance/<address>', methods=['GET'])
    def get_balance(address):
        """Retorna o saldo total baseado nos UTXOs confirmados"""
        try:
            return jsonify({
                "address": address,
                "balance": utxo_set.get_balance(address),
                "unit": "BTLF"
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @bp.route('/utxos/<address>', methods=['GET'])
    def get_utxos(address):
        """Lista todos os UTXOs confirmados do endereço"""
        try:
            return jsonify({
                "address": address,
                "utxos": [utxo.to_dict() for utxo in utxo_set.find_utxos(address)]
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500


    @bp.route('/transactions/<address>', methods=['GET'])
    def wallet_transactions(address):
        # Recarrega o blockchain e o mempool dinamicamente
        blockchain = init_blockchain()
        mempool.load_transactions()  # Força recarregar do disco
        
        history = []

        # --- Confirmadas ---
        for block in blockchain.chain:
            ts = block.get('timestamp')
            for tx in block.get('transactions', []):
                sender = tx.get('sender')
                sent = 0
                received = 0

                if sender == address:
                    # Enviado: outputs que não são pra si mesmo
                    sent = sum(
                        out.get('amount', 0) for out in tx.get('outputs', [])
                        if out.get('address') != address
                    )
                else:
                    # Recebido: outputs para mim
                    received = sum(
                        out.get('amount', 0) for out in tx.get('outputs', [])
                        if out.get('address') == address
                    )

                if sent > 0:
                    history.append({'txid': tx['txid'], 'type': 'sent (confirmed)', 'amount': sent, 'date': ts})
                if received > 0:
                    history.append({'txid': tx['txid'], 'type': 'received (confirmed)', 'amount': received, 'date': ts})

        # --- Pendentes ---
        for tx in mempool.get_all_transactions():
            txid = tx.get('txid')
            ts = tx.get('timestamp') or tx.get('date')
            sender = tx.get('sender')
            sent_pending = 0
            received_pending = 0

            if sender == address:
                sent_pending = sum(
                    out.get('amount', 0) for out in tx.get('outputs', [])
                    if out.get('address') != address
                )
            else:
                received_pending = sum(
                    out.get('amount', 0) for out in tx.get('outputs', [])
                    if out.get('address') == address
                )

            if sent_pending > 0:
                history.append({'txid': txid, 'type': 'sent (pending)', 'amount': sent_pending, 'date': ts})
            if received_pending > 0:
                history.append({'txid': txid, 'type': 'received (pending)', 'amount': received_pending, 'date': ts})

        history.sort(key=lambda x: x['date'], reverse=True)

        return jsonify({'transactions': history})


    return bp 