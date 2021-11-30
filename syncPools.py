import requests

from flask import request
from config import Config


def syncPools(commonTxs,tradeTxs,nodes):
    c = 0

    try:
        whiteIp = requests.get('https://api.ipify.org').content
        whiteIp = whiteIp.decode()
    except:
        print('ipify.org connection denied')

    for node in nodes:
        try:
            requests.post("http://"+node+"/transactions/sync", json={'commonTxs':commonTxs, 'tradeTxs': tradeTxs, 'node': 'http://'+Config().DEFAULT_HOST+':'+Config().DEFAULT_PORT})
            c+=1
        except:
            print(f'Access to node {node} denied.')

    return f'Tx pool synced among {c} nodes'
