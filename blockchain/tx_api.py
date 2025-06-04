from flask import Blueprint, request, jsonify
from datetime import datetime
import hashlib
import json
from ecdsa import SigningKey, SECP256k1, BadSignatureError
from transactions.utxo import is_valid_transaction

def tx_bp(utxo_set, mempool, blockchain):
    bp = Blueprint('transaction', __name__)

    @bp.route('/new', methods=['POST'])
    def create_transaction():
        try:
            if not request.is_json:
                return jsonify({'status': 'error', 'message': 'Content-Type deve ser application/json'}), 400

            data = request.get_json()
            required_fields = {'sender', 'recipient', 'amount', 'private_key'}
            if not all(field in data for field in required_fields):
                missing = [f for f in required_fields if f not in data]
                return jsonify({'status': 'error', 'message': f'Campos obrigatórios faltando: {", ".join(missing)}'}), 400
                
            if data['sender'] == data['recipient']:
                return jsonify({'status': 'error', 'message': 'Remetente e destinatário não podem ser iguais'}), 400
            try:
                amount = float(data['amount'])
                if amount <= 0:
                    return jsonify({'status': 'error', 'message': 'O valor deve ser positivo'}), 400
            except (ValueError, TypeError):
                return jsonify({'status': 'error', 'message': 'Valor de transação inválido'}), 400

            sender_utxos = utxo_set.find_utxos(data['sender'])
            if not sender_utxos:
                return jsonify({'status': 'error', 'message': 'Nenhum UTXO disponível para o remetente'}), 400

            selected_utxos = []
            total_input = 0.0
            for utxo in sender_utxos:
                selected_utxos.append(utxo)
                total_input += utxo.amount
                if total_input >= amount:
                    break

            if total_input < amount:
                return jsonify({'status': 'error', 'message': f'Saldo insuficiente. Necessário: {amount}, Disponível: {total_input}'}), 400

            tx = {
                'version': 1,
                'sender': data['sender'],
                'recipient': data['recipient'],
                'amount': amount,
                'timestamp': datetime.utcnow().isoformat(),
                'inputs': [],
                'outputs': [],
                'signatures': []
            }

            for utxo in selected_utxos:
                tx['inputs'].append({
                    'txid': utxo.txid,
                    'index': utxo.index,
                    'public_key': utxo.public_key
                })

            tx['outputs'].append({
                'address': data['recipient'],
                'amount': amount,
                'public_key': ''
            })

            change = total_input - amount
            if change > 0:
                tx['outputs'].append({
                    'address': data['sender'],
                    'amount': change,
                    'public_key': selected_utxos[0].public_key
                })

            tx_str = json.dumps({k: v for k, v in tx.items() if k not in ['signatures']}, sort_keys=True)
            tx['txid'] = hashlib.sha256(tx_str.encode()).hexdigest()

            signing_key = SigningKey.from_string(bytes.fromhex(data['private_key']), curve=SECP256k1)
            for i, inp in enumerate(tx['inputs']):
                signing_data = f"{tx['txid']}:{i}".encode()
                signing_hash = hashlib.sha256(signing_data).digest()
                signature = signing_key.sign_digest(signing_hash)
                tx['signatures'].append(signature.hex())
                tx['inputs'][i]['signature'] = signature.hex()

                verifying_key = signing_key.verifying_key
                if not verifying_key.verify_digest(signature, signing_hash):
                    return jsonify({'status': 'error', 'message': 'Assinatura inválida gerada'}), 400

            is_valid, validation_msg = is_valid_transaction(tx, utxo_set)
            if not is_valid:
                return jsonify({'status': 'error', 'message': f'Transação inválida: {validation_msg}'}), 400

            try:
                mempool.add_transaction(tx)
                utxo_set.save_utxos()
            except Exception as e:
                return jsonify({'status': 'error', 'message': f'Erro ao adicionar ao mempool: {str(e)}'}), 400

            return jsonify({'status': 'success', 'txid': tx['txid'], 'message': 'Transação criada com sucesso'})

        except BadSignatureError as e:
            return jsonify({'status': 'error', 'message': 'Assinatura inválida - chave privada incorreta'}), 400
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Erro interno: {str(e)}'}), 500

    @bp.route('/pending', methods=['GET'])
    def pending_transactions():
        return jsonify({
            'count': len(mempool.transactions),
            'transactions': mempool.transactions
        })

    return bp