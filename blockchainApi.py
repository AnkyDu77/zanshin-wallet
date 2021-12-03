import os
import re
import sys
import requests
import json
import pickle

from textwrap import dedent
from time import time
from datetime import datetime, timezone
from uuid import uuid4
from sys import argv
from urllib.parse import urlparse
from flask import render_template, Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from config import Config
from blockchain import Blockchain

from remoteNodes import RemoteNodes

from createWallet import createWallet
from authoriseUser import authoriseUser
from signTransaction import signTransaction
from getCoinbase import getCoinbase
from syncPools import syncPools
from sendAccountState import sendAccountState
from sendNewPool import sendNewPool


app = Flask(__name__)
CORS(app)
nodeIdentifier = str(uuid4()).replace('-','')
blockchain = Blockchain()
remoteNode = RemoteNodes().connect_to_node()
print(remoteNode)
if remoteNode == False:
    print("All remote nodes are on maintenance now. Please, try again later.")

# Get accounts and pools

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
            remoteNode = RemoteNodes().connect_to_node()
            if remoteNode == False:
                return jsonify({"MSG": "All remote nodes are on maintenance now. Please, try again later."}), 400


        psw = json.loads(request.data)['password']
        blockHash = json.loads(requests.get(remoteNode+'/remote-wallet/node/getLastBlockHash').content)['block_hash']
        address = createWallet(psw, blockHash, remoteNode)

        return jsonify({"ADDRESS": address}), 200


@app.route('/wallet/login', methods=['POST'])
def loginUser():
    if request.method == 'POST':

        """ Check if there is a connection to remote nodes """
        if remoteNode == False:
            remoteNode = RemoteNodes().connect_to_node()
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
            remoteNode = RemoteNodes().connect_to_node()
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
        remoteNode = RemoteNodes().connect_to_node()
        if remoteNode == False:
            return jsonify({"MSG": "All remote nodes are on maintenance now. Please, try again later."}), 400

    response = json.loads(requests.get(remoteNode+'/getTxPool').content)

    return jsonify(response), 200


@app.route('/getTradeOrders', methods=['GET'])
def tradeOrders(remoteNode=remoteNode):

    """ Check if there is a connection to remote nodes """
    if remoteNode == False:
        remoteNode = RemoteNodes().connect_to_node()
        if remoteNode == False:
            return jsonify({"MSG": "All remote nodes are on maintenance now. Please, try again later."}), 400

    response = json.loads(requests.get(remoteNode+'/getTradeOrders').content)

    return jsonify(response), 200


# if len(blockchain.nodes) > 0:
#     for node in blockchain.nodes:
#         try:
#             values = json.loads(requests.get('http://'+node+'/wallet/syncAllAccounts').content)
#             accounts = pickle.loads(bytes.fromhex(values['ACCOUNTS']))
#             if accounts == None:
#                 blockchain.accounts = []
#             else:
#                 blockchain.accounts = accounts
#                 blockchain.coinbase = accounts[0].address
#
#             pools = pickle.loads(bytes.fromhex(values['POOLS']))
#             if pools == None:
#                 blockchain.pools = []
#             else:
#                 blockchain.pools = pools
#             print('Accounts and pools were added')
#             break
#         except:
#             print(f'Node {node} is not respond or smt went wrong with sync process')






@app.route('/mine', methods=['GET'])
def mine():
    lastBlock = blockchain.lastBlock
    lastProof = lastBlock['proof']
    proof = blockchain.pow(lastProof)

    blockchain.newTransaction(
        sender=Config().MINEADDR,
        timestamp = datetime.now(timezone.utc).timestamp(),
        recipient=blockchain.coinbase,
        sendAmount=1
    )

    # Match trade txs and route trades
    blockchain.transactTradeOrders()

    # Make Transactions
    blockHash = blockchain.hash(blockchain.chain[-1])
    for transaction in blockchain.current_transactions:
        if transaction['symbol'] == 'zsh' or transaction['contract'] == 'zsh':
            try:
                account = [account for account in blockchain.accounts if account.address == transaction['recipient']][0]
                account.makeTransaction(transaction['sendAmount'], blockHash)
                syncAccState = sendAccountState(account, blockchain.nodes)
            except:
                return jsonify({'MSG': f'Something went terribly wrong with transaction to recipient {transaction["recipient"]}'}), 400
        else:
            try:
                blockchain.makePoolTransaction(transaction['contract'], transaction['recipient'], transaction['sendAmount'])
            except:
                return jsonify({'MSG': f'Something went terribly wrong with pool transaction to recipient {transaction["recipient"]}'}), 400

    previousHash = blockchain.hash(lastBlock)
    block = blockchain.newBlock(proof, previousHash)

    syncStatus = syncPools(blockchain.current_transactions, blockchain.trade_transactions, blockchain.nodes)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previousHash'],
        'pool_syncing': syncStatus
    }

    return jsonify(response), 200



