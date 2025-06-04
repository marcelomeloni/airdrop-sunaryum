import hashlib
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from nodes.node_manager import NodeManager
from transactions.utxo import UTXOSet
from blockchain.consensus import ProofOfEnergy
from ecdsa import SigningKey, SECP256k1, VerifyingKey
from transactions.mempool import Mempool
from transactions.utxo import is_valid_transaction
def compress_pubkey(pubkey_hex: str) -> str:
    # Remove o prefixo 0x04 que indica chave pública não comprimida
    pubkey_bytes = bytes.fromhex(pubkey_hex)
    if pubkey_bytes[0] == 0x04:
        vk = VerifyingKey.from_string(pubkey_bytes[1:], curve=SECP256k1)
        compressed = vk.to_string("compressed").hex()
        return compressed
    else:
        # Já comprimida ou formato diferente, retorna original
        return pubkey_hex

# Geração da chave para endereço (exemplo, pode não ser usada diretamente aqui)
sk = SigningKey.generate(curve=SECP256k1)
vk = sk.verifying_key

# Chave pública não comprimida (com prefixo 04)
public_key_uncompressed = '04' + vk.to_string().hex()

# Chave pública comprimida (sem prefixo 04)
public_key_compressed = compress_pubkey(public_key_uncompressed)

# Hash SHA-1 da chave pública comprimida para gerar o endereço
address = hashlib.sha1(public_key_compressed.encode()).hexdigest()

_blockchain = None

def init_blockchain(utxo_set=None):
    global _blockchain
    if _blockchain is None:
        # Se receber um UTXOSet, usa-o. Caso contrário, cria novo.
        _blockchain = Blockchain(utxo_set=utxo_set)  # Modificado!
    return _blockchain
def mine_mempool_transactions(blockchain, mempool, max_txs=100):
    pending_txs = mempool.get_transactions_for_block(max_txs)
    if not pending_txs:
        print("[MINER] Nenhuma transação pendente para minerar.")
        return None

    valid_txs = []
    for tx in pending_txs:
        if is_valid_transaction(tx, blockchain.utxo_set):
            valid_txs.append(tx)
        else:
            print(f"[MINER] Transação inválida descartada: {tx['txid']}")

    if not valid_txs:
        print("[MINER] Nenhuma transação válida após verificação.")
        return None

    daily_data = blockchain.node_manager.aggregate_daily_data()
    print("[DEBUG] daily_data:", daily_data)  # DEBUG

    if daily_data is None or 'total_energy' not in daily_data:
        print("[MINER] daily_data inválido para minerar bloco.")
        return None

    daily_data['transactions'] = valid_txs
    blockchain.node_manager.aggregate_daily_data = lambda: daily_data

    try:
        new_block = blockchain.add_block()
    except Exception as e:
        print(f"[ERROR] Falha ao minerar bloco: {e}")
        return None

    mempool.remove_confirmed_transactions([tx['txid'] for tx in valid_txs])
    print(f"[MINER] Bloco {new_block['index']} minerado com {len(valid_txs)} transações.")
    return new_block

