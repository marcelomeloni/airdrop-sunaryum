import json
import threading
from datetime import datetime
from .utxo import is_valid_transaction
import os
class Mempool:
    def __init__(self, utxo_set):
        self.transactions = []
        self.utxo_set = utxo_set    
        self.max_size = 10000
        self.lock = threading.Lock()

        # Caminho absoluto para o arquivo mempool.json na raiz do servidor
        self.mempool_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mempool.json'))
        self.load_transactions()

    def add_transaction(self, tx):
        with self.lock:
            # — suas validações existentes —
            for inp in tx.get('inputs', []):
                if not self.utxo_set.get_utxo(inp['txid'], inp['index']):
                    raise Exception(f"UTXO {inp['txid']}:{inp['index']} não encontrado ou já gasto")

            # adiciona timestamp se necessário
            if 'timestamp' not in tx:
                tx['timestamp'] = datetime.utcnow().isoformat()

            # **1. remova do UTXOSet os inputs desta tx**
            for inp in tx['inputs']:
                self.utxo_set.spend_utxo(inp['txid'], inp['index'])

            # **2. adicione ao UTXOSet os outputs desta tx**
            for idx, out in enumerate(tx.get('outputs', [])):
                self.utxo_set.add_utxo(
                    out['address'],
                    tx['txid'],
                    idx,
                    out['amount'],
                    out.get('public_key', '')
                )

            # **3. persista as mudanças no utxos.json**
            self.utxo_set.save_utxos()

            # agora sim adiciona ao mempool
            self.transactions.append(tx)
            self.save_transactions()
            print(f"[MEMPOOL] Transação {tx['txid']} adicionada e UTXOSet atualizado")
    def _calculate_txid(self, tx):
        """Calcula um TXID único para a transação"""
        import hashlib
        tx_str = json.dumps(tx, sort_keys=True)
        return hashlib.sha256(tx_str.encode()).hexdigest()

    def get_all_transactions(self):
        """Retorna cópia segura das transações"""
        with self.lock:
            return self.transactions.copy()

    def get_transactions_for_block(self, max_count=100):
        """Retorna transações para mineração, ordenadas por fee"""
        with self.lock:
            sorted_txs = sorted(
                self.transactions,
                key=lambda x: (-x.get('fee', 0), x['timestamp'])
            )
            return sorted_txs[:max_count]

    def remove_confirmed_transactions(self, txids):
        """Remove transações confirmadas em blocos"""
        with self.lock:
            initial_count = len(self.transactions)
            self.transactions = [
                tx for tx in self.transactions 
                if tx['txid'] not in txids
            ]
            removed = initial_count - len(self.transactions)
            if removed > 0:
                print(f"[MEMPOOL] Removidas {removed} transações confirmadas")
                self.save_transactions()
    def add_system_transaction(self, tx):
        """Adiciona transações do sistema sem validação de inputs"""
        with self.lock:
            # Validação básica
            if not tx.get('outputs'):
                raise Exception("Transação do sistema sem outputs")
            
            # Gera TXID se necessário
            if 'txid' not in tx:
                tx['txid'] = self._calculate_txid(tx)
            
            # Adiciona outputs ao UTXO
            for idx, out in enumerate(tx['outputs']):
                self.utxo_set.add_utxo(
                    out['address'],
                    tx['txid'],
                    idx,
                    out['amount'],
                    out.get('public_key', '')
                )
            
            self.transactions.append(tx)
            self.save_transactions()
            print(f"[MEMPOOL] Recompensa instantânea {tx['txid']} adicionada")
    def save_transactions(self):
        try:
            with open(self.mempool_file, 'w') as f:
                json.dump(self.transactions, f, indent=2)
        except Exception as e:
            print(f"[ERROR] Falha ao salvar mempool: {e}")

    def load_transactions(self):
        try:
            with open(self.mempool_file, 'r') as f:
                self.transactions = json.load(f)
                print(f"[MEMPOOL] Carregadas {len(self.transactions)} transações")
        except (FileNotFoundError, json.JSONDecodeError):
            self.transactions = []