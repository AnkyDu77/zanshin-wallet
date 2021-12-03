import os
import re
import sys
import requests
import json
import pickle
import webbrowser as wb

from time import time
from datetime import datetime, timezone
from uuid import uuid4
from flask import render_template, Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from config import Config
from blockchain import Blockchain


from createWallet import createWallet
from authoriseUser import authoriseUser
from signTransaction import signTransaction


app = Flask(__name__)
CORS(app)
nodeIdentifier = str(uuid4()).replace('-','')
blockchain = Blockchain()
remoteNode = Blockchain().connect_to_node()
print(remoteNode)
if remoteNode == False:
    print("All remote nodes are on maintenance now. Please, try again later.")

# try:
#     wb.get(using='chrome').open_new(f'http://{Config().DEFAULT_HOST}:{Config().DEFAULT_PORT}')
# except:
wb.open_new(f'http://{Config().DEFAULT_HOST}:{Config().DEFAULT_PORT}')
"""
I. Connect to Full Node

1. Searching for full nodes out of trust list.
2. Connect to first full node that was found.


II. Default Browser Open


III. Modify /transactions/new to send to full node mode

Set unique endpoints on full nodes for working with wallets nodes.

"""

@app.route('/', methods=['GET'])
@app.route('/index.html', methods=['GET'])
def index():
    # return jsonify({'MSG': 'Working'}), 200
    return render_template('index.html')

@app.route('/login.html', methods=['GET'])
def login():
    return render_template('login.html')

@app.route('/sign_up.html', methods=['GET'])
def sign_up():
    return render_template('sign_up.html')


@app.route('/wallet/new', methods=['POST'])
def newWallet(remoteNode=remoteNode):
    if request.method == 'POST':

        """ Check if there is a connection to remote nodes """
        if remoteNode == False:
            remoteNode = Blockchain().connect_to_node()
            if remoteNode == False:
                return jsonify({"MSG": "All remote nodes are on maintenance now. Please, try again later."}), 400


        psw = json.loads(request.data)['password']
        blockHash = json.loads(requests.get(remoteNode+'/remote-wallet/node/getLastBlockHash').content)['block_hash']
        address = createWallet(psw, blockHash, remoteNode)

        return jsonify({"ADDRESS": address}), 200


@app.route('/wallet/login', methods=['POST'])
def loginUser(remoteNode=remoteNode):
    if request.method == 'POST':

        """ Check if there is a connection to remote nodes """
        if remoteNode == False:
            remoteNode = Blockchain().connect_to_node()
            if remoteNode == False:
                return jsonify({"MSG": "All remote nodes are on maintenance now. Please, try again later."}), 400


        psw = json.loads(request.data)['password']
        pubKey, prKey, address = authoriseUser(psw)
        if prKey == False:
            return jsonify({'MSG': 'Wrong password or there is no wallet'}), 400

        blockchain.prkey = prKey
        blockchain.pubKey = pubKey
        return jsonify({'MSG': True, 'ADDRESS': address}), 200


@app.route('/wallet/logout', methods=['GET'])
def logoutUser():
    blockchain.prkey = None
    blockchain.pubKey = None
    return jsonify({'MSG': True}), 200




@app.route('/wallet/getBalance', methods=['POST'])
def gBalance(remoteNode=remoteNode):
    if request.method == 'POST':
        """ Check if there is a connection to remote nodes """
        if remoteNode == False:
            remoteNode = Blockchain().connect_to_node()
            if remoteNode == False:
                return jsonify({"MSG": "All remote nodes are on maintenance now. Please, try again later."}), 400


        address = json.loads(request.data)['address']
        balances = json.loads(requests.post(remoteNode+'/remote-wallet/getBalance', json={'address': address}).content)
        return jsonify(balances), 200



