# app.py
from flask import Flask
from argparse import ArgumentParser
from flask_cors import CORS
from blockchain.wallet_api import wallet_bp
from blockchain.tx_api import tx_bp
from blockchain.chain_api import chain_bp
from transactions.utxo import UTXOSet
from transactions.mempool import Mempool
from blockchain.core import init_blockchain
from routes.node_routes import node_bp
from routes.quest_routes import quest_bp  # Importa o blueprint de quests
from apscheduler.schedulers.background import BackgroundScheduler
import os

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})

    # 1. Cria o UTXOSet e carrega do disco
    utxo_set = UTXOSet()
    utxo_set.load_utxos()

    # 2. Inicializa a blockchain com o UTXOSet compartilhado
    blockchain = init_blockchain(utxo_set)  # Passa o UTXOSet existente!

    # 3. Cria o Mempool vinculado ao mesmo UTXOSet
    mempool = Mempool(utxo_set)

    # 4. Configura a blockchain para usar o UTXOSet compartilhado
    blockchain.utxo_set = utxo_set
    blockchain.mempool = mempool
    
    app.register_blueprint(wallet_bp(utxo_set, mempool), url_prefix='/wallet')
    app.register_blueprint(tx_bp(utxo_set, mempool, blockchain), url_prefix='/transaction')
    app.register_blueprint(chain_bp(), url_prefix='/chain')
    app.register_blueprint(node_bp(blockchain), url_prefix='/node')
    app.register_blueprint(quest_bp(), url_prefix='/quest')  # Registra o blueprint das quests

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=lambda: blockchain.mine_mempool_transactions(),
        trigger='cron',
        hour=15, 
        minute=26,
        timezone=blockchain.fusohorario
    ) 
    scheduler.start()

    return app 

if __name__ == '__main__': 
    parser = ArgumentParser()
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()

    app = create_app()
    app.run(host='0.0.0.0', port=args.port, debug=True)
