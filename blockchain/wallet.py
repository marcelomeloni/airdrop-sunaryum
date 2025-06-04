# blockchain/wallet.py
from mnemonic import Mnemonic
from ecdsa import SigningKey, SECP256k1, VerifyingKey, BadSignatureError
import hashlib
import json
from typing import List, Dict
from transactions.utxo import UTXOSet, UTXO

class InsufficientFundsError(Exception):
    pass

class InvalidTransactionError(Exception):
    pass

class Wallet:
    @staticmethod
    def create() -> 'Wallet':
        mnemo = Mnemonic('english')
        seed = mnemo.generate(strength=128)
        priv = SigningKey.generate(curve=SECP256k1)
        pub = priv.get_verifying_key()
        
        w = Wallet()
        w.mnemonic = seed
        w.private_key = priv
        w.public_key = pub
        w.address = Wallet.generate_address(pub)
        return w

    @staticmethod
    def generate_address(pub_key: VerifyingKey) -> str:
        return hashlib.sha256(pub_key.to_string()).hexdigest()[:40]

    @staticmethod
    def build_transaction(sender: str, recipient: str, amount: float, 
                      private_key: str, fee: float = 0.0001) -> Dict:
        utxo_set = UTXOSet()
        sk = SigningKey.from_string(bytes.fromhex(private_key), curve=SECP256k1)

        utxos = utxo_set.find_utxos(sender)
        if not utxos:
            raise InsufficientFundsError("Sem UTXOs disponíveis")

        total_input = sum(utxo.amount for utxo in utxos)
        required = amount + fee

        if total_input < required:
            raise InsufficientFundsError(f"Saldo insuficiente. Necessário: {required}, Disponível: {total_input}")

        inputs = []
        for utxo in utxos:
            input_data = {
                "txid": utxo.txid,
                "index": utxo.index,
                "public_key": sk.get_verifying_key().to_string("compressed").hex(),
                "signature": None
            }
            inputs.append(input_data)

        outputs = [
            {"address": recipient, "amount": amount, "locking_script": f"PKH:{recipient}"}
        ]

        change = total_input - required
        if change > 0:
            outputs.append({
                "address": sender,
                "amount": change,
                "locking_script": f"PKH:{sender}"
            })

        tx_data = {"inputs": inputs, "outputs": outputs}

        # Calcular hash dos dados da transação
        signing_data = hashlib.sha256(json.dumps(tx_data, sort_keys=True).encode()).digest()

        # Assinar a transação uma única vez
        signature = sk.sign(signing_data).hex()

        # Colocar essa assinatura em todos inputs
        for inp in inputs:
            inp["signature"] = signature

        txid = hashlib.sha256(json.dumps(tx_data, sort_keys=True).encode()).hexdigest()

        return {
            "txid": txid,
            "inputs": inputs,
            "outputs": outputs,
            "fee": fee
        }

    @staticmethod
    def verify_transaction(tx: Dict) -> bool:
        utxo_set = UTXOSet()

        required_fields = {"txid", "inputs", "outputs"}
        if not all(field in tx for field in required_fields):
            return False

        # Calcular hash dos dados para verificação (inputs + outputs)
        signing_data = hashlib.sha256(json.dumps({"inputs": tx["inputs"], "outputs": tx["outputs"]}, sort_keys=True).encode()).digest()

        for inp in tx["inputs"]:
            try:
                vk = VerifyingKey.from_string(
    bytes.fromhex(inp["public_key"]), 
    curve=SECP256k1,
    validate_point=True
)
                if not vk.verify(bytes.fromhex(inp["signature"]), signing_data):
                    return False
            except BadSignatureError:
                return False

        total_input = 0
        for inp in tx["inputs"]:
            utxo = utxo_set.utxos.get(inp["txid"], {}).get(inp["index"])
            if not utxo:
                return False
            total_input += utxo.amount

        total_output = sum(out["amount"] for out in tx["outputs"]) + tx.get("fee", 0)
        return abs(total_input - total_output) < 1e-8