class Blockchain:
    def __init__(self, utxo_set=None):
        self.chain = []
        self.fusohorario = ZoneInfo("America/Sao_Paulo")

        # ✅ Inicializa o UTXOSet primeiro
        self.utxo_set = utxo_set if utxo_set else UTXOSet()

        # 🔧 Só depois carrega a blockchain
        self.load_chain()

        # ✅ Inicializa dependências restantes
        self.mempool = Mempool(self.utxo_set)
        self.consensus = ProofOfEnergy(self)
        self.node_manager = NodeManager(self)

        # ✅ Reconstrói UTXOs se estiverem vazios
        if not utxo_set:
            self.utxo_set.load_utxos()
            if not self.utxo_set.utxos:
                self._rebuild_utxos()
    
    def load_chain(self):
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
        os.makedirs(data_dir, exist_ok=True)
        self.blockchain_file = os.path.join(data_dir, 'blockchain.json')
        try:
            with open(self.blockchain_file, 'r') as f:
                self.chain = json.load(f)
        except FileNotFoundError:
            self.create_genesis_block()
    def mine_mempool_transactions(self, max_txs=10000):
        """Mina transações da mempool e cria novo bloco"""
        pending_txs = self.mempool.get_transactions_for_block(max_txs)

        if not pending_txs:
            print("[MINER] Nenhuma transação pendente para minerar.")
            return None

        try:
            new_block = self.add_block(transactions=pending_txs)
            self.mempool.remove_confirmed_transactions([tx['txid'] for tx in new_block['transactions']])
            print(f"[MINER] Bloco {new_block['index']} minerado com {len(new_block['transactions'])} transações.")
            return new_block
        except Exception as e:
            print(f"[ERROR] Falha ao minerar bloco: {e}")
            return None
    def create_genesis_block(self):
        # Chave pública fixa que você já possui (não comprimida)
        public_key_full  = "04" + "4a7ff1aa7356399c35c683ff9845e20407d33f1a7d6d9e24f3a328310b51efd0bf1513861313c43e13d9e94242170eec662ddcbaccb73944818ab1a2d887446e"
        # Comprime a chave pública para guardar na saída
        public_key_compressed = compress_pubkey(public_key_full)
        # Endereço fixo que você já possui
        address = "07281107d057ca7718521a70f3406675c985a1cc"

        genesis_tx = {
            'txid': 'genesis-tx-1',
            'inputs': [],
            'outputs': [
                {
                    'address': address,
                    'amount': 1000.0,
                    'public_key': public_key_compressed
                }
            ],
            'type': 'genesis',
            'date': self.current_time(),
            'status': 'confirmed'
        }

        genesis = {
            'index': 0,
            'timestamp': self.current_time(),
            'consolidated_energy': 0,
            'transactions': [genesis_tx],
            'previous_hash': '0'*64,
            'node_count': 0
        }
        genesis['hash'] = self.calculate_hash(genesis)
        self.chain.append(genesis)
        self._update_utxos(genesis)
        self.save_chain()

    def _rebuild_utxos(self):
        """Reconstroi todos os UTXOs a partir da blockchain"""
        # Limpa UTXOs existentes
        self.utxo_set.reset()
        
        # Processa todos os blocos desde o genesis
        for block in self.chain:
            for tx in block.get('transactions', []):
                # Processa inputs (gasta UTXOs)
                for inp in tx.get('inputs', []):
                    self.utxo_set.spend_utxo(inp['txid'], inp['index'])
                
                # Processa outputs (cria novos UTXOs)
                for idx, out in enumerate(tx.get('outputs', [])):
                    public_key = out.get('public_key', '')
                    self.utxo_set.add_utxo(
                        out['address'],
                        tx['txid'],
                        idx,
                        out['amount'],
                        public_key
                    )
        self.utxo_set.save_utxos()
        print(f"[Blockchain] UTXOs reconstruídos - {len(self.utxo_set.utxos)} UTXOs registrados")
    def _update_utxos(self, block):
        """Atualiza UTXOs com as transações de um bloco recém-minerado"""
        for tx in block['transactions']:
            # Processa inputs (gasta UTXOs)
            for inp in tx.get('inputs', []):
                self.utxo_set.spend_utxo(inp['txid'], inp['index'])
            
            # Processa outputs (cria novos UTXOs)
            for idx, out in enumerate(tx.get('outputs', [])):
                public_key = out.get('public_key', '')
                self.utxo_set.add_utxo(
                    out['address'],
                    tx['txid'],
                    idx,
                    out['amount'],
                    public_key
                )
        self.utxo_set.save_utxos()

    def add_block(self, transactions=None):
        """Cria novo bloco com transações da mempool"""
        # Pega transações da mempool se não forem fornecidas
        if transactions is None:
            transactions = self.mempool.get_transactions_for_block(10000)
            
        # Filtra transações válidas
        valid_txs = [tx for tx in transactions 
                    if is_valid_transaction(tx, self.utxo_set)]
        
        # Obtém estatísticas de energia
        energy_stats = self.node_manager.get_energy_stats()
        
        # Cria bloco
        new_block = {
            'index': len(self.chain),
            'timestamp': self.current_time(),
            'transactions': valid_txs,
            'total_energy': energy_stats['total_energy'],
            'valid_nodes': energy_stats['valid_nodes'],
            'previous_hash': self.chain[-1]['hash'] if self.chain else '0'*64,
            'hash': ''
        }
        
        new_block['hash'] = self.calculate_hash(new_block)
        
        # Atualiza UTXOs
        self._update_utxos(new_block)
        
        # Limpa dados após mineração
        self.node_manager.reset_daily_data()
        
        self.chain.append(new_block)
        self.save_chain()
        
        return new_block

    def calculate_hash(self, block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def save_chain(self):
        # Garante que o caminho do arquivo está definido
        if not hasattr(self, 'blockchain_file'):
            self.blockchain_file = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', 'data', 'blockchain.json')
            )
        with open(self.blockchain_file, 'w') as f:
            json.dump(self.chain, f, indent=2)

    def current_time(self):
        return datetime.now(self.fusohorario).isoformat()


# blockchain/core.py

def get_chain():
    if _blockchain is None:
        init_blockchain()
    return _blockchain.chain