@app.route('/transactions/sync', methods=['POST'])
def syncTxs():
    node = request.json['node']
    commonTxs = request.json['commonTxs']
    tradeTxs = request.json['tradeTxs']
    parsedUrl = urlparse(node)
    if parsedUrl.netloc in blockchain.nodes:
        blockchain.current_transactions = commonTxs
        blockchain.trade_transactions = tradeTxs
        print('Tx pool synced')
        return jsonify({'MSG': 'Tx pool synced'}), 200

    else:
        print('Node is not registered')
        return jsonify({'MSG': 'Node is not registered'}), 400


# @app.route('/getTxPool', methods=['GET'])
# def txPool():
#     response = {
#         'txPool': blockchain.current_transactions
#     }
#
#     return jsonify(response), 200
#
#
# @app.route('/getTradeOrders', methods=['GET'])
# def tradeOrders():
#     response = {
#         'tradeOrders': blockchain.trade_transactions
#     }
#
#     return jsonify(response), 200


@app.route('/chain', methods=['GET'])
def fullChain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
    }

    return jsonify(response), 200


@app.route('/chain/sync', methods=['POST'])
def syncCh():
    node = request.json['node']
    chain = request.json['chain']
    parsedUrl = urlparse(node)
    print(f'\n====\nparsedUrl.netloc: {parsedUrl.netloc}\n====\n\n')
    if parsedUrl.netloc in blockchain.nodes:
        blockchain.chain = chain
        if sys.getsizeof(blockchain.chain) >= Config().MAX_CHAIN_SIZE:
            with open(f'./chain/{int(datetime.now(timezone.utc).timestamp())}.json', 'w') as file:
                json.dump(blockchain.chain, file)
            blockchain.chain = [blockchain.chain[-1]]
        print('Chain synced')
        return jsonify({'MSG': 'Chain synced'}), 200

    else:
        print('Node is not registered')
        return jsonify({'MSG': 'Node is not registered'}), 400


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    print(values)

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please provide a valid list of nodes", 400

    for node in nodes:
        print(node)
        blockchain.registerNode(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolveConflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200

@app.route('/nodes/getNodes', methods=['GET'])
def gNodes():
    nodes = blockchain.nodes
    nodesList = [node for node in nodes]
    return json.dumps({"nodes": nodesList})


@app.route('/nodes/getChainFilesAmount', methods=['GET'])
def getChFAm():
    chainFiles = os.listdir(os.path.join(Config().BASEDIR, 'chain'))
    chainFiles = [file for file in chainFiles if re.split(r'\.', file)[1] == 'json']
    return jsonify({'MSG': len(chainFiles)}), 200


@app.route('/nodes/sendChainData', methods=['POST'])
def sendChData():
    # Get files names list
    chainFiles = os.listdir(os.path.join(Config().BASEDIR, 'chain'))
    chainFiles = [file for file in chainFiles if re.split(r'\.', file)[1] == 'json']

    # Get files index
    fileNum = request.json['iter']

    # Send file
    return send_from_directory(
        Config().UPLOAD_FOLDER, chainFiles[fileNum], as_attachment=True
    )





@app.route('/wallet/syncAllAccounts', methods=['GET'])
def sncAllAccounts():
    pickledAccounts = pickle.dumps(blockchain.accounts).hex()
    pickledPools = pickle.dumps(blockchain.pools).hex()

    return jsonify({'ACCOUNTS': pickledAccounts, 'POOLS': pickledPools}), 200


@app.route('/wallet/sync', methods=['POST'])
def sncAccs():

    node = request.json['node']
    parsedUrl = urlparse(node)

    if parsedUrl.netloc in blockchain.nodes:
        account = pickle.loads(bytes.fromhex(request.json['account']))
        blockchain.accounts.append(account)

        # Add account to pools
        if len(blockchain.pools) > 0:
            for pool in blockchain.pools:
                pool.accountsBalance[account.address]=0.0

        print('New account is added')
        return jsonify({'MSG': 'New account is added'}), 200

    else:
        print('Node is not registered')
        return jsonify({'MSG': 'Node is not registered'}), 400


@app.route('/wallet/sendAccountState', methods=['POST'])
def sAccState():
    node = request.json['node']
    parsedUrl = urlparse(node)

    if parsedUrl.netloc in blockchain.nodes:
        senderAccount = pickle.loads(bytes.fromhex(request.json['senderAccount']))
        # Sync miner tx
        if senderAccount == None:
            recipientAccount = pickle.loads(bytes.fromhex(request.json['recipientAccount']))
            blockchain.accounts = [recipientAccount if accountToSync.address == recipientAccount.address else accountToSync for accountToSync in blockchain.accounts]
            print(f'Account {recipientAccount.address} is synced')
            return jsonify({'MSG': f'Account {recipientAccount.address} is synced'}), 200

        # Sync common tx
        else:
            blockchain.accounts = [senderAccount if accountToSync.address == senderAccount.address else accountToSync for accountToSync in blockchain.accounts]

            recipientAccount = pickle.loads(bytes.fromhex(request.json['recipientAccount']))
            blockchain.accounts = [recipientAccount if accountToSync.address == recipientAccount.address else accountToSync for accountToSync in blockchain.accounts]

            print(f'Account {senderAccount.address} is synced')
            print(f'Account {recipientAccount.address} is synced')
            return jsonify({'MSG': f'Accounts:\n{senderAccount.address}\n{recipientAccount.address}\nis synced'}), 200

    else:
        print('Account syncing denied. Node is not registered')
        return jsonify({'MSG': 'Account syncing denied. Node is not registered'}), 400






@app.route('/wallet/getAccounts', methods=['GET'])
def gAccs():
    accounts = pickle.dumps(blockchain.accounts).hex()
    return jsonify({'ACCOUNTS': accounts}), 200


@app.route('/pools/createPool', methods=['POST'])
def crPool():
    values = json.loads(request.data)
    pool, creationResult = blockchain.createPool(values['name'], values['symbol'].upper())
    sendNewPool(pool, blockchain.nodes)
    return jsonify({"MSG": creationResult}), 200



@app.route('/pools/getNewPool', methods=['POST'])
def gNPool():
    pool = pickle.loads(bytes.fromhex(request.json['pool']))
    blockchain.pools.append(pool)

    # !!!! ==== ADD ACCOUNTS SYNCING THROUGH POOL ==== !!!!

    return jsonify({"MSG": f'{pool.name} pool was added'}), 200



@app.route('/pools/getPools', methods=['GET'])
def gPools():
    pools = blockchain.getPools()
    return json.dumps({"MSG": pools}), 200


@app.route('/pools/sendTokenPoolsState', methods=['POST'])
def sTokensPoolsState():
    node = request.json['node']
    parsedUrl = urlparse(node)

    if parsedUrl.netloc in blockchain.nodes:
        poolAddress = request.json['poolAddress']
        poolBalacne = request.json['poolBalacne']
        accountAddress = request.json['accountAddress']
        accountBalance = request.json['accountBalance']

        pool = [pool for pool in blockchain.pools if pool.poolAddress==poolAddress][0]
        pool.poolBalance = poolBalacne
        pool.accountsBalance[accountAddress] = accountBalance

        blockchain.pools = [pool if pool.poolAddress == replacePool.poolAddress else replacePool for replacePool in blockchain.pools]

        return jsonify({'MSG': 'Pool was successfully synced'}), 200

    else:
        print('Pools syncing denied. Node is not registered')
        return jsonify({'MSG': 'Pools syncing denied. Node is not registered'}), 400



if __name__ == '__main__':
    # _, host, port = argv
    app.run(host= '0.0.0.0', port=5000)