"""
NEW TRANSACTION

1. Sign transaction localy.
2. Remote expenditure proof.
3. Remote newTransaction.

"""
@app.route('/transactions/new', methods=['POST'])
def newTx(remoteNode=remoteNode):

    # values = request.get_json()
    values = json.loads(request.data)
    required = Config().REQUIRED_TX_FIELDS
    if not all(k in values for k in required):
        return jsonify({'MSG':'Missing values'}), 400

    # Define orders type
    type = values['type']

    if type not in Config().REQUIRED_TX_TYPE:
        return jsonify({'MSG': 'Transaction type error! Provide "common" or "trade" transaction'}), 400

    if type == 'common':

        if values['comissionAmount'] < Config().MIN_COMISSION:
            values['comissionAmount'] = Config().MIN_COMISSION

        timestamp = datetime.now(timezone.utc).timestamp()
        symbol = values['symbol']
        contract = values['contract']
        sender = values['sender']
        recipient = values['recipient']
        sendAmount = values['sendAmount']
        comissionAmount = values['comissionAmount']
        get=None
        price=0.0
        tradeTxHash=None


        # Sign transaction
        transactionDict = {
            'timestamp': timestamp,
            'symbol': symbol,
            'contract': contract,
            'sender': sender,
            'recipient': recipient,
            'sendAmount': sendAmount,
            'recieveAmount': get,
            'price': price,
            'comissionAmount': float(comissionAmount),
            'tradeTxId':tradeTxHash
        }

        try:
            # Sign message
            signiture = signTransaction(str(transactionDict), blockchain.prkey)

        except:
            return jsonify({'MSG': 'Simple tx not accepted. Try to sign in first'}), 400

        transactionDict['signiture'] = signiture
        transactionDict['type'] = type
        transactionDict['publicKey'] = blockchain.pubKey.hex()

        # return jsonify(transactionDict), 201
        syncStatus = json.loads(requests.post(remoteNode+'/remote-wallet/transactions/new', json=transactionDict).content)['MSG']


    elif type == 'trade':

        if values['comissionAmount'] < Config().MIN_COMISSION:
            values['comissionAmount'] = Config().MIN_COMISSION

        timestamp = datetime.now(timezone.utc).timestamp()
        sender = values['sender']
        symbol = values['symbol']
        price = values['price']
        send = values['send']
        sendVol = values['sendVol']
        get = values['get']
        getVol = values['getVol']
        comissionAmount = values['comissionAmount']


        transactionDict = {
            'timestamp': timestamp,
            'sender': sender,
            'symbol': symbol,
            'price': price,
            'send': send,
            'sendVol': sendVol,
            'get': get,
            'getVol': getVol,
            'comissionAmount':float(comissionAmount)
        }

        try:
            # Sign message
            signiture = signTransaction(str(transactionDict), blockchain.prkey)
            print(f'\n\nTx signiture: {signiture}\n\n')
        except:
            return jsonify({'MSG': 'Trade tx not accepted. Try to sign in first'}), 400

        transactionDict['signiture'] = signiture
        transactionDict['type'] = type
        transactionDict['publicKey'] = blockchain.pubKey.hex()
        syncStatus = json.loads(requests.post(remoteNode+'/remote-wallet/transactions/new', json=transactionDict).content)['MSG']

    return jsonify({'MSG': syncStatus}), 201


"""
Get trade orders and executed transactions pool
"""
@app.route('/getTxPool', methods=['GET'])
def txPool(remoteNode=remoteNode):

    """ Check if there is a connection to remote nodes """
    if remoteNode == False:
        remoteNode = Blockchain().connect_to_node()
        if remoteNode == False:
            return jsonify({"MSG": "All remote nodes are on maintenance now. Please, try again later."}), 400

    response = json.loads(requests.get(remoteNode+'/getTxPool').content)

    return jsonify(response), 200


@app.route('/getTradeOrders', methods=['GET'])
def tradeOrders(remoteNode=remoteNode):

    """ Check if there is a connection to remote nodes """
    if remoteNode == False:
        remoteNode = Blockchain().connect_to_node()
        if remoteNode == False:
            return jsonify({"MSG": "All remote nodes are on maintenance now. Please, try again later."}), 400

    response = json.loads(requests.get(remoteNode+'/getTradeOrders').content)

    return jsonify(response), 200


@app.route('/chain', methods=['GET'])
def fullChain(remoteNode=remoteNode):

    """ Check if there is a connection to remote nodes """
    if remoteNode == False:
        remoteNode = Blockchain().connect_to_node()
        if remoteNode == False:
            return jsonify({"MSG": "All remote nodes are on maintenance now. Please, try again later."}), 400

    response = json.loads(requests.get(remoteNode+'/chain').content)
    return jsonify(response), 200



if __name__ == '__main__':
    # _, host, port = argv
    app.run(host= '0.0.0.0', port=5000)
