import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from threading import Lock
import hashlib

class NodeManager:
    def __init__(self, blockchain):  # ✅ Agora recebe apenas 1 argumento
        self.data_file = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', 'data', 'energy_pool.json'))
        self.blockchain = blockchain  # Armazena a blockchain inteira
        self.lock = Lock()  # Lock para operações de arquivo
        
        # Garante que o arquivo de dados existe
        with self.lock:
            if not os.path.exists(self.data_file):
                with open(self.data_file, 'w') as f:
                    json.dump([], f)

    # Acesso aos componentes via blockchain
    @property
    def mempool(self):
        return self.blockchain.mempool
        
    @property
    def consensus(self):
        return self.blockchain.consensus
        
    @property
    def utxo_set(self):
        return self.blockchain.utxo_set

    def get_energy_stats(self):
        """Obtém estatísticas de energia"""
        with self.lock:
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
            except:
                data = []
        
        return {
            'total_energy': sum(entry.get('energy', 0) for entry in data),
            'valid_nodes': len({entry['wallet_address'] for entry in data if 'wallet_address' in entry})
        }

    def reset_daily_data(self):
        """Limpa os registros diários de energia"""
        with self.lock:
            try:
                with open(self.data_file, 'w') as f:
                    json.dump([], f)
                print("[NodeManager] Dados diários resetados")
            except Exception as e:
                print(f"[NodeManager] Erro ao resetar dados: {str(e)}")
                raise

    def record_energy(self, wallet_address, public_key, energy):
        try:
            # Validação básica
            if not all([wallet_address, public_key, energy > 0]):
                print(f"[ERROR] Parâmetros inválidos: wallet_address={wallet_address}, public_key={public_key}, energy={energy}")
                return False

            print(f"[DEBUG] Registrando energia para {wallet_address[:6]}...")
            print(f"[DEBUG] Public Key recebida: {public_key}")
            
            # Validação do consenso
            if not self.consensus.validate_node(wallet_address, energy):
                print(f"[Consenso] Node {wallet_address[:6]}... inválido")
                return False
    
            # Cria e processa transação
            tx = self._create_reward_transaction(wallet_address, public_key, energy)
            self.mempool.add_system_transaction(tx)
            output = tx['outputs'][0]  # Assumindo que há apenas 1 output

            # Adiciona o UTXO
            self.utxo_set.add_utxo(
                address=output['address'],
                txid=tx['txid'],
                index=0,  # Índice fixo para a primeira saída
                amount=output['amount'],
                public_key=output['public_key']
            )
            self.utxo_set.save_utxos()
            self._save_energy_record(wallet_address, public_key, energy)
            return True
        except Exception as e:
            print(f"[ERROR] Falha em record_energy: {str(e)}")
            return False

    def _create_reward_transaction(self, wallet_address, public_key, energy):
        """Cria transação de recompensa"""
        try:
            timestamp = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()
            tokens = self.consensus.mint_tokens(energy)
            
            return {
                'txid': hashlib.sha256(
                    f"{wallet_address}{timestamp}{energy}{public_key}".encode()
                ).hexdigest(),
                'inputs': [],
                'outputs': [{
                    'address': wallet_address,
                    'amount': tokens,
                    'public_key': public_key
                }],
                'type': 'instant_energy_reward',
                'timestamp': timestamp,
            }
        except Exception as e:
            print(f"[ERROR] Erro ao criar transação: {str(e)}")
            raise

    def _save_energy_record(self, wallet_address, public_key, energy):
        """Salva registro de energia"""
        with self.lock:
            try:
                # Lê dados existentes
                if os.path.exists(self.data_file):
                    with open(self.data_file, 'r') as f:
                        data = json.load(f)
                else:
                    data = []
                
                # Adiciona novo registro
                data.append({
                    'wallet_address': wallet_address,
                    'public_key': public_key,
                    'energy': energy,
                    'timestamp': datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()
                })
                
                # Escreve de volta
                with open(self.data_file, 'w') as f:
                    json.dump(data, f, indent=2)
                    
            except Exception as e:
                print(f"[ERROR] Falha ao salvar registro: {str(e)}")
                raise
