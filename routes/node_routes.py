import os
import json
from flask import Blueprint, request, jsonify
from threading import Lock
from datetime import datetime
def node_bp (blockchain):
    bp = Blueprint('node', __name__)
    lock = Lock()
    DATA_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    
    # Garante que a pasta data existe
    os.makedirs(DATA_FOLDER, exist_ok=True)

    def _add_wallet_to_quest_file(quest_name, wallet_address):
        """Adiciona carteira ao arquivo de quest com timestamp"""
        file_path = os.path.join(DATA_FOLDER, f'quest_{quest_name}.json')

        with lock:
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                else:
                    data = {"claimed_wallets": {}, "last_played": {}}

                current_time = datetime.utcnow().timestamp()

                # Verifica cooldown para mini_game
                if quest_name == 'mini_game':
                    last_played = data["last_played"].get(wallet_address, 0)
                    if current_time - last_played < 12 * 3600:  # 12 horas
                        return False

                    # Atualiza o último horário jogado
                    data["last_played"][wallet_address] = current_time

                # Adiciona à lista de claims
                if wallet_address not in data["claimed_wallets"]:
                    data["claimed_wallets"][wallet_address] = current_time

                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)

                return True

            except Exception as e:
                print(f"[ERROR] Erro ao processar quest: {str(e)}")
                raise

    @bp.route('/report_energy', methods=['POST'])
    def report_energy():
        """Endpoint para reportar energia"""
        try:
            # Validação básica
            if not request.is_json:
                return jsonify({'error': 'Content-Type must be application/json'}), 400
                
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Missing JSON payload'}), 400
            
            # Campos obrigatórios
            required_fields = ['wallet_address', 'public_key', 'energy', 'quest']
            missing = [field for field in required_fields if field not in data]
            if missing:
                return jsonify({'error': f'Missing fields: {missing}'}), 400

            # Validação de energia
            try:
                energy = float(data['energy'])
                if energy <= 0:
                    return jsonify({'error': 'Energy must be positive'}), 400
            except ValueError:
                return jsonify({'error': 'Invalid energy value'}), 400

            # Processamento no blockchain
            try:
                success = blockchain.node_manager.record_energy(
                    data['wallet_address'],
                    data['public_key'],
                    energy
                )
            except Exception as e:
                print(f"[API ERROR] Blockchain error: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': 'Blockchain processing failed',
                    'details': str(e)
                }), 500

            # Registra na quest se sucesso
            if success:
                try:
                    _add_wallet_to_quest_file(data['quest'], data['wallet_address'])
                    return jsonify({
                        'status': 'success',
                        'message': f'{energy}kWh converted to tokens',
                        'quest': data['quest']
                    }), 200
                except Exception as e:
                    print(f"[API ERROR] Quest registration failed: {str(e)}")
                    return jsonify({
                        'status': 'partial_success',
                        'message': 'Energy processed but quest not registered',
                        'error': str(e)
                    }), 207
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Energy validation failed'
                }), 400
                
        except Exception as e:
            print(f"[API CRITICAL ERROR] {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Internal server error',
                'error': str(e)
            }), 500

    return bp